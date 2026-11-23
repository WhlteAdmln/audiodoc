# Copyright (c) 2026 Nikolai Zelensky
"""Extract PDF text within the budget and mark unprocessed pages as omitted."""

import logging
import math

import pymupdf

from audiodoc.common.deadline import Deadline
from audiodoc.document_engine.extractors.base import (
    ExtractContext,
    add_chunk,
    make_context,
)
from audiodoc.document_engine.limits import (
    MAX_DOCUMENT_PAGES,
    MAX_IMAGE_PIXELS,
    PDF_OCR_DPI,
    PDF_OCR_MIN_DPI,
)
from audiodoc.document_engine.ocr import extract_image_text
from audiodoc.errors.documents import DocumentRejectedError
from audiodoc.errors.messages import ERROR_MESSAGES, EXTRACTION_MESSAGES

logger = logging.getLogger(__name__)


class _InvalidPdfPageSizeError(DocumentRejectedError):
    """Raised when a PDF page has invalid dimensions."""

    public_message = ERROR_MESSAGES["invalid_pdf_page_size"]


class _PdfPageTooLargeError(DocumentRejectedError):
    """Raised when a PDF page exceeds the safe OCR pixel limit."""

    public_message = ERROR_MESSAGES["pdf_page_too_large"]


class _PdfTooManyPagesError(DocumentRejectedError):
    """Raised when a PDF document exceeds the page limit."""

    public_message = ERROR_MESSAGES["pdf_too_many_pages"]


def _render_dpi(page: pymupdf.Page) -> int:
    """Choose the highest OCR DPI whose rendered page stays under the pixel cap."""
    page_rect = page.rect
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


def _render_page_png(page: pymupdf.Page) -> bytes:
    """Render a page without alpha at the capped OCR DPI as PNG bytes."""
    pixmap = page.get_pixmap(dpi=_render_dpi(page), alpha=False)
    return pixmap.tobytes("png")


def extract_pdf(
    data: bytes,
    *,
    context: ExtractContext | None = None,
    deadline: Deadline | None = None,
) -> str:
    """Extract PDF text while bounding OCR resolution, pages, time, and output."""
    ctx = make_context(context, deadline=deadline)
    result: list[str] = []

    with pymupdf.open(stream=data, filetype="pdf") as document:
        if document.page_count > MAX_DOCUMENT_PAGES:
            raise _PdfTooManyPagesError

        for index, page in enumerate(document):
            ctx.check()
            text = page.get_text("text").strip()
            ctx.check()
            if not text:
                logger.info("PDF page %s has no text layer; starting OCR", index + 1)
                ctx.check()
                image_data = _render_page_png(page)
                text = extract_image_text(image_data, deadline=ctx.deadline).strip()

            if text:
                add_chunk(
                    result,
                    ctx,
                    (
                        EXTRACTION_MESSAGES["pdf_page_label"].format(index=index + 1)
                        + text
                    ),
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
