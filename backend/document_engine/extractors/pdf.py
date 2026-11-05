"""Extract text from PDF pages and OCR pages at a pixel-safe rendering DPI."""

import logging
import math

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


def _render_dpi(page: object) -> int:
    """Choose the highest OCR DPI whose rendered page stays under the pixel cap."""
    width_inches = float(page.rect.width) / 72.0
    height_inches = float(page.rect.height) / 72.0
    if (
        not math.isfinite(width_inches)
        or not math.isfinite(height_inches)
        or width_inches <= 0
        or height_inches <= 0
    ):
        raise DocumentRejectedError("Размер страницы PDF некорректен")

    dpi = min(
        PDF_OCR_DPI, int(math.sqrt(MAX_IMAGE_PIXELS / (width_inches * height_inches)))
    )
    while dpi >= PDF_OCR_MIN_DPI:
        pixels = math.ceil(width_inches * dpi) * math.ceil(height_inches * dpi)
        if pixels <= MAX_IMAGE_PIXELS:
            return dpi
        dpi -= 1
    raise DocumentRejectedError("Страница PDF слишком велика для безопасного OCR")


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
            raise DocumentRejectedError("В PDF слишком много страниц")

        for index, page in enumerate(document):
            ctx.check()
            if ctx.budget.exhausted:
                break

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
            if ctx.budget.exhausted:
                break

    return "\n\n".join(result)
