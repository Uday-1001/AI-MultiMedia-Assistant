# Handles file ingestion, routing documents to the right parsers and chunking text

from __future__ import annotations

import os
import logging
from typing import List, Optional, Dict, Any, Callable

from langchain_community.document_loaders import (
    PyMuPDFLoader,
    TextLoader,
    Docx2txtLoader,
)
from langchain_core.documents import Document
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter,
)

from .metadata import MetadataEnricher
from ..config.settings import settings

logger = logging.getLogger(__name__)

# Setup OCR if available for scanned files

try:
    from .ocr_pipeline import PDFOCRPipeline
    _ocr_pipeline = PDFOCRPipeline(
        dpi=settings.OCR_DPI,
        languages=settings.OCR_LANGUAGE.split(","),
        char_threshold=settings.OCR_SCANNED_CHAR_THRESHOLD,
        max_workers=settings.OCR_MAX_WORKERS or 4,
    )
    OCR_AVAILABLE = True
except ImportError as _ocr_import_err:
    OCR_AVAILABLE = False
    _ocr_pipeline = None
    logger.warning(
        "OCR pipeline unavailable (%s). Scanned PDFs will not be processed.",
        _ocr_import_err,
    )

# Setup Docling for rich document parsing

try:
    from .docling_parser import parse_with_docling
    DOCLING_AVAILABLE = True
except ImportError as _docling_import_err:
    DOCLING_AVAILABLE = False
    parse_with_docling = None  # type: ignore[assignment]
    logger.warning(
        "Docling unavailable (%s). Falling back to PyMuPDFLoader for PDFs.",
        _docling_import_err,
    )

# Header levels for splitting markdown files

_MARKDOWN_HEADERS = [
    ("#",   "heading_1"),
    ("##",  "heading_2"),
    ("###", "heading_3"),
]


def _make_pymupdf_documents(file_path: str) -> List[Document]:
    # Load basic PDF text as a fallback when Docling fails
    loader = PyMuPDFLoader(file_path)
    docs = list(loader.lazy_load())
    for doc in docs:
        # PyMuPDFLoader sets 'page' (0-based); normalise to 1-based page_number
        raw_page = doc.metadata.pop("page", None)
        doc.metadata.setdefault("page_number", (raw_page + 1) if raw_page is not None else None)
        doc.metadata.setdefault("section",       None)
        doc.metadata["parser_used"]   = "pymupdf"
        doc.metadata["is_ocr"]        = False
        doc.metadata["document_type"] = "pdf_digital"
    return docs


