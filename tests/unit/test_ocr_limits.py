# Copyright (c) 2026 Nikolai Zelensky
"""Tests that OCR dimensions are checked before frame copies and setup is cached."""

import pytest

import audiodoc.document_engine.ocr as ocr_module
import audiodoc.document_engine.ocr.preprocessing as preprocessing_module
import audiodoc.document_engine.ocr.recognize as recognize_module
import audiodoc.document_engine.ocr.tesseract as tesseract_module
from audiodoc.errors.documents import DocumentRejectedError
from audiodoc.errors.messages import EXTRACTION_MESSAGES


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


def test_ocr_public_messages_remain_unchanged() -> None:
    assert ocr_module._EmptyImageError.public_message == "Изображение пустое"
    assert (
        ocr_module._UnknownImageFormatError.public_message
        == "\u041d\u0435 удалось определить формат изображения"
    )
    assert (
        ocr_module._UnsupportedOcrImageFormatError.public_message
        == "Формат изображения не поддерживается для OCR"
    )
    assert (
        preprocessing_module._ImageTooLargeError.public_message
        == "Изображение слишком большое: превышен лимит пикселей"
    )
    assert (
        recognize_module._TooManyImageFramesError.public_message
        == "\u0412 изображении слишком много страниц"
    )
    assert (
        recognize_module._ImageRecognitionFailedError.public_message
        == "\u041d\u0435 удалось распознать страницу изображения"
    )
    assert EXTRACTION_MESSAGES["ocr_page_label"] == "--- Страница {index} ---\n"


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
