# Copyright (c) 2026 Nikolai Zelensky

"""Tests for ocr recognize."""

import io
from pathlib import Path

import pytest
from PIL import Image

from audiodoc.common.deadline import Deadline, DeadlineExceededError
from audiodoc.document_engine.ocr import recognize as recognize_module
from audiodoc.document_engine.ocr.recognize import recognize_pages
from audiodoc.document_engine.ocr.tesseract import ensure_ready
from audiodoc.errors.documents import DocumentRejectedError
from tests.support.pil_images import OversizedImage, multi_page_tiff
from tests.support.tesseract import FakeTesseract


@pytest.fixture(name="tesseract")
def fixture_tesseract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeTesseract:
    """Put a fake Tesseract alone on PATH and forget earlier readiness checks."""
    fake = FakeTesseract(tmp_path)
    monkeypatch.setenv("PATH", str(fake.bin_dir))
    ensure_ready.cache_clear()
    return fake


def _recognize_tiff(pages: int) -> str:
    with Image.open(io.BytesIO(multi_page_tiff(pages))) as image:
        return recognize_pages(image, "rus+eng")


def _rejection(image: object) -> str:
    with pytest.raises(DocumentRejectedError) as caught:
        recognize_pages(image, "eng")
    return str(caught.value)


def test_labels_each_page_of_a_multi_page_image(tesseract: FakeTesseract) -> None:
    tesseract.configure(pages=[b" page one \n", b"\tpage two "])

    text = _recognize_tiff(2)

    expected_text = "--- Страница 1 ---\npage one\n\n--- Страница 2 ---\npage two"
    assert text == expected_text, "pages lost their labels or order"


def test_does_not_label_a_single_page(tesseract: FakeTesseract) -> None:
    tesseract.configure(pages=[b"  alone\n"])

    text = _recognize_tiff(1)

    expected_text = "alone"
    assert text == expected_text, "a single page got a label"


def test_skips_pages_without_text(tesseract: FakeTesseract) -> None:
    tesseract.configure(pages=[b" \n\f", b"second"])

    text = _recognize_tiff(2)

    expected_text = "--- Страница 2 ---\nsecond"
    assert text == expected_text, "an empty page reached the result"


@pytest.mark.usefixtures("tesseract")
def test_rejects_more_frames_than_the_page_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(recognize_module, "MAX_DOCUMENT_PAGES", 1)

    with Image.open(io.BytesIO(multi_page_tiff(2))) as image:
        message = _rejection(image)

    expected = "В изображении слишком много страниц"
    assert message == expected, "too many frames were accepted"


def test_reads_no_frame_of_an_image_over_the_page_limit(
    tesseract: FakeTesseract, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(recognize_module, "MAX_DOCUMENT_PAGES", 1)

    with Image.open(io.BytesIO(multi_page_tiff(3))) as image:
        _rejection(image)

    expected_empty: list[list[str]] = []
    assert tesseract.recognitions == expected_empty, "a frame was recognized"


def test_rejects_an_oversized_frame_before_copying_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(recognize_module, "MAX_IMAGE_PIXELS", 99)

    message = _rejection(OversizedImage())

    expected = "Изображение слишком большое: превышен лимит пикселей"
    assert message == expected, "an oversized frame was not rejected"


def test_cuts_the_text_at_the_extraction_limit(
    tesseract: FakeTesseract, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(recognize_module, "MAX_EXTRACTED_TEXT_LENGTH", 21)
    tesseract.configure(pages=[b"abcdef", b"ghi"])

    text = _recognize_tiff(2)

    expected_text = "--- Страница 1 ---\nab"
    assert text == expected_text, "the text limit was not applied"


def test_stops_recognizing_after_the_extraction_limit(
    tesseract: FakeTesseract, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(recognize_module, "MAX_EXTRACTED_TEXT_LENGTH", 21)
    tesseract.configure(pages=[b"abcdef", b"ghi"])

    _recognize_tiff(2)

    expected_runs = 1
    assert len(tesseract.recognitions) == expected_runs, "OCR ran past the limit"


def test_hides_tesseract_errors_behind_a_safe_message(
    tesseract: FakeTesseract,
) -> None:
    tesseract.configure(exit_code=1, stderr="Error: /srv/secret/input.png corrupt")

    with Image.new("RGB", (6, 6)) as image:
        message = _rejection(image)

    expected = "Не удалось распознать страницу изображения"
    assert message == expected, "Tesseract details reached the client"


def test_maps_a_page_timeout_to_a_recognition_error(
    tesseract: FakeTesseract, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(recognize_module, "OCR_PAGE_TIMEOUT", 0.3)
    tesseract.configure(delay=10)

    with Image.new("RGB", (8, 8)) as image:
        message = _rejection(image)

    expected = "Не удалось распознать страницу изображения"
    assert message == expected, "a hung page was not stopped"


def test_removes_the_image_directory_after_a_timeout(
    tesseract: FakeTesseract, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(recognize_module, "OCR_PAGE_TIMEOUT", 0.3)
    tesseract.configure(delay=10)
    with Image.new("RGB", (8, 8)) as image, pytest.raises(DocumentRejectedError):
        recognize_pages(image, "eng")

    image_directory = Path(tesseract.recognitions[0][0]).parent
    assert image_directory.exists() is False, "the OCR image outlived a timeout"


def test_reports_the_shared_deadline_when_it_runs_out(
    tesseract: FakeTesseract,
) -> None:
    tesseract.configure(delay=10)

    with (
        Image.new("RGB", (8, 8)) as image,
        pytest.raises(DeadlineExceededError) as caught,
    ):
        recognize_pages(image, "eng", deadline=Deadline(0.3))

    expected_message = "processing deadline exceeded"
    assert str(caught.value) == expected_message, "the deadline was not reported"
