"""Определение формата документа по содержимому и расширению."""

from pathlib import Path

from backend.document_engine.detection.formats import (
    IMAGE_EXTENSIONS,
    SUPPORTED_FORMATS,
    extension_map,
)
from backend.document_engine.detection.signatures import (
    detect_djvu_signature,
    detect_ole_signature,
    detect_pdf_signature,
    detect_rtf_signature,
)
from backend.document_engine.detection.text_probe import looks_like_text
from backend.document_engine.detection.zip_formats import _detect_zip_format


def detect_format(
    data: bytes,
    filename: str | None = None,
) -> str | None:
    """Determine the document format.

    The detection order is preserved: image extension, PDF/DJVU/OLE signatures,
    ZIP, RTF, extension, and text-content detection.

    Standalone images are not processed; they are routed to the separate
    Vision Engine.
    """
    if not data:
        return None

    file_extension = Path(filename or "").suffix.lower()

    # Изображения обрабатываются отдельным Vision Engine.
    if file_extension in IMAGE_EXTENSIONS:
        return None

    detected = detect_pdf_signature(data)
    if detected:
        return detected

    detected = detect_djvu_signature(data)
    if detected:
        return detected

    detected = detect_ole_signature(data, file_extension)
    if detected:
        return detected

    # ZIP-контейнеры: DOCX, XLSX, PPTX, EPUB, ODT и другие.
    if data.startswith(b"PK"):
        detected = _detect_zip_format(data)
        if detected:
            return detected

    detected = detect_rtf_signature(data)
    if detected:
        return detected

    # Текстовые форматы: проверяем расширение.
    extension = file_extension.lstrip(".")
    if extension in extension_map:
        return extension_map[extension]

    # Проверка, похоже ли содержимое на текст.
    if looks_like_text(data):
        return "txt"

    return None


__all__ = [
    "IMAGE_EXTENSIONS",
    "SUPPORTED_FORMATS",
    "detect_format",
]
