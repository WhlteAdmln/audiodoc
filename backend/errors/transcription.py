"""Client-safe exceptions raised by audio transcription."""

from backend.errors.base import BackendError


class AudioTooLongError(BackendError):
    """The uploaded audio exceeds the configured duration (HTTP 400)."""

    status_code = 400
    public_message = "Аудио слишком длинное"


class ModelNotReadyError(BackendError):
    """The Whisper model has not completed initialization (HTTP 503)."""

    status_code = 503
    public_message = "Модель Whisper ещё не загружена"
