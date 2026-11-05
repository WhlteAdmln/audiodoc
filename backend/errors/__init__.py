"""Typed application errors with safe client-facing messages."""

from backend.errors.base import BackendError, ServerBusyError
from backend.errors.documents import (
    DependencyMissingError,
    DocumentRejectedError,
    PayloadTooLargeError,
    ProcessingTimeoutError,
    UnsupportedFormatError,
)
from backend.errors.transcription import AudioTooLongError, ModelNotReadyError

__all__ = [
    "BackendError",
    "ServerBusyError",
    "DocumentRejectedError",
    "UnsupportedFormatError",
    "PayloadTooLargeError",
    "ProcessingTimeoutError",
    "DependencyMissingError",
    "AudioTooLongError",
    "ModelNotReadyError",
]
