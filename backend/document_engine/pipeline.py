"""Synchronous document validation and bounded extraction pipeline."""

import logging

from backend.common.deadline import Deadline, DeadlineExceededError
from backend.common.text_budget import TextBudget
from backend.document_engine.detection import detect_format
from backend.document_engine.extractors import REGISTRY
from backend.document_engine.extractors.base import ExtractContext
from backend.document_engine.guards.zip_archive import validate_zip_archive
from backend.document_engine.limits import (
    DOCUMENT_PROCESSING_TIMEOUT,
    MAX_DOCUMENT_SIZE,
    MAX_EXTRACTED_TEXT_LENGTH,
)
from backend.document_engine.result import DocumentResult, build_result
from backend.errors.base import BackendError
from backend.errors.documents import (
    DocumentRejectedError,
    PayloadTooLargeError,
    ProcessingTimeoutError,
    UnsupportedFormatError,
)

logger = logging.getLogger(__name__)

ZIP_FORMATS = {"docx", "xlsx", "pptx", "epub", "odt", "ods", "odp"}


def process_document_sync(
    data: bytes,
    filename: str,
    max_characters: int | None = None,
    deadline: Deadline | None = None,
) -> DocumentResult:
    """Validate a document, extract within a shared budget, and create its result.

    Args:
        data: Complete document bytes.
        filename: Client-supplied filename, used only for format detection.
        max_characters: Optional client hint; can only lower the server limit.
        deadline: Optional shared wall-clock deadline for this operation.

    Returns:
        A dictionary with ``format``, ``text``, ``characters``, and ``truncated``.

    Raises:
        BackendError: For invalid, unsupported, oversized, or timed-out documents.

    """
    limit = _get_text_limit(max_characters)
    operation_deadline = deadline or Deadline(DOCUMENT_PROCESSING_TIMEOUT)
    context = ExtractContext(
        budget=TextBudget(limit),
        deadline=operation_deadline,
        filename=filename,
    )

    try:
        _validate_document_input(data, context)
        filetype = detect_format(data, filename)
        if filetype is None:
            raise UnsupportedFormatError

        context.check()
        _validate_zip_document(data, filetype)
        context.check()

        text = _extract_document_text(data, filetype, context)
        context.check()
        return build_result(filetype, text, truncated=context.budget.truncated)

    except DeadlineExceededError as error:
        raise ProcessingTimeoutError from error


def _get_text_limit(max_characters: int | None) -> int:
    if max_characters is not None:
        if (
            isinstance(max_characters, bool)
            or not _is_integer(max_characters)
            or not 1 <= max_characters <= MAX_EXTRACTED_TEXT_LENGTH
        ):
            raise DocumentRejectedError("Некорректный лимит длины текста")
        return min(MAX_EXTRACTED_TEXT_LENGTH, max_characters)
    return MAX_EXTRACTED_TEXT_LENGTH


def _validate_document_input(data: bytes, context: ExtractContext) -> None:
    context.check()
    if not data:
        raise DocumentRejectedError("Документ пуст")
    if len(data) > MAX_DOCUMENT_SIZE:
        raise PayloadTooLargeError


def _validate_zip_document(data: bytes, filetype: str) -> None:
    if filetype in ZIP_FORMATS:
        try:
            validate_zip_archive(data)
        except ValueError as error:
            raise DocumentRejectedError(
                "Документ содержит повреждённый или недопустимый архив"
            ) from error


def _extract_document_text(
    data: bytes,
    filetype: str,
    context: ExtractContext,
) -> str:
    extractor = REGISTRY.get(filetype)
    if extractor is None:
        raise UnsupportedFormatError

    try:
        return extractor(data, context=context)
    except BackendError:
        raise
    except Exception as error:
        logger.exception("Document extractor failed: format=%s", filetype)
        raise DocumentRejectedError(
            "\u041d\u0435 удалось прочитать документ: файл повреждён или имеет "
            "неподдерживаемую структуру"
        ) from error


def _is_integer(value: object) -> bool:
    return isinstance(value, int)
