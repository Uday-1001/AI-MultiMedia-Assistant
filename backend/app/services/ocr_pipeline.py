# Process scanned PDFs by converting pages to images and reading text with EasyOCR

import logging
import os
import re
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Optional, Tuple, Any

import fitz  # PyMuPDF
import numpy as np
from langchain_core.documents import Document
from PIL import Image, ImageFilter

# Limit BLAS threads so OCR workers don't fight each other for CPU cores.
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

warnings.filterwarnings("ignore", message=".*pin_memory.*")

logger = logging.getLogger(__name__)


# Thread-safe EasyOCR reader setup

_thread_local      = threading.local()
_reader_init_lock  = threading.Lock()   # serialises only the model download
_torch_threads_per_worker = 2           # overwritten at runtime; safe default


def _get_reader(languages: List[str]) -> Any:
    # Load EasyOCR model lazily to save startup time
    if not hasattr(_thread_local, "reader"):
        try:
            import torch
            torch.set_num_threads(_torch_threads_per_worker)

            import easyocr
            with _reader_init_lock:
                logger.info(
                    "Thread %s: initialising EasyOCR (langs=%s)...",
                    threading.current_thread().name, languages,
                )
            _thread_local.reader = easyocr.Reader(
                languages,
                gpu=False,
                verbose=False,
            )
            logger.info(
                "Thread %s: EasyOCR ready.",
                threading.current_thread().name,
            )
        except ImportError:
            raise ImportError(
                "EasyOCR is not installed. Run: pip install easyocr"
            )
    return _thread_local.reader




# Image processing utilities

def _page_to_image(page: fitz.Page, dpi: int, max_px: int = 6000) -> np.ndarray:
    # Convert PDF page to a high-contrast RGB image optimized for EasyOCR
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False, colorspace=fitz.csRGB)
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)

    w, h = image.size
    if max(w, h) > max_px:
        scale = max_px / max(w, h)
        image = image.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
        logger.debug("Page resized from %dx%d to %dx%d before OCR.", w, h, *image.size)

    # Enhance contrast instead of sharpening (which can create noise around letters)
    from PIL import ImageEnhance
    image = ImageEnhance.Contrast(image).enhance(1.5)
    
    return np.array(image)


def _sort_into_reading_order(results) -> List[Tuple]:
    # Arrange detected text boxes top-to-bottom, left-to-right
    annotated = []
    for bbox, text, confidence in results:
        top_y = min(pt[1] for pt in bbox)
        left_x = min(pt[0] for pt in bbox)
        annotated.append((top_y, left_x, bbox, text, confidence))
    annotated.sort(key=lambda x: (round(x[0] / 15), x[1]))
    return [(bbox, text, conf) for _, _, bbox, text, conf in annotated]


def _detect_section(text: str) -> Optional[str]:
    # Guess the section heading by looking for short, all-caps, or numbered lines
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        is_short = len(line) < 80
        is_all_caps = line.isupper() and len(line) > 3
        ends_with_colon = line.endswith(":")
        looks_numbered = bool(re.match(r"^\d+[\.\/\)]\s+\w", line))
        if is_short and (is_all_caps or ends_with_colon or looks_numbered):
            return line
    return None


# Main OCR Pipeline

