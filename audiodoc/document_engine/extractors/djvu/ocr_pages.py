# Copyright (c) 2026 Nikolai Zelensky
"""Render bounded DJVU page images and recognize them with OCR."""

import logging
from pathlib import Path

from audiodoc.common.deadline import Deadline
from audiodoc.common.subprocess_runner import (
    SubprocessOutputLimitError,
    SubprocessTimeoutError,
    run_limited,
)
from audiodoc.document_engine.extractors.base import (
    ExtractContext,
    add_chunk,
    make_context,
)
from audiodoc.document_engine.limits import (
    DJVU_RENDER_MAX_SIZE,
    MAX_DJVU_PAGE_BYTES,
    MAX_DOCUMENT_PAGES,
    SUBPROCESS_TIMEOUT,
)
from audiodoc.document_engine.ocr import extract_image_text
from audiodoc.errors.documents import DocumentRejectedError, ProcessingTimeoutError
from audiodoc.errors.messages import ERROR_MESSAGES, EXTRACTION_MESSAGES

logger = logging.getLogger(__name__)


class _DjvuOutputTooLargeError(DocumentRejectedError):
    """Raised when a DjVuLibre command produces excessive output."""

    public_message = ERROR_MESSAGES["djvu_output_too_large"]


class _DjvuProcessingTimeoutError(ProcessingTimeoutError):
    """Raised when a DjVuLibre command exceeds its processing deadline."""

    public_message = ERROR_MESSAGES["djvu_processing_timeout"]


class _DjvuPageCountUnavailableError(DocumentRejectedError):
    """Raised when the DjVu page count cannot be determined."""

    public_message = ERROR_MESSAGES["djvu_page_count_unavailable"]


class _InvalidDjvuPageCountError(DocumentRejectedError):
    """Raised when the DjVu page count is malformed."""

    public_message = ERROR_MESSAGES["invalid_djvu_page_count"]


class _DjvuNoPagesError(DocumentRejectedError):
    """Raised when a DjVu document contains no pages."""

    public_message = ERROR_MESSAGES["djvu_no_pages"]


class _DjvuTooManyPagesError(DocumentRejectedError):
    """Raised when a DjVu document exceeds the page limit."""

    public_message = ERROR_MESSAGES["djvu_too_many_pages"]


class _DjvuPageRenderError(DocumentRejectedError):
    """Raised when a DjVu page cannot be rendered."""

    public_message = ERROR_MESSAGES["djvu_page_render_failed"]


class _DjvuPageTooLargeError(DocumentRejectedError):
    """Raised when a rendered DjVu page exceeds the OCR size limit."""

    public_message = ERROR_MESSAGES["djvu_page_too_large"]


def _run_djvu_command(
    args: list[str],
    context: ExtractContext,
    *,
    max_output: int = 4096,
) -> tuple[int, bytes, bytes]:
    """Run one DjVuLibre command under both the process and document deadlines."""
    context.check()
    remaining = context.deadline.remaining()
    if remaining <= 0:
        context.check()
    try:
        return run_limited(
            args,
            timeout=min(SUBPROCESS_TIMEOUT, max(remaining, 0.001)),
            max_output=max_output,
        )
    except SubprocessOutputLimitError as error:
        raise _DjvuOutputTooLargeError from error
    except SubprocessTimeoutError as error:
        context.check()
        raise _DjvuProcessingTimeoutError from error


def _get_page_count(
    file_path: Path,
    djvused: str,
    *,
    context: ExtractContext | None = None,
    deadline: Deadline | None = None,
) -> int:
    """Read and validate DJVU page count using a tiny bounded output buffer."""
    ctx = make_context(context, deadline=deadline)
    return_code, output, stderr = _run_djvu_command(
        [djvused, str(file_path), "-e", "n"],
        ctx,
        max_output=1024,
    )
    if return_code != 0:
        logger.warning(
            "djvused page count failed: stderr=%r",
            stderr.decode("utf-8", errors="replace"),
        )
        raise _DjvuPageCountUnavailableError
    try:
        page_count = int(output.decode("utf-8", errors="replace").strip())
    except ValueError as error:
        raise _InvalidDjvuPageCountError from error
    if page_count <= 0:
        raise _DjvuNoPagesError
    if page_count > MAX_DOCUMENT_PAGES:
        raise _DjvuTooManyPagesError
    return page_count


def _render_page_image(
    file_path: Path,
    image_path: Path,
    ddjvu: str,
    page_number: int,
    context: ExtractContext,
) -> bytes:
    """Render one DJVU page to a bounded TIFF image and return its bytes."""
    return_code, _stdout, stderr = _run_djvu_command(
        [
            ddjvu,
            "-format=tiff",
            f"-page={page_number}",
            f"-size={DJVU_RENDER_MAX_SIZE}x{DJVU_RENDER_MAX_SIZE}",
            str(file_path),
            str(image_path),
        ],
        context,
        max_output=4096,
    )
    if return_code != 0:
        logger.warning(
            "ddjvu render failed for page %s: stderr=%r",
            page_number,
            stderr.decode("utf-8", errors="replace"),
        )
        raise _DjvuPageRenderError
    if not image_path.is_file():
        raise _DjvuPageRenderError
    if image_path.stat().st_size > MAX_DJVU_PAGE_BYTES:
        raise _DjvuPageTooLargeError
    return image_path.read_bytes()


def _ocr_page(
    file_path: Path,
    temp_path: Path,
    ddjvu: str,
    page_number: int,
    context: ExtractContext,
) -> str:
    """Render and recognize one DJVU page, always removing the temporary image."""
    image_path = temp_path / f"page_{page_number}.tiff"
    try:
        image_data = _render_page_image(
            file_path, image_path, ddjvu, page_number, context
        )
        context.check()
        return extract_image_text(image_data, deadline=context.deadline).strip()
    finally:
        image_path.unlink(missing_ok=True)


def extract_ocr_pages(
    file_path: Path,
    temp_path: Path,
    djvused: str,
    ddjvu: str,
    *,
    context: ExtractContext | None = None,
    deadline: Deadline | None = None,
) -> str:
    """Render DJVU pages within the budget and mark unprocessed pages as omitted."""
    ctx = make_context(context, deadline=deadline)
    page_count = _get_page_count(file_path, djvused, context=ctx)
    result: list[str] = []

    for page_number in range(1, page_count + 1):
        ctx.check()
        logger.info("Rendering DJVU page %s/%s for OCR", page_number, page_count)
        page_text = _ocr_page(file_path, temp_path, ddjvu, page_number, ctx)
        if page_text:
            add_chunk(
                result,
                ctx,
                EXTRACTION_MESSAGES["djvu_page_label"].format(index=page_number)
                + page_text,
                separator_length=2,
            )

        if ctx.budget.truncated:
            break
        if ctx.budget.exhausted:
            # Do not render and OCR more pages just to probe beyond the limit.
            if page_number < page_count:
                ctx.budget.mark_truncated()
            break

    return "\n\n".join(result)
