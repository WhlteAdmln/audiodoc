# Copyright (c) 2026 Nikolai Zelensky
"""Client-safe exceptions raised while validating or extracting documents."""

from typing import ClassVar

from audiodoc.errors.base import AppError
from audiodoc.errors.messages import ERROR_MESSAGES


class DocumentRejectedError(AppError):
    """A document is malformed or cannot be processed (HTTP 400)."""

    code: ClassVar[str] = "document_rejected"
    status_code = 400
    public_message = ERROR_MESSAGES["document_rejected"]


class UnsupportedFormatError(DocumentRejectedError):
    """The Document Engine does not support the detected format."""

    code: ClassVar[str] = "unsupported_format"
    public_message = ERROR_MESSAGES["unsupported_format"]


class PayloadTooLargeError(AppError):
    """The uploaded payload exceeds the configured byte limit (HTTP 413)."""

    code: ClassVar[str] = "payload_too_large"
    status_code = 413
    public_message = ERROR_MESSAGES["payload_too_large"]


class ProcessingTimeoutError(AppError):
    """Document processing exceeded its allowed time (HTTP 504)."""

    code: ClassVar[str] = "processing_timeout"
    status_code = 504
    public_message = ERROR_MESSAGES["processing_timeout"]


class DependencyMissingError(AppError):
    """A required system executable or parser dependency is unavailable (HTTP 503)."""

    code: ClassVar[str] = "dependency_missing"
    status_code = 503
    public_message = ERROR_MESSAGES["dependency_missing"]
