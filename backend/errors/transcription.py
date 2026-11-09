# Copyright (c) 2026 Nikolai Zelensky
"""Client-safe exceptions raised by audio transcription."""

from backend.errors.base import BackendError


class InvalidAudioError(BackendError):
    """The uploaded file is not decodable audio (HTTP 400)."""

    status_code = 400
    public_message = (
        "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c "
        "\u043f\u0440\u043e\u0447\u0438\u0442\u0430\u0442\u044c "
        "\u0430\u0443\u0434\u0438\u043e\u0444\u0430\u0439\u043b"
    )


class AudioTooLongError(BackendError):
    """The uploaded audio exceeds the configured duration (HTTP 400)."""

    status_code = 400
    public_message = "Аудио слишком длинное"


class ModelNotReadyError(BackendError):
    """The Whisper model has not completed initialization (HTTP 503)."""

    status_code = 503
    public_message = "Модель Whisper ещё не загружена"


class TranscriptionTimeoutError(BackendError):
    """Transcription exceeded its wall-clock deadline (HTTP 504)."""

    status_code = 504
    public_message = "Превышено время обработки аудио"
