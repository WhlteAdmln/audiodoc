"""Render bounded DJVU page images and recognize them with OCR."""

import logging
from pathlib import Path

from backend.common.deadline import Deadline
from backend.common.subprocess_runner import (
    SubprocessOutputLimitError,
    SubprocessTimeoutError,
    run_limited,
)
from backend.document_engine.extractors.base import (
    ExtractContext,
    add_chunk,
    make_context,
)
from backend.document_engine.limits import (
    DJVU_RENDER_MAX_SIZE,
    MAX_DJVU_PAGE_BYTES,
    MAX_DOCUMENT_PAGES,
    SUBPROCESS_TIMEOUT,
)
from backend.document_engine.ocr import extract_image_text
from backend.errors.documents import DocumentRejectedError, ProcessingTimeoutError

logger = logging.getLogger(__name__)


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
        raise DocumentRejectedError(
            "Результат программы DjVuLibre слишком большой"
        ) from error
    except SubprocessTimeoutError as error:
        context.check()
        raise ProcessingTimeoutError("Превышено время обработки DJVU") from error


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
        raise DocumentRejectedError("Не удалось определить количество страниц DJVU")
    try:
        page_count = int(output.decode("utf-8", errors="replace").strip())
    except ValueError as error:
        raise DocumentRejectedError("Некорректное количество страниц DJVU") from error
    if page_count <= 0:
        raise DocumentRejectedError("В DJVU не найдено страниц")
    if page_count > MAX_DOCUMENT_PAGES:
        raise DocumentRejectedError("В DJVU слишком много страниц")
    return page_count


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

        image_path = temp_path / f"page_{page_number}.tiff"
        logger.info("Rendering DJVU page %s/%s for OCR", page_number, page_count)
        try:
            return_code, _stdout, stderr = _run_djvu_command(
                [
                    ddjvu,
                    "-format=tiff",
                    f"-page={page_number}",
                    f"-size={DJVU_RENDER_MAX_SIZE}x{DJVU_RENDER_MAX_SIZE}",
                    str(file_path),
                    str(image_path),
                ],
                ctx,
                max_output=4096,
            )
            if return_code != 0:
                logger.warning(
                    "ddjvu render failed for page %s: stderr=%r",
                    page_number,
                    stderr.decode("utf-8", errors="replace"),
                )
                raise DocumentRejectedError("Не удалось отобразить страницу DJVU")
            if not image_path.is_file():
                raise DocumentRejectedError("Не удалось отобразить страницу DJVU")

            page_size = image_path.stat().st_size
            if page_size > MAX_DJVU_PAGE_BYTES:
                raise DocumentRejectedError("Страница DJVU слишком велика для OCR")

            image_data = image_path.read_bytes()
            ctx.check()
            page_text = extract_image_text(image_data, deadline=ctx.deadline).strip()
            if page_text:
                add_chunk(
                    result,
                    ctx,
                    f"--- Страница {page_number} ---\n{page_text}",
                    separator_length=2,
                )
        finally:
            image_path.unlink(missing_ok=True)

        if ctx.budget.truncated:
            break
        if ctx.budget.exhausted:
            # Do not render and OCR more pages just to probe beyond the limit.
            if page_number < page_count:
                ctx.budget.mark_truncated()
            break

    return "\n\n".join(result)
