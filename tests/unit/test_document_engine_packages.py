# Copyright (c) 2026 Nikolai Zelensky
"""Unit-проверки разнесённых пакетов Document Engine и OCR."""

import io

import pytest
from PIL import Image

import backend.document_engine.result as result_module
from backend.document_engine.detection import detect_format
from backend.document_engine.detection.formats import (
    IMAGE_EXTENSIONS,
    SUPPORTED_FORMATS,
    extension_map,
)
from backend.document_engine.ocr import (
    extract_image_text,
)
from backend.document_engine.ocr import preprocessing as ocr_preprocessing
from backend.document_engine.ocr import recognize as ocr_package_recognize
from backend.document_engine.ocr import tesseract as ocr_tesseract
from backend.document_engine.result import build_result, limit_text
from backend.errors.documents import DependencyMissingError, DocumentRejectedError


def test_detection_package_exports_expected_format_collections():
    assert "pdf" in SUPPORTED_FORMATS
    assert ".png" in IMAGE_EXTENSIONS
    assert extension_map["markdown"] == "md"


def test_image_extension_check_still_precedes_file_signature():
    assert detect_format(b"%PDF-1.7 payload", "payload.png") is None


def test_signature_check_still_precedes_other_extension():
    assert detect_format(b"%PDF-1.7 payload", "payload.txt") == "pdf"


def test_text_extension_mapping_is_preserved():
    assert detect_format(b"not really markdown", "payload.markdown") == "md"


def test_limit_text_and_build_result_preserve_response_shape(monkeypatch):
    monkeypatch.setattr(result_module, "MAX_EXTRACTED_TEXT_LENGTH", 5)
    assert limit_text("123456") == "12345"
    assert build_result("txt", " hello ", truncated=True) == {
        "format": "txt",
        "text": "hello",
        "characters": 5,
        "truncated": True,
    }


def test_prepare_image_returns_autocontrasted_grayscale():
    source = Image.new("RGB", (4, 4), color=(100, 100, 100))
    prepared = ocr_preprocessing._prepare_image(source)
    try:
        assert prepared.mode == "L"
        assert prepared.size == (4, 4)
    finally:
        prepared.close()
        source.close()


def test_prepare_image_rejects_excessive_pixel_count(monkeypatch):
    monkeypatch.setattr(ocr_preprocessing, "MAX_IMAGE_PIXELS", 3)
    source = Image.new("RGB", (2, 2))
    try:
        with pytest.raises(DocumentRejectedError, match="превышен лимит пикселей"):
            ocr_preprocessing._prepare_image(source)
    finally:
        source.close()


def test_check_tesseract_requires_binary_when_not_installed(monkeypatch):
    monkeypatch.setattr(ocr_tesseract.shutil, "which", lambda _: None)
    with pytest.raises(DependencyMissingError):
        ocr_tesseract._check_tesseract()


def test_check_languages_reports_missing_language(monkeypatch):
    monkeypatch.setattr(
        ocr_tesseract.pytesseract,
        "get_languages",
        lambda config="": ["eng"],
    )
    with pytest.raises(DependencyMissingError):
        ocr_tesseract._check_languages("rus+eng")


def test_recognize_pages_preserves_page_headers_and_timeout(monkeypatch):
    class DummyPrepared:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    class DummyImage:
        n_frames = 2
        width = 10
        height = 10

        def __init__(self):
            self.current_page = None

        def seek(self, page):
            self.current_page = page

        def copy(self):
            return object()

    prepared_images = []
    calls = []

    def prepare(_image):
        item = DummyPrepared()
        prepared_images.append(item)
        return item

    def recognize(_image, *, lang, config, timeout):
        calls.append((lang, config, timeout))
        return f" page {len(calls)} "

    monkeypatch.setattr(ocr_package_recognize, "_prepare_image", prepare)
    monkeypatch.setattr(
        ocr_package_recognize.pytesseract,
        "image_to_string",
        recognize,
    )

    text = ocr_package_recognize.recognize_pages(DummyImage(), "rus+eng")

    assert text == "--- Страница 1 ---\npage 1\n\n--- Страница 2 ---\npage 2"
    assert calls == [("rus+eng", "--psm 3", 60)] * 2
    assert all(item.closed for item in prepared_images)


def test_ocr_package_keeps_extract_image_text_entry_point(monkeypatch):
    monkeypatch.setattr("backend.document_engine.ocr.ensure_ready", lambda _: None)
    monkeypatch.setattr(
        "backend.document_engine.ocr.recognize_pages",
        lambda image, languages, **_kwargs: "Recognized text",
    )

    output = io.BytesIO()
    Image.new("RGB", (2, 2), color="white").save(output, format="PNG")

    assert extract_image_text(output.getvalue()) == "Recognized text"
