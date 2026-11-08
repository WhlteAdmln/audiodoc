"""Recognize image frames using Tesseract after checking pixel dimensions."""

from typing import cast

import pytesseract
from PIL import Image

from backend.common.deadline import Deadline
from backend.document_engine.limits import (
    MAX_DOCUMENT_PAGES,
    MAX_EXTRACTED_TEXT_LENGTH,
    MAX_IMAGE_PIXELS,
    OCR_PAGE_TIMEOUT,
)
from backend.document_engine.ocr.preprocessing import _prepare_image
from backend.errors.documents import DocumentRejectedError


def recognize_pages(
    image: Image.Image,
    languages: str,
    *,
    deadline: Deadline | None = None,
) -> str:
    """Recognize image frames, rejecting oversized frames before copying them."""
    page_count = getattr(image, "n_frames", 1)
    if page_count > MAX_DOCUMENT_PAGES:
        raise DocumentRejectedError("В изображении слишком много страниц")

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
        raise DocumentRejectedError(
            "Изображение слишком большое: превышен лимит пикселей"
        )

    prepared = _prepare_image(image.copy())
    try:
        if deadline is not None:
            deadline.check()
            timeout = min(OCR_PAGE_TIMEOUT, max(deadline.remaining(), 0.001))
        else:
            timeout = OCR_PAGE_TIMEOUT
        text = cast(
            "str",
            pytesseract.image_to_string(
                prepared,
                lang=languages,
                config="--psm 3",
                timeout=timeout,
            ),
        )
    except RuntimeError as error:
        if deadline is not None:
            deadline.check()
        raise DocumentRejectedError(
            "Не удалось распознать страницу изображения"
        ) from error
    finally:
        prepared.close()

    text = text.strip()
    if not text:
        return ""

    prefix = f"--- Страница {page_index + 1} ---\n" if page_count > 1 else ""
    return (prefix + text)[:remaining_characters]
