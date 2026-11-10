# Copyright (c) 2026 Nikolai Zelensky
"""Russian public messages displayed to application clients."""

ERROR_MESSAGES: dict[str, str] = {
    "internal_error": "Внутренняя ошибка сервиса",
    "server_busy": "Сервис занят. Повторите запрос позже",
    "document_rejected": "Документ не может быть обработан",
    "unsupported_format": "Формат не поддерживается Document Engine",
    "payload_too_large": "Файл слишком большой",
    "upload_too_large": "Файл слишком большой. Максимальный размер: {limit} МБ.",
    "processing_timeout": "Превышено время обработки",
    "dependency_missing": "\u041d\u0430 сервере не установлена нужная программа",
    "invalid_audio": "\u041d\u0435 удалось прочитать аудиофайл",
    "audio_too_long": "Аудио слишком длинное",
    "audio_too_long_with_limit": (
        "Аудио слишком длинное. Максимальная длительность: " + "{limit} \u0441."
    ),
    "invalid_text_limit": "Некорректный лимит длины текста",
    "empty_document": "Документ пуст",
    "invalid_document_archive": (
        "Документ содержит повреждённый или недопустимый архив"
    ),
    "document_extraction_failed": (
        "\u041d\u0435 удалось прочитать документ: файл повреждён или имеет "
        "неподдерживаемую структуру"
    ),
    "model_not_ready": "Модель Whisper ещё не загружена",
    "transcription_timeout": "Превышено время обработки аудио",
}

EXTRACTION_MESSAGES: dict[str, str] = {
    "odf_slide_label": "--- Слайд {index} ---",
    "odf_sheet_label": "--- Лист: {name} ---",
}
