# Copyright (c) 2026 Nikolai Zelensky
"""Read the embedded DJVU text layer with bounded subprocess output."""

import logging
from pathlib import Path

from audiodoc.common.deadline import Deadline
from audiodoc.common.subprocess_runner import (
    SubprocessOutputLimitError,
    SubprocessTimeoutError,
    run_limited,
)
from audiodoc.document_engine.extractors.base import ExtractContext, make_context
from audiodoc.document_engine.limits import (
    MAX_EXTRACTED_TEXT_LENGTH,
    SUBPROCESS_TIMEOUT,
)
from audiodoc.errors.documents import DocumentRejectedError, ProcessingTimeoutError
from audiodoc.errors.messages import ERROR_MESSAGES

logger = logging.getLogger(__name__)


class _DjvuTextTooLargeError(DocumentRejectedError):
    """Raised when the embedded DjVu text layer exceeds its size limit."""

    public_message = ERROR_MESSAGES["djvu_text_too_large"]


class _DjvuTextLayerTimeoutError(ProcessingTimeoutError):
    """Raised when extracting the DjVu text layer exceeds its deadline."""

    public_message = ERROR_MESSAGES["djvu_text_layer_timeout"]


class _DjvuTextLayerReadError(DocumentRejectedError):
    """Raised when the embedded DjVu text layer cannot be read."""

    public_message = ERROR_MESSAGES["djvu_text_layer_read_failed"]


def extract_text_layer(
    file_path: Path,
    executable: str,
    *,
    context: ExtractContext | None = None,
    deadline: Deadline | None = None,
) -> str:
    """Run ``djvutxt`` with a byte cap derived from the maximum text size."""
    ctx = make_context(context, deadline=deadline)
    ctx.check()
    remaining = ctx.deadline.remaining()
    if remaining <= 0:
        ctx.check()
    try:
        return_code, output, stderr = run_limited(
            [executable, str(file_path)],
            timeout=min(SUBPROCESS_TIMEOUT, max(remaining, 0.001)),
            max_output=MAX_EXTRACTED_TEXT_LENGTH * 4,
        )
    except SubprocessOutputLimitError as error:
        raise _DjvuTextTooLargeError from error
    except SubprocessTimeoutError as error:
        ctx.check()
        raise _DjvuTextLayerTimeoutError from error

    if return_code != 0:
        logger.warning(
            "djvutxt failed: stderr=%r", stderr.decode("utf-8", errors="replace")
        )
        raise _DjvuTextLayerReadError
    ctx.check()
    return output.decode("utf-8", errors="replace").strip()
