# Copyright (c) 2026 Nikolai Zelensky
"""Registry of Document Engine extractors with a shared bounded context."""

from collections.abc import Callable

from backend.common.deadline import Deadline
from backend.document_engine.extractors.base import ExtractContext
from backend.document_engine.extractors.csv_text import extract_csv
from backend.document_engine.extractors.djvu import extract_djvu
from backend.document_engine.extractors.docx import extract_docx
from backend.document_engine.extractors.epub import extract_epub
from backend.document_engine.extractors.fb2 import extract_fb2
from backend.document_engine.extractors.html import extract_html
from backend.document_engine.extractors.odf import extract_odf
from backend.document_engine.extractors.pdf import extract_pdf
from backend.document_engine.extractors.plain import extract_plain
from backend.document_engine.extractors.pptx import extract_pptx
from backend.document_engine.extractors.rtf import extract_rtf
from backend.document_engine.extractors.xlsx import extract_xlsx
from backend.document_engine.extractors.xml_text import extract_xml_text

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
