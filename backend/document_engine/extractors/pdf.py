"""Extract PDF text within the budget and mark unprocessed pages as omitted."""

import logging
import math
from typing import Any, Protocol, cast

import pymupdf

from backend.common.deadline import Deadline
from backend.document_engine.extractors.base import (
    ExtractContext,
    add_chunk,
    make_context,
)
from backend.document_engine.limits import (
    MAX_DOCUMENT_PAGES,
    MAX_IMAGE_PIXELS,
    PDF_OCR_DPI,
    PDF_OCR_MIN_DPI,
)
from backend.document_engine.ocr import extract_image_text
from backend.errors.documents import DocumentRejectedError

logger = logging.getLogger(__name__)


class _InvalidPdfPageSizeError(DocumentRejectedError):
    """Raised when a PDF page has invalid dimensions."""

    public_message = "Размер страницы PDF некорректен"


class _PdfPageTooLargeError(DocumentRejectedError):
    """Raised when a PDF page exceeds the safe OCR pixel limit."""

    public_message = "Страница PDF слишком велика для безопасного OCR"


class _PdfTooManyPagesError(DocumentRejectedError):
    """Raised when a PDF document exceeds the page limit."""

    public_message = "\u0412 PDF слишком много страниц"


class _PageRect(Protocol):
    width: float
    height: float


class _PageWithRect(Protocol):
    rect: _PageRect


def _render_dpi(page: object) -> int:
    """Choose the highest OCR DPI whose rendered page stays under the pixel cap."""
    page_rect = cast("_PageWithRect", page).rect
    width_inches = float(page_rect.width) / 72.0
    height_inches = float(page_rect.height) / 72.0
    if (
        not math.isfinite(width_inches)
        or not math.isfinite(height_inches)
        or width_inches <= 0
        or height_inches <= 0
    ):
        raise _InvalidPdfPageSizeError

    dpi = min(
        PDF_OCR_DPI, int(math.sqrt(MAX_IMAGE_PIXELS / (width_inches * height_inches)))
    )
    while dpi >= PDF_OCR_MIN_DPI:
        pixels = math.ceil(width_inches * dpi) * math.ceil(height_inches * dpi)
        if pixels <= MAX_IMAGE_PIXELS:
            return dpi
        dpi -= 1
    raise _PdfPageTooLargeError


def extract_pdf(
    data: bytes,
    *,
    context: ExtractContext | None = None,
    deadline: Deadline | None = None,
) -> str:
    """Extract PDF text while bounding OCR resolution, pages, time, and output."""
    ctx = make_context(context, deadline=deadline)
    result: list[str] = []
    open_document = cast("Any", pymupdf.open)

    with open_document(stream=data, filetype="pdf") as document:
        if document.page_count > MAX_DOCUMENT_PAGES:
            raise _PdfTooManyPagesError

        for index, page in enumerate(document):
            ctx.check()
            text = page.get_text("text").strip()
            ctx.check()
            if not text:
                logger.info("PDF page %s has no text layer; starting OCR", index + 1)
                pixmap = None
                try:
                    ctx.check()
                    pixmap = page.get_pixmap(dpi=_render_dpi(page), alpha=False)
                    image_data = pixmap.tobytes("png")
                    text = extract_image_text(image_data, deadline=ctx.deadline).strip()
                finally:
                    if pixmap is not None:
                        del pixmap

            if text:
                add_chunk(
                    result,
                    ctx,
                    f"--- Страница {index + 1} ---\n{text}",
                    separator_length=2,
                )
            if ctx.budget.truncated:
                break
            if ctx.budget.exhausted:
                # Remaining pages are left unread rather than OCRed only to
                # discover whether they contain text beyond the client limit.
                if index + 1 < document.page_count:
                    ctx.budget.mark_truncated()
                break

    return "\n\n".join(result)
