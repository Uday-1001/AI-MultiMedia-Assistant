"""
OCR pipeline for scanned / image-based PDFs.

Workflow:
  1. Detect whether a PDF is text-based or scanned (is_scanned).
  2. Rasterise pages with PyMuPDF and convert to grayscale.
  3. Run EasyOCR in parallel — each worker thread gets its own Reader instance
     so threads don't block each other on the model mutex.
  4. Re-assemble pages in order and return List[Document].

Performance notes:
  - DPI 200 is the sweet spot: ~56% less pixels than 300 DPI with negligible
    accuracy loss on standard print-resolution scans.
  - Grayscale cuts memory and OCR time by ~30% vs RGB.
  - Thread-local Readers mean N pages run truly concurrently on N cores.
  - max_workers defaults to half the CPU count — leaves room for the FastAPI
    event loop and embedding model to breathe.
"""

import io
import logging
import os
import re
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple, Callable

# Suppress PyTorch DataLoader warning about pin_memory on CPU
warnings.filterwarnings("ignore", message=".*pin_memory.*")

# CRITICAL FIX for parallel CPU inference:
# Must be set before importing numpy/torch to prevent internal libraries
# from spawning dozens of threads per worker and thrashing the CPU.
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import fitz  # PyMuPDF
import numpy as np
from langchain_core.documents import Document
from PIL import Image, ImageFilter, ImageOps

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Thread-local EasyOCR readers
#
# Why thread-local instead of a shared singleton?
# EasyOCR's Reader holds PyTorch model state that isn't thread-safe under
# concurrent readtext() calls. Giving each worker thread its own Reader
# lets pages run in parallel without locks, at the cost of ~300 MB RAM per
# extra thread — acceptable for a document pipeline.
# ---------------------------------------------------------------------------

_thread_local = threading.local()


def _get_reader(languages: List[str]):
    """Return (or lazily create) the EasyOCR Reader for the current thread."""
    if not hasattr(_thread_local, "reader"):
        try:
            import easyocr
            import torch
            
            # CRITICAL FIX for parallel CPU inference:
            # By default, PyTorch uses all available CPU cores for a single model.
            # If we have 4 workers running 4 models, they spawn 4 x 16 = 64 threads,
            # causing massive thread thrashing and slowing everything down.
            # We restrict each model to 1 or 2 internal threads to fix this.
            torch.set_num_threads(2)
            
            _thread_local.reader = easyocr.Reader(languages, gpu=False, verbose=False)
            logger.debug("EasyOCR reader initialised on thread %s", threading.current_thread().name)
        except ImportError:
            raise ImportError("EasyOCR is not installed. Run: pip install easyocr")
    return _thread_local.reader


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def _page_to_array(page: fitz.Page, dpi: int) -> np.ndarray:
    """
    Rasterise one PDF page directly to a grayscale numpy array.
    Skipping PIL RGB→grayscale conversion saves one intermediate copy.
    """
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    # "L" colorspace = 8-bit grayscale — much smaller than RGB
    pixmap = page.get_pixmap(matrix=matrix, alpha=False, colorspace=fitz.csGRAY)
    image = Image.frombytes("L", (pixmap.width, pixmap.height), pixmap.samples)

    # Light sharpening helps OCR on slightly blurry scans
    image = image.filter(ImageFilter.SHARPEN)

    # Stack to 3-channel array because EasyOCR expects HxWx3
    image_array = np.array(image)
    return np.stack([image_array, image_array, image_array], axis=-1)


def _sort_into_reading_order(ocr_results) -> List[Tuple]:
    """
    EasyOCR doesn't guarantee top-to-bottom order. We bucket detections into
    row-groups (15 px tolerance) then sort left-to-right within each group.
    """
    annotated = []
    for bbox, text, confidence in ocr_results:
        top_y = min(pt[1] for pt in bbox)
        left_x = min(pt[0] for pt in bbox)
        annotated.append((top_y, left_x, bbox, text, confidence))

    annotated.sort(key=lambda x: (round(x[0] / 15), x[1]))
    return [(bbox, text, confidence) for _, _, bbox, text, confidence in annotated]


