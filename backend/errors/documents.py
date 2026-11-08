# Copyright (c) 2026 Nikolai Zelensky
"""Client-safe exceptions raised while validating or extracting documents."""

from backend.errors.base import BackendError


class DocumentRejectedError(BackendError):
    """A document is malformed or cannot be processed (HTTP 400)."""

    status_code = 400
    public_message = "Документ не может быть обработан"


class UnsupportedFormatError(DocumentRejectedError):
    """The Document Engine does not support the detected format."""

    public_message = "Формат не поддерживается Document Engine"


class PayloadTooLargeError(BackendError):
    """The uploaded payload exceeds the configured byte limit (HTTP 413)."""

    status_code = 413
    public_message = "Файл слишком большой"


class ProcessingTimeoutError(BackendError):
    """Document processing exceeded its allowed time (HTTP 504)."""

    status_code = 504
    public_message = "Превышено время обработки"


class DependencyMissingError(BackendError):
    """A required system executable or parser dependency is unavailable (HTTP 503)."""

    status_code = 503
    public_message = "\u041d\u0430 сервере не установлена нужная программа"
