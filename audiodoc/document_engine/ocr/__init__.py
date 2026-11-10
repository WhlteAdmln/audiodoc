# Copyright (c) 2026 Nikolai Zelensky
"""OCR helpers built on Pillow and Tesseract."""

import io
import logging

from PIL import Image, UnidentifiedImageError

from audiodoc.common.deadline import Deadline
from audiodoc.document_engine.ocr.preprocessing import SUPPORTED_IMAGE_FORMATS
from audiodoc.document_engine.ocr.recognize import recognize_pages
from audiodoc.document_engine.ocr.tesseract import DEFAULT_OCR_LANGUAGES, ensure_ready
from audiodoc.errors.documents import DocumentRejectedError
from audiodoc.errors.messages import ERROR_MESSAGES

logger = logging.getLogger(__name__)


class _EmptyImageError(DocumentRejectedError):
    """Raised when OCR receives empty image data."""

    public_message = ERROR_MESSAGES["empty_image"]


class _UnknownImageFormatError(DocumentRejectedError):
    """Raised when the image format cannot be identified."""

    public_message = ERROR_MESSAGES["unknown_image_format"]


class _UnsupportedOcrImageFormatError(DocumentRejectedError):
    """Raised when an image format is unsupported by OCR."""

    public_message = ERROR_MESSAGES["unsupported_ocr_image_format"]


def extract_image_text(
    data: bytes,
    languages: str = DEFAULT_OCR_LANGUAGES,
    *,
    deadline: Deadline | None = None,
) -> str:
    """Recognize text from an image after cached dependency and format checks."""
    if deadline is not None:
        deadline.check()
    if not data:
        raise _EmptyImageError

    ensure_ready(languages)
    try:
        image = Image.open(io.BytesIO(data))
    except UnidentifiedImageError as error:
        raise _UnknownImageFormatError from error

    with image:
        if image.format not in SUPPORTED_IMAGE_FORMATS:
            raise _UnsupportedOcrImageFormatError
        return recognize_pages(image, languages, deadline=deadline)


__all__ = ["DEFAULT_OCR_LANGUAGES", "extract_image_text"]
