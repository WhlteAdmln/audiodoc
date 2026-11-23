# Copyright (c) 2026 Nikolai Zelensky

"""Tests for ocr preprocessing."""

import pytest
from PIL import Image

from audiodoc.document_engine.ocr import preprocessing as ocr_preprocessing
from audiodoc.document_engine.ocr import recognize as ocr_recognize
from audiodoc.errors.documents import DocumentRejectedError


def _capture_tesseract_input(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, tuple[int, int], object]]:
    seen: list[tuple[str, tuple[int, int], object]] = []

    def image_to_string(image: Image.Image, **_kwargs: object) -> str:
        pixel = image.getpixel((0, 0))
        seen.append((image.mode, image.size, pixel))
        return "Ёжик 42"

    monkeypatch.setattr(ocr_recognize.pytesseract, "image_to_string", image_to_string)
    return seen


def test_recognition_receives_a_same_sized_grayscale_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _capture_tesseract_input(monkeypatch)
    with Image.new("RGB", (4, 3), color=(100, 140, 30)) as source:
        ocr_recognize.recognize_pages(source, "rus+eng")
    actual = [(mode, size) for mode, size, _pixel in seen]
    expected = [("L", (4, 3))]
    assert actual == expected, "the page must reach Tesseract as same-sized grayscale"


def test_recognition_flattens_transparency_onto_white(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _capture_tesseract_input(monkeypatch)
    with Image.new("RGBA", (3, 5), color=(12, 200, 7, 0)) as source:
        ocr_recognize.recognize_pages(source, "rus+eng")
    actual = [pixel for _mode, _size, pixel in seen]
    expected = [255]
    assert actual == expected, "a fully transparent page must become white"


def test_preprocessing_rejects_excessive_pixel_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _capture_tesseract_input(monkeypatch)
    monkeypatch.setattr(ocr_preprocessing, "MAX_IMAGE_PIXELS", 3)
    with (
        Image.new("RGB", (2, 2)) as source,
        pytest.raises(DocumentRejectedError, match="превышен лимит пикселей"),
    ):
        ocr_recognize.recognize_pages(source, "rus+eng")
