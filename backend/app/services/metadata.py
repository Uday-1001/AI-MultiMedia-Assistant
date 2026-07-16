import os
import uuid
from typing import Optional, List, Dict
from langchain_core.documents import Document


class MetadataEnricher:
    """
    Adds useful context (metadata) to document chunks before they are saved to the database.
    This helps the AI know exactly where a piece of information came from.
    """
    def enrich(
        self,
        document: Document,
        file_id: int,
        filename: str,
        chunk_number: int,
        page_number: Optional[int] = None,
        timestamp_start: Optional[str] = None,
        timestamp_end: Optional[str] = None,
        language: str = "en",
        document_type: Optional[str] = None,
        ocr_confidence: Optional[float] = None,
    ) -> Document:
        document.metadata["document_id"] = str(file_id)
        document.metadata["filename"] = filename
        document.metadata["chunk_number"] = chunk_number
        document.metadata["page_number"] = page_number or document.metadata.get("page")
        document.metadata["timestamp_start"] = timestamp_start
        document.metadata["timestamp_end"] = timestamp_end
        document.metadata["language"] = language
        document.metadata["embedding_id"] = str(uuid.uuid4())

        # OCR-specific fields — present for scanned docs, None for digital
        document.metadata["document_type"] = document_type or document.metadata.get("document_type", "digital")
        document.metadata["ocr_confidence"] = ocr_confidence if ocr_confidence is not None else document.metadata.get("ocr_confidence")

        return document

    def extract_timestamps_from_segments(
        self,
        content: str,
        segments: List[Dict]
    ) -> tuple:
        if not segments:
            return None, None

        words = content.split()[:5]
        content_start = " ".join(words)

        for segment in segments:
            if content_start in segment["text"] or segment["text"].startswith(content[:20]):
                return segment.get("start"), segment.get("end")

        return segments[0].get("start"), segments[-1].get("end")