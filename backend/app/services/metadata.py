# Standardises metadata for all documents before vector storage

import uuid
from typing import Optional, List, Dict
from langchain_core.documents import Document


class MetadataEnricher:

    def enrich(
        self,
        document: Document,
        file_id: int,
        filename: str,
        chunk_number: int,
        # Location in original document
        page_number: Optional[int] = None,
        timestamp_start: Optional[str] = None,
        timestamp_end: Optional[str] = None,
        # Source extraction details
        section: Optional[str] = None,
        parser_used: Optional[str] = None,
        is_ocr: Optional[bool] = None,
        document_type: Optional[str] = None,
        # Output quality metrics
        ocr_confidence: Optional[float] = None,
        language: str = "en",
    ) -> Document:
        # Standardise metadata for a single Document in-place
        meta = document.metadata  # mutate in place

        # Add core identifiers
        meta["document_id"]   = str(file_id)
        meta["filename"]      = filename
        meta["chunk_number"]  = chunk_number
        meta["embedding_id"]  = str(uuid.uuid4())
        meta["language"]      = language

        # Add positioning info
        meta["page_number"] = (
            page_number
            if page_number is not None
            else meta.get("page_number") or meta.get("page")
        )
        meta["timestamp_start"] = timestamp_start
        meta["timestamp_end"]   = timestamp_end

        # Add processing details
        meta["section"] = (
            section
            if section is not None
            else meta.get("section")
        )
        meta["parser_used"] = (
            parser_used
            if parser_used is not None
            else meta.get("parser_used", "unknown")
        )
        meta["is_ocr"] = (
            is_ocr
            if is_ocr is not None
            else meta.get("is_ocr", False)
        )
        meta["document_type"] = (
            document_type
            if document_type is not None
            else meta.get("document_type", "digital")
        )

        # Add extraction quality metrics
        meta["ocr_confidence"] = (
            ocr_confidence
            if ocr_confidence is not None
            else meta.get("ocr_confidence")
        )

        # Remove redundant keys
        meta.pop("page", None)  # replaced by page_number

        return document



    def extract_timestamps_from_segments(
        self,
        content: str,
        segments: List[Dict],
    ) -> tuple:
        if not segments:
            return None, None

        words = content.split()[:5]
        content_start = " ".join(words)

        for segment in segments:
            seg_text = segment.get("text", "")
            if content_start in seg_text or seg_text.startswith(content[:20]):
                return segment.get("start"), segment.get("end")

        return segments[0].get("start"), segments[-1].get("end")