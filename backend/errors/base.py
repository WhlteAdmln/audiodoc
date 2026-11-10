# Copyright (c) 2026 Nikolai Zelensky
"""Base exception contract used to map safe backend errors to HTTP responses."""

from typing import ClassVar, TypeAlias

from backend.errors.messages import ERROR_MESSAGES


class AppError(Exception):
    """Base application error with a safe public message and machine-readable code."""

    code: ClassVar[str] = "internal_error"
    status_code = 500
    public_message = ERROR_MESSAGES["internal_error"]
    headers: ClassVar[dict[str, str]] = {}

    def __init__(self, message: str | None = None) -> None:
        """Initialize with an optional safe message, otherwise use the class default."""
        self.public_message = message or self.public_message
        super().__init__(self.public_message)


BackendError: TypeAlias = AppError


class ServerBusyError(AppError):
    """The bounded work queue is full (HTTP 503 with a retry hint)."""

    code: ClassVar[str] = "server_busy"
    status_code = 503
    public_message = ERROR_MESSAGES["server_busy"]
    headers: ClassVar[dict[str, str]] = {"Retry-After": "30"}
