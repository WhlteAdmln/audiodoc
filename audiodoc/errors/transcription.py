# Copyright (c) 2026 Nikolai Zelensky
"""Client-safe exceptions raised by audio transcription."""

from typing import ClassVar

from audiodoc.errors.base import AppError
from audiodoc.errors.messages import ERROR_MESSAGES


class InvalidAudioError(AppError):
    """The uploaded file is not decodable audio (HTTP 400)."""

    code: ClassVar[str] = "invalid_audio"
    status_code = 400
    public_message = ERROR_MESSAGES["invalid_audio"]


class AudioTooLongError(AppError):
    """The uploaded audio exceeds the configured duration (HTTP 400)."""

    code: ClassVar[str] = "audio_too_long"
    status_code = 400
    public_message = ERROR_MESSAGES["audio_too_long"]


class ModelNotReadyError(AppError):
    """The Whisper model has not completed initialization (HTTP 503)."""

    code: ClassVar[str] = "model_not_ready"
    status_code = 503
    public_message = ERROR_MESSAGES["model_not_ready"]


class TranscriptionTimeoutError(AppError):
    """Transcription exceeded its wall-clock deadline (HTTP 504)."""

    code: ClassVar[str] = "transcription_timeout"
    status_code = 504
    public_message = ERROR_MESSAGES["transcription_timeout"]
