# Copyright (c) 2026 Nikolai Zelensky

"""Tests for ocr preprocessing."""

import io
from pathlib import Path

import pytest
from PIL import Image

from audiodoc.document_engine.ocr import preprocessing as preprocessing_module
from audiodoc.document_engine.ocr.recognize import recognize_pages
from audiodoc.document_engine.ocr.tesseract import ensure_ready
from audiodoc.errors.documents import DocumentRejectedError
from tests.support.tesseract import FakeTesseract

_EXIF_ORIENTATION = 0x0112
_ROTATED_90_CLOCKWISE = 6


@pytest.fixture(name="tesseract")
def fixture_tesseract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeTesseract:
    """Put a fake Tesseract alone on PATH and forget earlier readiness checks."""
    fake = FakeTesseract(tmp_path)
    monkeypatch.setenv("PATH", str(fake.bin_dir))
    ensure_ready.cache_clear()
    return fake


def _received(tesseract: FakeTesseract, source: Image.Image) -> Image.Image:
    recognize_pages(source, "rus+eng")
    with Image.open(tesseract.received_image(0)) as received:
        received.load()
        return received.copy()


def test_sends_a_same_sized_grayscale_page(tesseract: FakeTesseract) -> None:
    with Image.new("RGB", (4, 3), color=(100, 140, 30)) as source:
        received = _received(tesseract, source)

    expected = ("L", (4, 3))
    assert (received.mode, received.size) == expected, "the page was not grayscale"


@pytest.mark.parametrize(
    ("mode", "color"), [("RGBA", (12, 200, 7, 0)), ("LA", (3, 0))], ids=str
)
def test_flattens_transparency_onto_white(
    tesseract: FakeTesseract, mode: str, color: tuple[int, ...]
) -> None:
    with Image.new(mode, (3, 5), color=color) as source:
        received = _received(tesseract, source)

    expected_pixel = 255
    assert received.getpixel((1, 2)) == expected_pixel, "transparency was not white"


def test_applies_the_exif_orientation(tesseract: FakeTesseract) -> None:
    with Image.new("RGB", (4, 2), color="white") as image:
        exif = image.getexif()
        exif[_EXIF_ORIENTATION] = _ROTATED_90_CLOCKWISE
        output = io.BytesIO()
        image.save(output, format="JPEG", exif=exif.tobytes())
    with Image.open(io.BytesIO(output.getvalue())) as source:
        received = _received(tesseract, source)

    expected_size = (2, 4)
    assert received.size == expected_size, "the EXIF orientation was ignored"


def test_stretches_the_contrast(tesseract: FakeTesseract) -> None:
    with Image.new("L", (2, 1), color=100) as source:
        source.putpixel((1, 0), 150)
        received = _received(tesseract, source)

    expected_extrema = (0, 255)
    assert received.getextrema() == expected_extrema, "the contrast was not stretched"


@pytest.mark.usefixtures("tesseract")
def test_rejects_an_excessive_pixel_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preprocessing_module, "MAX_IMAGE_PIXELS", 3)

    with (
        Image.new("RGB", (2, 2)) as source,
        pytest.raises(DocumentRejectedError) as caught,
    ):
        recognize_pages(source, "rus+eng")

    expected = "Изображение слишком большое: превышен лимит пикселей"
    assert str(caught.value) == expected, "an excessive pixel count was accepted"


def test_does_not_run_ocr_on_an_excessive_pixel_count(
    tesseract: FakeTesseract, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(preprocessing_module, "MAX_IMAGE_PIXELS", 3)

    with Image.new("RGB", (2, 2)) as source, pytest.raises(DocumentRejectedError):
        recognize_pages(source, "rus+eng")

    expected_empty: list[list[str]] = []
    assert tesseract.recognitions == expected_empty, "OCR ran on a rejected image"
