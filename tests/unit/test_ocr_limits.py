"""Tests that OCR dimensions are checked before frame copies and setup is cached."""

import pytest

import backend.document_engine.ocr.recognize as recognize_module
import backend.document_engine.ocr.tesseract as tesseract_module
from backend.errors.documents import DocumentRejectedError


class _UnexpectedImageCopyError(AssertionError):
    """Raised when OCR copies an oversized image frame."""

    def __init__(self) -> None:
        """Initialize the test assertion error."""
        super().__init__("copy must not be called for oversized frames")


class _OversizedImage:
    n_frames = 1
    width = 100
    height = 100

    def seek(self, _index):
        return None

    def copy(self):
        raise _UnexpectedImageCopyError


def test_ocr_rejects_oversized_frame_before_copy(monkeypatch):
    monkeypatch.setattr(recognize_module, "MAX_IMAGE_PIXELS", 99)
    with pytest.raises(DocumentRejectedError, match="лимит пикселей"):
        recognize_module.recognize_pages(_OversizedImage(), "eng")


def test_tesseract_language_checks_are_cached(monkeypatch):
    calls = {"binary": 0, "languages": 0}
    tesseract_module.ensure_ready.cache_clear()

    def check_binary():
        calls["binary"] += 1

    def check_languages(_languages):
        calls["languages"] += 1

    monkeypatch.setattr(tesseract_module, "_check_tesseract", check_binary)
    monkeypatch.setattr(tesseract_module, "_check_languages", check_languages)

    for _ in range(5):
        tesseract_module.ensure_ready("rus+eng")

    assert calls == {"binary": 1, "languages": 1}
    tesseract_module.ensure_ready.cache_clear()
