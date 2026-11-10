# Copyright (c) 2026 Nikolai Zelensky
"""Typed application errors with safe client-facing messages."""

from backend.errors.base import AppError, BackendError, ServerBusyError
from backend.errors.documents import (
    DependencyMissingError,
    DocumentRejectedError,
    PayloadTooLargeError,
    ProcessingTimeoutError,
    UnsupportedFormatError,
)
from backend.errors.transcription import (
    AudioTooLongError,
    InvalidAudioError,
    ModelNotReadyError,
    TranscriptionTimeoutError,
)

__all__ = [
    "AppError",
    "AudioTooLongError",
    "BackendError",
    "DependencyMissingError",
    "DocumentRejectedError",
    "InvalidAudioError",
    "ModelNotReadyError",
    "PayloadTooLargeError",
    "ProcessingTimeoutError",
    "ServerBusyError",
    "TranscriptionTimeoutError",
    "UnsupportedFormatError",
]