def _detect_section(text: str) -> Optional[str]:
    """
    Lightweight heading heuristic — catches all-caps titles, numbered sections,
    and colon-terminated labels. Returns the first match or None.
    """
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        is_short = len(line) < 80
        is_all_caps = line.isupper() and len(line) > 3
        ends_with_colon = line.endswith(":")
        looks_numbered = bool(re.match(r"^\d+[\.\)]\s+\w", line))

        if is_short and (is_all_caps or ends_with_colon or looks_numbered):
            return line
    return None


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class PDFOCRPipeline:
    """
    Parallel scanned-PDF processor: EasyOCR + PyMuPDF.

    Usage:
        pipeline = PDFOCRPipeline(dpi=200, languages=["en"], max_workers=4)
        if pipeline.is_scanned("report.pdf"):
            docs = pipeline.process("report.pdf", filename="report.pdf")
    """

    SCANNED_CHAR_THRESHOLD = 10

    def __init__(
        self,
        dpi: int = 200,
        languages: List[str] = None,
        char_threshold: int = None,
        max_workers: int = None,
    ):
        self.dpi = dpi
        self.languages = languages or ["en"]
        self.max_workers = max_workers or max(1, os.cpu_count() // 2)
        if char_threshold is not None:
            self.SCANNED_CHAR_THRESHOLD = char_threshold

    def is_scanned(self, pdf_path: str) -> bool:
        """
        Count selectable characters across all pages. If the average per page
        is below the threshold the document is almost certainly image-only.
        """
        try:
            pdf_document = fitz.open(pdf_path)
            total_chars = sum(len(p.get_text("text").strip()) for p in pdf_document)
            avg_chars = total_chars / max(len(pdf_document), 1)
            pdf_document.close()
            result = avg_chars < self.SCANNED_CHAR_THRESHOLD
            logger.debug("is_scanned=%s (avg %.1f chars/page)", result, avg_chars)
            return result
        except Exception as file_error:
            logger.warning("Could not read PDF text layer: %s — assuming scanned.", file_error)
            return True

    def process(self, pdf_path: str, filename: str, progress_callback: Optional[Callable[[int, int, str], None]] = None) -> List[Document]:
        """
        Parallel OCR across all pages.

        Strategy:
          1. Rasterise every page to a numpy array (fast, done in the main thread).
          2. Submit each page's OCR work to a thread pool — each thread owns
             its own EasyOCR Reader so there's no locking on the model.
          3. Collect results, sort by page number, return Documents.

        Pages that raise any exception are skipped with a warning.
        """
        try:
            pdf = fitz.open(pdf_path)
        except Exception as open_error:
            raise RuntimeError(f"Could not open '{pdf_path}': {open_error}") from open_error

        total_pages = len(pdf)
        logger.info("Starting parallel OCR on '%s' (%d pages, %d workers)", filename, total_pages, self.max_workers)

        # Rasterise all pages upfront — fitz is not thread-safe so we do this
        # sequentially, but it's fast (just pixel math, no ML inference).
        page_arrays: Dict[int, np.ndarray] = {}
        for i in range(total_pages):
            try:
                page_arrays[i] = _page_to_array(pdf[i], self.dpi)
            except Exception as extraction_error:
                logger.warning("Could not rasterise page %d: %s — skipping.", i + 1, extraction_error)

        pdf.close()

        # OCR all rasterised pages in parallel
        results: Dict[int, Document] = {}
        languages = self.languages  # capture for lambda closure

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            future_to_page = {
                pool.submit(self._ocr_page_worker, page_num, image_array, filename, pdf_path, languages): page_num
                for page_num, image_array in page_arrays.items()
            }

            completed_count = 0
            for future in as_completed(future_to_page):
                page_num = future_to_page[future]
                completed_count += 1
                try:
                    extracted_document = future.result()
                    if extracted_document is not None:
                        results[page_num] = extracted_document
                    logger.info("OCR Progress: %d/%d pages processed ('%s')", completed_count, total_pages, filename)
                    if progress_callback:
                        progress_callback(completed_count, total_pages, f"🔍 Reading scanned document: {completed_count} of {total_pages} pages analyzed...")
                except Exception as worker_error:
                    logger.warning("OCR worker failed on page %d: %s — skipping.", page_num + 1, worker_error)

        # Sort by original page order before returning
        documents = [results[i] for i in sorted(results)]
        logger.info("OCR complete: %d/%d pages extracted from '%s'.", len(documents), total_pages, filename)
        return documents

    def _ocr_page_worker(
        self,
        page_num: int,
        img_array: np.ndarray,
        filename: str,
        pdf_path: str,
        languages: List[str],
    ) -> Optional[Document]:
        """
        Worker function — runs in its own thread.
        Gets/creates the thread-local Reader, runs OCR, returns a Document or None.
        """
        page_label = page_num + 1
        reader = _get_reader(languages)

        raw_results = reader.readtext(img_array, detail=1, paragraph=False)
        if not raw_results:
            logger.debug("Page %d: no text detected.", page_label)
            return None

        sorted_lines = _sort_into_reading_order(raw_results)

        lines = []
        confidences = []
        for _, text, confidence_score in sorted_lines:
            if text.strip():
                lines.append(text.strip())
                confidences.append(confidence_score)

        if not lines:
            return None

        page_text = "\n".join(lines)
        mean_conf = float(np.mean(confidences))

        return Document(
            page_content=page_text,
            metadata={
                "source": pdf_path,
                "filename": filename,
                "page": page_label,
                "document_type": "scanned",
                "ocr_confidence": round(mean_conf, 4),
                "section": _detect_section(page_text),
            }
        )
