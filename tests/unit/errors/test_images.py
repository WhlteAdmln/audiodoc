# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the client-safe image recognition errors."""

import pytest

from audiodoc.errors.images import (
    EmptyImageError,
    ImageRecognitionFailedError,
    ImageTooLargeError,
    TooManyImageFramesError,
    UnknownImageFormatError,
    UnsupportedOcrImageFormatError,
)


@pytest.mark.parametrize(
    ("error_type", "expected_message"),
    [
        (EmptyImageError, "Изображение пустое"),
        (
            UnknownImageFormatError,
            "Не удалось определить формат изображения",
        ),
        (
            UnsupportedOcrImageFormatError,
            "Формат изображения не поддерживается для OCR",
        ),
        (ImageTooLargeError, "Изображение слишком большое: превышен лимит пикселей"),
        (TooManyImageFramesError, "В изображении слишком много страниц"),
        (
            ImageRecognitionFailedError,
            "Не удалось распознать страницу изображения",
        ),
    ],
)
def test_image_error_keeps_its_public_message(
    error_type: type[Exception],
    expected_message: str,
) -> None:
    assert error_type.public_message == expected_message, (
        f"{error_type.__name__} changed its client-facing message"
    )
