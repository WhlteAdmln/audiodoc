# Copyright (c) 2026 Nikolai Zelensky
"""Russian public messages displayed to application clients."""

ERROR_MESSAGES: dict[str, str] = {
    "internal_error": "Внутренняя ошибка сервиса",
    "server_busy": "Сервис занят. Повторите запрос позже",
    "document_rejected": "Документ не может быть обработан",
    "xml_forbidden_constructs": "XML содержит запрещённые конструкции",
    "malformed_xml_document": "Некорректный XML-документ",
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
    "empty_image": "Изображение пустое",
    "image_recognition_failed": "\u041d\u0435 удалось распознать страницу изображения",
    "image_too_large": "Изображение слишком большое: превышен лимит пикселей",
    "missing_fb2_body": "\u0412 FB2 не найдено содержимое книги",
    "invalid_document_archive": (
        "Документ содержит повреждённый или недопустимый архив"
    ),
    "document_extraction_failed": (
        "\u041d\u0435 удалось прочитать документ: файл повреждён или имеет "
        "неподдерживаемую структуру"
    ),
    "djvu_output_too_large": "Результат программы DjVuLibre слишком большой",
    "djvu_processing_timeout": "Превышено время обработки DJVU",
    "djvu_page_count_unavailable": (
        "\u041d\u0435 удалось определить количество страниц DJVU"
    ),
    "invalid_djvu_page_count": "Некорректное количество страниц DJVU",
    "djvu_no_pages": "\u0412 DJVU не найдено страниц",
    "djvu_too_many_pages": "\u0412 DJVU слишком много страниц",
    "djvu_page_render_failed": "\u041d\u0435 удалось отобразить страницу DJVU",
    "djvu_page_too_large": "Страница DJVU слишком велика для OCR",
    "djvu_text_too_large": "Текстовый слой DJVU слишком большой",
    "djvu_text_layer_timeout": "Превышено время извлечения текста DJVU",
    "djvu_text_layer_read_failed": "\u041d\u0435 удалось прочитать DJVU",
    "model_not_ready": "Модель Whisper ещё не загружена",
    "too_many_image_frames": "\u0412 изображении слишком много страниц",
    "transcription_timeout": "Превышено время обработки аудио",
    "unknown_image_format": "\u041d\u0435 удалось определить формат изображения",
    "unsupported_ocr_image_format": "Формат изображения не поддерживается для OCR",
    "invalid_pdf_page_size": "Размер страницы PDF некорректен",
    "pdf_page_too_large": "Страница PDF слишком велика для безопасного OCR",
    "pdf_too_many_pages": "\u0412 PDF слишком много страниц",
}

EXTRACTION_MESSAGES: dict[str, str] = {
    "odf_slide_label": "--- Слайд {index} ---",
    "pptx_slide_label": "--- Слайд {slide_number} ---",
    "odf_sheet_label": "--- Лист: {name} ---",
    "xlsx_sheet_label": "--- Лист: {name} ---",
    "ocr_page_label": "--- Страница {index} ---\n",
    "pdf_page_label": "--- Страница {index} ---\n",
    "djvu_page_label": "--- Страница {index} ---\n",
}