class IngestionService:

    _metadata_enricher = MetadataEnricher()

    SUPPORTED_EXTENSIONS = {
        "video":    [".mp4", ".mov", ".mkv", ".avi", ".webm"],
        "audio":    [".mp3", ".wav", ".m4a", ".flac"],
        "document": [".pdf", ".docx", ".pptx", ".txt"],
    }



    def get_file_type(self, filename: str) -> Optional[str]:
        ext = os.path.splitext(filename)[1].lower()
        for file_type, extensions in self.SUPPORTED_EXTENSIONS.items():
            if ext in extensions:
                return file_type
        return None

    def load_document(
        self,
        file_path: str,
        file_type: str,
        progress_callback: Optional[Callable] = None,
    ) -> List[Document]:
        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".pdf":
            return self._load_pdf(file_path, progress_callback)
        elif ext == ".docx":
            return self._load_docx(file_path)
        elif ext == ".pptx":
            return self._load_pptx(file_path)
        elif ext == ".txt":
            return self._load_txt(file_path)
        elif file_type in ["video", "audio"]:
            return []
        else:
            raise ValueError(f"Unsupported file extension: {ext}")

    def load_transcript(self, transcript_path: Optional[str]) -> List[Document]:
        if not transcript_path:
            return []
        return TextLoader(transcript_path, encoding="utf-8").load()

    def split_documents(
        self,
        documents: List[Document],
        chunk_size: int = 1500,
        chunk_overlap: int = 300,
    ) -> List[Document]:
        # Split documents intelligently based on their source format
        recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            add_start_index=True,
        )
        md_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=_MARKDOWN_HEADERS,
            strip_headers=False,
        )

        result: List[Document] = []

        for doc in documents:
            if doc.metadata.get("parser_used") == "docling":
                # Stage 1: split on Markdown headers (preserves hierarchy)
                try:
                    header_chunks = md_splitter.split_text(doc.page_content)
                except Exception as md_exc:
                    logger.warning(
                        "MarkdownHeaderTextSplitter failed, falling back to "
                        "RecursiveCharacterTextSplitter: %s", md_exc
                    )
                    header_chunks = [doc]

                # Propagate source document's metadata into header chunks
                for chunk in header_chunks:
                    chunk.metadata = {**doc.metadata, **chunk.metadata}

                # Stage 2: further split oversized sections
                further_split = recursive_splitter.split_documents(header_chunks)
                result.extend(further_split)
            else:
                result.extend(recursive_splitter.split_documents([doc]))

        return result

    def process_document(
        self,
        file_path: str,
        file_id: int,
        filename: str,
        file_type: str,
        transcript_path: Optional[str] = None,
        segment_timestamps: Optional[List[Dict]] = None,
        progress_callback: Optional[Callable] = None,
    ) -> List[Document]:

        if file_type in ["video", "audio"]:
            documents = self.load_transcript(transcript_path)
            for doc in documents:
                doc.metadata["source_type"] = file_type
                doc.metadata["filename"]    = filename
        else:
            documents = self.load_document(file_path, file_type, progress_callback)
            for doc in documents:
                doc.metadata["source_type"] = file_type
                doc.metadata["filename"]    = filename

        split_docs = self.split_documents(documents)

        enriched: List[Document] = []
        for i, doc in enumerate(split_docs):
            if file_type in ["video", "audio"] and segment_timestamps:
                ts_start, ts_end = self._metadata_enricher.extract_timestamps_from_segments(
                    doc.page_content, segment_timestamps
                )
                enriched_doc = self._metadata_enricher.enrich(
                    doc, file_id, filename, i,
                    timestamp_start=ts_start,
                    timestamp_end=ts_end,
                    parser_used=doc.metadata.get("parser_used"),
                    is_ocr=doc.metadata.get("is_ocr"),
                    document_type=doc.metadata.get("document_type"),
                    ocr_confidence=doc.metadata.get("ocr_confidence"),
                    section=doc.metadata.get("section"),
                )
            else:
                enriched_doc = self._metadata_enricher.enrich(
                    doc, file_id, filename, i,
                    page_number=doc.metadata.get("page_number"),
                    parser_used=doc.metadata.get("parser_used"),
                    is_ocr=doc.metadata.get("is_ocr"),
                    document_type=doc.metadata.get("document_type"),
                    ocr_confidence=doc.metadata.get("ocr_confidence"),
                    section=doc.metadata.get("section"),
                )
            enriched.append(enriched_doc)

        return enriched



    def _load_pdf(
        self,
        file_path: str,
        progress_callback: Optional[Callable] = None,
    ) -> List[Document]:
        filename = os.path.basename(file_path)

        # 1. OCR scanned PDFs
        if OCR_AVAILABLE and _ocr_pipeline is not None:
            try:
                if _ocr_pipeline.is_scanned(file_path):
                    logger.info("'%s' is scanned — routing to PaddleOCR.", filename)
                    return self._run_ocr(file_path, progress_callback)
            except Exception as scan_exc:
                logger.warning(
                    "Scan-detection failed for '%s' (%s) — assuming digital.",
                    filename, scan_exc,
                )

        # 2. Extract rich text from digital PDFs
        if DOCLING_AVAILABLE and parse_with_docling is not None:
            try:
                docs = parse_with_docling(file_path)
                total_text = " ".join(d.page_content for d in docs).strip()
                if len(total_text) < 100:
                    raise RuntimeError(
                        f"Docling extracted only {len(total_text)} characters — "
                        "content appears empty; trying fallback."
                    )
                return docs
            except Exception as docling_exc:
                logger.warning(
                    "Docling failed for '%s' (%s) — falling back to PyMuPDFLoader.",
                    filename, docling_exc,
                )

        # 3. Fallback to basic text extraction
        logger.info("'%s' — using PyMuPDFLoader (fallback).", filename)
        docs = _make_pymupdf_documents(file_path)

        # Last-resort OCR if PyMuPDF also returns near-empty content
        total_text = " ".join(d.page_content for d in docs).strip()
        if len(total_text) < 100 and OCR_AVAILABLE and _ocr_pipeline is not None:
            logger.info(
                "'%s' yielded only %d chars via PyMuPDF — attempting OCR fallback.",
                filename, len(total_text),
            )
            ocr_docs = self._run_ocr(file_path, progress_callback)
            if ocr_docs:
                return ocr_docs

        return docs



    def _load_docx(self, file_path: str) -> List[Document]:
        filename = os.path.basename(file_path)

        if DOCLING_AVAILABLE and parse_with_docling is not None:
            try:
                return parse_with_docling(file_path)
            except Exception as exc:
                logger.warning(
                    "Docling failed for DOCX '%s' (%s) — falling back to Docx2txtLoader.",
                    filename, exc,
                )

        docs = Docx2txtLoader(file_path).load()
        for doc in docs:
            doc.metadata.setdefault("page_number",   1)
            doc.metadata.setdefault("section",       None)
            doc.metadata["parser_used"]   = "docx2txt"
            doc.metadata["is_ocr"]        = False
            doc.metadata["document_type"] = "docx"
        return docs



    def _load_pptx(self, file_path: str) -> List[Document]:
        filename = os.path.basename(file_path)

        if DOCLING_AVAILABLE and parse_with_docling is not None:
            try:
                return parse_with_docling(file_path)
            except Exception as exc:
                logger.warning(
                    "Docling failed for PPTX '%s' (%s) — falling back to basic extraction.",
                    filename, exc,
                )

        # Basic fallback: extract all text via PyMuPDF (treats PPTX as generic)
        # Most PPTX files won't be readable by PyMuPDF; we attempt a TextLoader
        # which at minimum avoids a hard crash.
        logger.warning(
            "'%s': Docling unavailable/failed for PPTX — attempting TextLoader fallback.",
            filename,
        )
        try:
            docs = TextLoader(file_path, encoding="utf-8").load()
        except Exception:
            docs = [Document(
                page_content="[PPTX parsing unavailable — install docling]",
                metadata={},
            )]
        for doc in docs:
            doc.metadata.setdefault("page_number",   1)
            doc.metadata.setdefault("section",       None)
            doc.metadata["parser_used"]   = "text_fallback"
            doc.metadata["is_ocr"]        = False
            doc.metadata["document_type"] = "pptx"
        return docs



    def _load_txt(self, file_path: str) -> List[Document]:
        docs = TextLoader(file_path, encoding="utf-8").load()
        for doc in docs:
            doc.metadata.setdefault("page_number",   1)
            doc.metadata.setdefault("section",       None)
            doc.metadata["parser_used"]   = "textloader"
            doc.metadata["is_ocr"]        = False
            doc.metadata["document_type"] = "txt"
        return docs



    def _run_ocr(
        self,
        file_path: str,
        progress_callback: Optional[Callable] = None,
    ) -> List[Document]:
        if not OCR_AVAILABLE or _ocr_pipeline is None:
            raise RuntimeError(
                "OCR is required for this file but PaddleOCR / PyMuPDF are not installed. "
                "Run: pip install paddlepaddle paddleocr PyMuPDF"
            )
        filename = os.path.basename(file_path)
        return _ocr_pipeline.process(file_path, filename, progress_callback)


ingestion_service = IngestionService()