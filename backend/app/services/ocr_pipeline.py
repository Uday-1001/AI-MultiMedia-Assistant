import io
import logging
import os
import re
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple, Callable

warnings.filterwarnings("ignore", message=".*pin_memory.*")

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


_thread_local = threading.local()


def _get_reader(languages: List[str]):
    """Return (or lazily create) the EasyOCR Reader for the current thread."""
    if not hasattr(_thread_local, "reader"):
        try:
            import easyocr
            import torch
            
            torch.set_num_threads(2)
            
            _thread_local.reader = easyocr.Reader(languages, gpu=False, verbose=False)
            logger.debug("EasyOCR reader initialised on thread %s", threading.current_thread().name)
        except ImportError:
            raise ImportError("EasyOCR is not installed. Run: pip install easyocr")
    return _thread_local.reader


def _page_to_array(page: fitz.Page, dpi: int) -> np.ndarray:
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False, colorspace=fitz.csGRAY)
    image = Image.frombytes("L", (pixmap.width, pixmap.height), pixmap.samples)

    image = image.filter(ImageFilter.SHARPEN)

    image_array = np.array(image)
    return np.stack([image_array, image_array, image_array], axis=-1)


def _sort_into_reading_order(ocr_results) -> List[Tuple]:

    annotated = []
    for bbox, text, confidence in ocr_results:
        top_y = min(pt[1] for pt in bbox)
        left_x = min(pt[0] for pt in bbox)
        annotated.append((top_y, left_x, bbox, text, confidence))

    annotated.sort(key=lambda x: (round(x[0] / 15), x[1]))
    return [(bbox, text, confidence) for _, _, bbox, text, confidence in annotated]


def _detect_section(text: str) -> Optional[str]:

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


class PDFOCRPipeline:

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
    
        try:
            pdf = fitz.open(pdf_path)
        except Exception as open_error:
            raise RuntimeError(f"Could not open '{pdf_path}': {open_error}") from open_error

        total_pages = len(pdf)
        logger.info("Starting parallel OCR on '%s' (%d pages, %d workers)", filename, total_pages, self.max_workers)

        page_arrays: Dict[int, np.ndarray] = {}
        for i in range(total_pages):
            try:
                page_arrays[i] = _page_to_array(pdf[i], self.dpi)
            except Exception as extraction_error:
                logger.warning("Could not rasterise page %d: %s — skipping.", i + 1, extraction_error)

        pdf.close()

        results: Dict[int, Document] = {}
        languages = self.languages  

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