class PDFOCRPipeline:
    # Run OCR on scanned documents using a thread pool for fast rasterization

    SCANNED_CHAR_THRESHOLD = 10  # avg chars/page below this → assumed scanned

    def __init__(
        self,
        dpi: int = 150,
        languages: Optional[List[str]] = None,
        char_threshold: Optional[int] = None,
        max_workers: Optional[int] = None,
    ):
        self.dpi = dpi
        self.languages = languages or ["en"]
        cpu_count = os.cpu_count() or 1
        self.max_workers = max_workers or max(1, cpu_count // 2)
        if char_threshold is not None:
            self.SCANNED_CHAR_THRESHOLD = char_threshold



    def is_scanned(self, pdf_path: str) -> bool:
        # Check if PDF lacks text layers (meaning it's just scanned images)
        try:
            pdf_document = fitz.open(pdf_path)
            total_chars = sum(len(str(p.get_text("text")).strip()) for p in pdf_document)
            avg_chars = total_chars / max(len(pdf_document), 1)
            pdf_document.close()
            result = avg_chars < self.SCANNED_CHAR_THRESHOLD
            logger.debug("is_scanned=%s (avg %.1f chars/page)", result, avg_chars)
            return result
        except Exception as file_error:
            logger.warning(
                "Could not read PDF text layer: %s — assuming scanned.", file_error
            )
            return True

    def process(
        self,
        pdf_path: str,
        filename: str,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[Document]:
        # Extract text from all pages and return as LangChain Documents
        try:
            pdf = fitz.open(pdf_path)
        except Exception as open_error:
            raise RuntimeError(
                f"Could not open '{pdf_path}': {open_error}"
            ) from open_error

        total_pages = len(pdf)
        logger.info(
            "Starting OCR on '%s' (%d pages, %d rasterisation workers)",
            filename, total_pages, self.max_workers,
        )

        # 1. Convert all pages to images concurrently
        page_arrays: Dict[int, np.ndarray] = {}
        for i in range(total_pages):
            try:
                page_arrays[i] = _page_to_image(pdf[i], self.dpi)
            except Exception as raster_error:
                logger.warning(
                    "Could not rasterise page %d: %s — skipping.", i + 1, raster_error
                )
        pdf.close()

        # 2. Extract text from each image concurrently
        results: Dict[int, Document] = {}
        languages = self.languages

        # Allocate CPU threads evenly across OCR workers
        global _torch_threads_per_worker
        cpu_count = os.cpu_count() or 1
        _torch_threads_per_worker = max(1, cpu_count // self.max_workers)

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            future_to_page = {
                pool.submit(
                    self._ocr_page_worker,
                    page_num, img_array, filename, pdf_path, languages
                ): page_num
                for page_num, img_array in page_arrays.items()
            }

            completed = 0
            for future in as_completed(future_to_page):
                page_num = future_to_page[future]
                completed += 1
                try:
                    doc = future.result()
                    if doc is not None:
                        results[page_num] = doc
                    logger.info(
                        "OCR Progress: %d/%d pages processed ('%s')",
                        completed, total_pages, filename,
                    )
                    if progress_callback:
                        progress_callback(
                            completed, total_pages,
                            f"🔍 Reading scanned document: {completed} of {total_pages} pages analysed…"
                        )
                except Exception as worker_error:
                    logger.warning(
                        "OCR worker failed on page %d: %s — skipping.",
                        page_num + 1, worker_error,
                    )

        documents = [results[i] for i in sorted(results)]
        logger.info(
            "OCR complete: %d/%d pages extracted from '%s'.",
            len(documents), total_pages, filename,
        )
        return documents

    # Worker function for parallel processing

    def _ocr_page_worker(
        self,
        page_num: int,
        img_array: np.ndarray,
        filename: str,
        pdf_path: str,
        languages: List[str],
    ) -> Optional[Document]:
        # Read text from a single image and format as a LangChain Document
        page_label = page_num + 1
        reader = _get_reader(languages)

        # Run inference using the thread-local reader with high-accuracy settings
        raw_results = reader.readtext(
            img_array, 
            batch_size=4,
            decoder='beamsearch',
            mag_ratio=1.5,
            adjust_contrast=0.5
        )

        if not raw_results:
            logger.debug("Page %d: no text detected.", page_label)
            return None

        # raw_results: List[(bbox, text, confidence)]
        sorted_lines = _sort_into_reading_order(raw_results)

        lines: List[str] = []
        confidences: List[float] = []
        for _, text, conf in sorted_lines:
            if text.strip():
                lines.append(text.strip())
                confidences.append(conf)

        if not lines:
            return None

        page_text = "\n".join(lines)
        mean_conf = float(np.mean(confidences)) if confidences else 0.0

        return Document(
            page_content=page_text,
            metadata={
                "source":         pdf_path,
                "filename":       filename,
                "page_number":    page_label,
                "section":        _detect_section(page_text),
                "parser_used":    "easyocr",
                "is_ocr":         True,
                "document_type":  "pdf_scanned",
                "ocr_confidence": round(mean_conf, 4),
            },
        )
