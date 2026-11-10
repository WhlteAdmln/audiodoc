# Copyright (c) 2026 Nikolai Zelensky
"""Recognize image frames using Tesseract after checking pixel dimensions."""

from PIL import Image

from backend.common.deadline import Deadline
from backend.document_engine.limits import (
    MAX_DOCUMENT_PAGES,
    MAX_EXTRACTED_TEXT_LENGTH,
    MAX_IMAGE_PIXELS,
    OCR_PAGE_TIMEOUT,
)
from backend.document_engine.ocr.preprocessing import (
    _ImageTooLargeError,
    _prepare_image,
)
from backend.document_engine.ocr.tesseract import pytesseract
from backend.errors.documents import DocumentRejectedError
from backend.errors.messages import ERROR_MESSAGES, EXTRACTION_MESSAGES


class _TooManyImageFramesError(DocumentRejectedError):
    """Raised when an image contains more frames than allowed."""

    public_message = ERROR_MESSAGES["too_many_image_frames"]


class _ImageRecognitionFailedError(DocumentRejectedError):
    """Raised when Tesseract cannot recognize an image page."""

    public_message = ERROR_MESSAGES["image_recognition_failed"]


def recognize_pages(
    image: Image.Image,
    languages: str,
    *,
    deadline: Deadline | None = None,
) -> str:
    """Recognize image frames, rejecting oversized frames before copying them."""
    page_count = getattr(image, "n_frames", 1)
    if page_count > MAX_DOCUMENT_PAGES:
        raise _TooManyImageFramesError

    result: list[str] = []
    total_characters = 0
    for page_index in range(page_count):
        accepted = _recognize_page(
            image,
            page_index,
            page_count,
            languages,
            deadline,
            MAX_EXTRACTED_TEXT_LENGTH - total_characters,
        )
        if accepted:
            result.append(accepted)
            total_characters += len(accepted)
        if total_characters >= MAX_EXTRACTED_TEXT_LENGTH:
            break

    return "\n\n".join(result)


def _recognize_page(
    image: Image.Image,
    page_index: int,
    page_count: int,
    languages: str,
    deadline: Deadline | None,
    remaining_characters: int,
) -> str:
    if deadline is not None:
        deadline.check()
    image.seek(page_index)

    # Accessing dimensions does not create a decoded copy; copy() below does.
    if image.width * image.height > MAX_IMAGE_PIXELS:
        raise _ImageTooLargeError

    prepared = _prepare_image(image.copy())
    try:
        if deadline is not None:
            deadline.check()
            timeout = min(OCR_PAGE_TIMEOUT, max(deadline.remaining(), 0.001))
        else:
            timeout = OCR_PAGE_TIMEOUT
        text = pytesseract.image_to_string(
            prepared,
            lang=languages,
            config="--psm 3",
            timeout=timeout,
        )
    except RuntimeError as error:
        if deadline is not None:
            deadline.check()
        raise _ImageRecognitionFailedError from error
    finally:
        prepared.close()

    text = text.strip()
    if not text:
        return ""

    prefix = (
        EXTRACTION_MESSAGES["ocr_page_label"].format(index=page_index + 1)
        if page_count > 1
        else ""
    )
    return (prefix + text)[:remaining_characters]
