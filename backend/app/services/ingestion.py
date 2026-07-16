
import os
import logging
from typing import List, Optional, Dict, Any

from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader,
    UnstructuredPowerPointLoader
)
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .metadata import MetadataEnricher
from ..config.settings import settings

logger = logging.getLogger(__name__)

try:
    from .ocr_pipeline import PDFOCRPipeline
    _ocr_pipeline = PDFOCRPipeline(
        dpi=settings.OCR_DPI,
        languages=settings.OCR_LANGUAGE.split(","),
        char_threshold=settings.OCR_SCANNED_CHAR_THRESHOLD,
        max_workers=settings.OCR_MAX_WORKERS or None,  
    )
    OCR_AVAILABLE = True
except ImportError as _ocr_import_err:
    OCR_AVAILABLE = False
    _ocr_pipeline = None
    logger.warning("OCR pipeline unavailable (%s). Scanned PDFs will not be processed.", _ocr_import_err)


class IngestionService:
    _metadata_enricher = MetadataEnricher()

    SUPPORTED_EXTENSIONS = {
        "video": [".mp4", ".mov", ".mkv", ".avi", ".webm"],
        "audio": [".mp3", ".wav", ".m4a", ".flac"],
        "document": [".pdf", ".docx", ".pptx", ".txt"]
    }

    def get_file_type(self, filename: str) -> Optional[str]:
        file_extension = os.path.splitext(filename)[1].lower()
        for file_type, extensions in self.SUPPORTED_EXTENSIONS.items():
            if file_extension in extensions:
                return file_type
        return None

    def _load_pdf(self, file_path: str, progress_callback: Optional[callable] = None) -> List[Document]:
        file_extension = ".pdf"

        is_scanned = False
        if OCR_AVAILABLE:
            try:
                is_scanned = _ocr_pipeline.is_scanned(file_path)
            except Exception as ocr_exception:
                logger.warning("PDF scan-detection failed, defaulting to digital loader: %s", ocr_exception)

        if is_scanned:
            logger.info("'%s' detected as scanned — routing to OCR pipeline", file_path)
            return self._run_ocr(file_path, progress_callback)

        documents = PyPDFLoader(file_path).load()

        for document in documents:
            document.metadata.setdefault("document_type", "digital")
            document.metadata.setdefault("ocr_confidence", None)
            document.metadata.setdefault("section", None)

        total_text = " ".join(document.page_content for document in documents).strip()
        if len(total_text) < 100 and OCR_AVAILABLE:
            logger.info(
                "PDF yielded only %d chars via PyPDFLoader — attempting OCR fallback",
                len(total_text)
            )
            ocr_extracted_documents = self._run_ocr(file_path, progress_callback)
            if ocr_extracted_documents:
                return ocr_extracted_documents

        return documents

    def _run_ocr(self, file_path: str, progress_callback: Optional[callable] = None) -> List[Document]:
        if not OCR_AVAILABLE:
            raise RuntimeError(
                "OCR is required for this file but PaddleOCR / PyMuPDF are not installed. "
                "Run: pip install paddleocr paddlepaddle PyMuPDF"
            )
        filename = os.path.basename(file_path)
        return _ocr_pipeline.process(file_path, filename, progress_callback)

    def load_document(self, file_path: str, file_type: str, progress_callback: Optional[callable] = None) -> List[Document]:

        file_extension = os.path.splitext(file_path)[1].lower()

        if file_extension == ".pdf":
            return self._load_pdf(file_path, progress_callback)
        elif file_extension == ".txt":
            return TextLoader(file_path, encoding="utf-8").load()
        elif file_extension == ".docx":
            return Docx2txtLoader(file_path).load()
        elif file_extension == ".pptx":
            return UnstructuredPowerPointLoader(file_path).load()
        elif file_type in ["video", "audio"]:
            return []
        else:
            raise ValueError(f"Unsupported file extension: {file_extension}")

    def load_transcript(self, transcript_path: str) -> List[Document]:
        return TextLoader(transcript_path, encoding="utf-8").load()

    def split_documents(
        self,
        documents: List[Document],
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> List[Document]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            add_start_index=True
        )
        return splitter.split_documents(documents)

    def process_document(
        self,
        file_path: str,
        file_id: int,
        filename: str,
        file_type: str,
        transcript_path: Optional[str] = None,
        segment_timestamps: Optional[List[Dict]] = None,
        progress_callback: Optional[callable] = None
    ) -> List[Document]:

        if file_type in ["video", "audio"]:
            documents = self.load_transcript(transcript_path)
            for document in documents:
                document.metadata["source_type"] = file_type
                document.metadata["filename"] = filename
        else:
            documents = self.load_document(file_path, file_type, progress_callback)
            for document in documents:
                document.metadata["source_type"] = file_type
                document.metadata["filename"] = filename

        split_documents = self.split_documents(documents)

        enriched_documents = []
        for i, document in enumerate(split_documents):
            if file_type in ["video", "audio"] and segment_timestamps:
                timestamp_start, timestamp_end = self._metadata_enricher.extract_timestamps_from_segments(
                    document.page_content, segment_timestamps
                )
                enriched_document = self._metadata_enricher.enrich(
                    document, file_id, filename, i,
                    timestamp_start=timestamp_start,
                    timestamp_end=timestamp_end,
                    document_type=document.metadata.get("document_type"),
                    ocr_confidence=document.metadata.get("ocr_confidence"),
                )
            else:
                enriched_document = self._metadata_enricher.enrich(
                    document, file_id, filename, i,
                    document_type=document.metadata.get("document_type"),
                    ocr_confidence=document.metadata.get("ocr_confidence"),
                )
            enriched_documents.append(enriched_document)

        return enriched_documents


ingestion_service = IngestionService()