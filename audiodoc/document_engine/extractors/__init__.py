# Copyright (c) 2026 Nikolai Zelensky
"""Registry of Document Engine extractors with a shared bounded context."""

from collections.abc import Callable

from audiodoc.common.deadline import Deadline
from audiodoc.document_engine.extractors.base import ExtractContext
from audiodoc.document_engine.extractors.csv_text import extract_csv
from audiodoc.document_engine.extractors.djvu import extract_djvu
from audiodoc.document_engine.extractors.docx import extract_docx
from audiodoc.document_engine.extractors.epub import extract_epub
from audiodoc.document_engine.extractors.fb2 import extract_fb2
from audiodoc.document_engine.extractors.html import extract_html
from audiodoc.document_engine.extractors.odf import extract_odf
from audiodoc.document_engine.extractors.pdf import extract_pdf
from audiodoc.document_engine.extractors.plain import extract_plain
from audiodoc.document_engine.extractors.pptx import extract_pptx
from audiodoc.document_engine.extractors.rtf import extract_rtf
from audiodoc.document_engine.extractors.xlsx import extract_xlsx
from audiodoc.document_engine.extractors.xml_text import extract_xml_text

Extractor = Callable[..., str]


def _odf(kind: str) -> Extractor:
    """Create an ODF adapter that binds the package's public file type."""

    def adapted(
        data: bytes,
        *,
        context: ExtractContext | None = None,
        deadline: Deadline | None = None,
    ) -> str:
        """Dispatch this adapted extractor to the selected ODF format."""
        return extract_odf(data, kind, context=context, deadline=deadline)

    return adapted


REGISTRY: dict[str, Extractor] = {
    "pdf": extract_pdf,
    "docx": extract_docx,
    "xlsx": extract_xlsx,
    "pptx": extract_pptx,
    "epub": extract_epub,
    "fb2": extract_fb2,
    "djvu": extract_djvu,
    "odt": _odf("odt"),
    "ods": _odf("ods"),
    "odp": _odf("odp"),
    "txt": extract_plain,
    "md": extract_plain,
    "csv": extract_csv,
    "html": extract_html,
    "xml": extract_xml_text,
    "rtf": extract_rtf,
}

__all__ = ["REGISTRY", "Extractor"]
