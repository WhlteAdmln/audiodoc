"""Base exception contract used to map safe backend errors to HTTP responses."""

from typing import ClassVar


class BackendError(Exception):
    """Base backend error whose public message is safe to return to clients."""

    status_code = 500
    public_message = "Внутренняя ошибка сервиса"
    headers: ClassVar[dict[str, str]] = {}

    def __init__(self, message: str | None = None) -> None:
        """Initialize with an optional safe message, otherwise use the class default."""
        self.public_message = message or self.public_message
        super().__init__(self.public_message)


class ServerBusyError(BackendError):
    """The bounded work queue is full (HTTP 503 with a retry hint)."""

    status_code = 503
    public_message = "Сервис занят. Повторите запрос позже"
    headers: ClassVar[dict[str, str]] = {"Retry-After": "30"}
