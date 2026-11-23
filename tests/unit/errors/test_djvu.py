# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the client-safe DJVU errors."""

import pytest

from audiodoc.errors.djvu import (
    DjvuNoPagesError,
    DjvuOutputTooLargeError,
    DjvuPageCountUnavailableError,
    DjvuPageRenderError,
    DjvuPageTooLargeError,
    DjvuProcessingTimeoutError,
    DjvuTextLayerReadError,
    DjvuTextLayerTimeoutError,
    DjvuTextTooLargeError,
    DjvuTooManyPagesError,
    InvalidDjvuPageCountError,
)


@pytest.mark.parametrize(
    ("error_type", "expected_message"),
    [
        (DjvuOutputTooLargeError, "Результат программы DjVuLibre слишком большой"),
        (DjvuProcessingTimeoutError, "Превышено время обработки DJVU"),
        (
            DjvuPageCountUnavailableError,
            "Не удалось определить количество страниц DJVU",
        ),
        (InvalidDjvuPageCountError, "Некорректное количество страниц DJVU"),
        (DjvuNoPagesError, "В DJVU не найдено страниц"),
        (DjvuTooManyPagesError, "В DJVU слишком много страниц"),
        (DjvuPageRenderError, "Не удалось отобразить страницу DJVU"),
        (DjvuPageTooLargeError, "Страница DJVU слишком велика для OCR"),
        (DjvuTextTooLargeError, "Текстовый слой DJVU слишком большой"),
        (DjvuTextLayerTimeoutError, "Превышено время извлечения текста DJVU"),
        (DjvuTextLayerReadError, "Не удалось прочитать DJVU"),
    ],
)
def test_djvu_error_keeps_its_public_message(
    error_type: type[Exception],
    expected_message: str,
) -> None:
    assert error_type.public_message == expected_message, (
        f"{error_type.__name__} changed its client-facing message"
    )
