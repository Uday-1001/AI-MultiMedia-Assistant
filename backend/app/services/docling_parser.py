# Parse documents like PDFs and Word files into Markdown with LangChain support

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# Supported formats this parser handles natively
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx"}


def _build_docling_converter():
    # Lazily build the document converter to avoid early ImportErrors
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions

    pipeline_options = PdfPipelineOptions(
        do_ocr=False,           # OCR handled by our dedicated PaddleOCR pipeline
        do_table_structure=True,
        generate_page_images=False,
    )

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        }
    )
    return converter


def _extract_heading(markdown_text: str) -> Optional[str]:
    # Extract the first heading from markdown
    for line in markdown_text.splitlines():
        stripped = line.lstrip("#").strip()
        if line.startswith("#") and stripped:
            return stripped
    return None


def parse_with_docling(file_path: str) -> List[Document]:
    # Break down the document page by page and extract text with metadata
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"DoclingParser does not support '{ext}'. "
            f"Supported: {SUPPORTED_EXTENSIONS}"
        )

    document_type_map = {
        ".pdf":  "pdf_digital",
        ".docx": "docx",
        ".pptx": "pptx",
    }
    document_type = document_type_map[ext]

    logger.info("Docling: parsing '%s' (%s)", path.name, ext)

    try:
        converter = _build_docling_converter()
        result = converter.convert(file_path)
    except ImportError:
        raise
    except Exception as exc:
        raise RuntimeError(
            f"Docling failed to parse '{path.name}': {exc}"
        ) from exc

    # Try exporting page by page for better metadata
    documents: List[Document] = []

    try:
        # Attempt page-level export for richer page_number metadata
        pages = list(result.document.pages.values()) if hasattr(result.document, "pages") else []
    except Exception:
        pages = []

    if pages:
        for page in pages:
            try:
                # Collect all text elements belonging to this page
                page_chunks = []
                for item, _ in result.document.iterate_items():
                    item_prov = getattr(item, "prov", [])
                    if any(getattr(p, "page_no", None) == page.page_no for p in item_prov):
                        if hasattr(item, "export_to_markdown"):
                            chunk = item.export_to_markdown() # type: ignore
                        elif hasattr(item, "text"):
                            chunk = item.text # type: ignore
                        else:
                            continue
                        if chunk and chunk.strip():
                            page_chunks.append(chunk.strip())

                page_text = "\n\n".join(page_chunks)
                if not page_text.strip():
                    continue

                documents.append(Document(
                    page_content=page_text,
                    metadata={
                        "source":        file_path,
                        "page_number":   page.page_no,
                        "section":       _extract_heading(page_text),
                        "parser_used":   "docling",
                        "is_ocr":        False,
                        "document_type": document_type,
                    }
                ))
            except Exception as page_exc:
                logger.warning(
                    "Docling: skipped page %s of '%s': %s",
                    getattr(page, "page_no", "?"), path.name, page_exc,
                )

    # Fallback if page-level export fails
    if not documents:
        logger.debug(
            "Docling: page-level extraction yielded nothing for '%s' — "
            "falling back to full-document export.", path.name
        )
        try:
            full_markdown = result.document.export_to_markdown()
        except Exception as md_exc:
            raise RuntimeError(
                f"Docling markdown export failed for '{path.name}': {md_exc}"
            ) from md_exc

        if not full_markdown.strip():
            raise RuntimeError(
                f"Docling extracted empty content from '{path.name}'."
            )

        documents.append(Document(
            page_content=full_markdown,
            metadata={
                "source":        file_path,
                "page_number":   1,
                "section":       _extract_heading(full_markdown),
                "parser_used":   "docling",
                "is_ocr":        False,
                "document_type": document_type,
            }
        ))

    logger.info(
        "Docling: produced %d document(s) from '%s'.", len(documents), path.name
    )
    return documents
