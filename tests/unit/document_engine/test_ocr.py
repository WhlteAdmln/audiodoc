# Copyright (c) 2026 Nikolai Zelensky

"""Tests for document engine ocr."""

from pathlib import Path

import pytest

from audiodoc.common import deadline as deadline_module
from audiodoc.common.deadline import Deadline, DeadlineExceededError
from audiodoc.document_engine.ocr import extract_image_text
from audiodoc.document_engine.ocr.tesseract import ensure_ready
from audiodoc.errors.base import AppError
from tests.support.clock import FakeMonotonicClock
from tests.support.pil_images import encoded_image, png_header
from tests.support.tesseract import FakeTesseract


@pytest.fixture(name="tesseract")
def fixture_tesseract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeTesseract:
    """Put a fake Tesseract alone on PATH and forget earlier readiness checks."""
    fake = FakeTesseract(tmp_path)
    monkeypatch.setenv("PATH", str(fake.bin_dir))
    ensure_ready.cache_clear()
    return fake


def _rejection(data: bytes) -> str:
    with pytest.raises(AppError) as caught:
        extract_image_text(data)
    return str(caught.value)


@pytest.fixture(name="expired_deadline")
def fixture_expired_deadline(monkeypatch: pytest.MonkeyPatch) -> Deadline:
    """Return a deadline that has already run out on a manual clock."""
    clock = FakeMonotonicClock()
    monkeypatch.setattr(deadline_module, "time", clock)
    deadline = Deadline(2)
    clock.advance(2)
    return deadline


@pytest.mark.parametrize("image_format", ["PNG", "JPEG", "TIFF", "BMP", "WEBP"])
def test_recognizes_supported_formats(
    tesseract: FakeTesseract, image_format: str
) -> None:
    tesseract.configure(pages=["Строка 1\n".encode()])

    text = extract_image_text(encoded_image(image_format))

    expected_text = "Строка 1"
    assert text == expected_text, "a supported format was not recognized"


@pytest.mark.usefixtures("tesseract")
def test_rejects_empty_data() -> None:
    message = _rejection(b"")

    expected = "Изображение пустое"
    assert message == expected, "empty data was accepted"


@pytest.mark.usefixtures("tesseract")
@pytest.mark.parametrize(
    "data", [b"not an image", b"%PDF-1.7\n", b"\x89PNG", b"\x00" * 64], ids=repr
)
def test_rejects_data_of_unknown_format(data: bytes) -> None:
    message = _rejection(data)

    expected = "Не удалось определить формат изображения"
    assert message == expected, "unidentifiable data was accepted"


@pytest.mark.usefixtures("tesseract")
@pytest.mark.parametrize("image_format", ["GIF", "ICO", "PPM"])
def test_rejects_formats_without_ocr_support(image_format: str) -> None:
    message = _rejection(encoded_image(image_format))

    expected = "Формат изображения не поддерживается для OCR"
    assert message == expected, "an unsupported format was accepted"


@pytest.mark.usefixtures("tesseract")
def test_rejects_a_header_that_declares_too_many_pixels() -> None:
    message = _rejection(png_header(7000, 7000))

    expected = "Изображение слишком большое: превышен лимит пикселей"
    assert message == expected, "a huge declared size was not rejected"


def test_requires_tesseract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    monkeypatch.setenv("PATH", str(empty_bin))
    ensure_ready.cache_clear()

    message = _rejection(encoded_image("PNG"))

    expected = "На сервере не установлена нужная программа"
    assert message == expected, "a missing Tesseract was not reported"


@pytest.mark.usefixtures("tesseract")
def test_checks_the_deadline_first(expired_deadline: Deadline) -> None:
    with pytest.raises(DeadlineExceededError) as caught:
        extract_image_text(encoded_image("PNG"), deadline=expired_deadline)

    expected_message = "processing deadline exceeded"
    assert str(caught.value) == expected_message, "the expired deadline was ignored"


def test_does_not_run_tesseract_after_the_deadline(
    tesseract: FakeTesseract, expired_deadline: Deadline
) -> None:
    with pytest.raises(DeadlineExceededError):
        extract_image_text(encoded_image("PNG"), deadline=expired_deadline)

    expected_runs = 0
    assert len(tesseract.recognitions) == expected_runs, "OCR ran after the deadline"
