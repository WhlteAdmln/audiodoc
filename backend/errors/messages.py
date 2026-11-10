# Copyright (c) 2026 Nikolai Zelensky
"""Russian public messages for application errors."""

ERROR_MESSAGES: dict[str, str] = {
    "internal_error": "Внутренняя ошибка сервиса",
    "server_busy": "Сервис занят. Повторите запрос позже",
    "document_rejected": "Документ не может быть обработан",
    "unsupported_format": "Формат не поддерживается Document Engine",
    "payload_too_large": "Файл слишком большой",
    "processing_timeout": "Превышено время обработки",
    "dependency_missing": "\u041d\u0430 сервере не установлена нужная программа",
    "invalid_audio": "\u041d\u0435 удалось прочитать аудиофайл",
    "audio_too_long": "Аудио слишком длинное",
    "model_not_ready": "Модель Whisper ещё не загружена",
    "transcription_timeout": "Превышено время обработки аудио",
}
