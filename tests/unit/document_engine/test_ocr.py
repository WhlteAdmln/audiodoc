# Copyright (c) 2026 Nikolai Zelensky

"""Tests for document engine ocr."""

import io

import pytest
from PIL import Image

import audiodoc.document_engine.ocr as ocr_module
import audiodoc.document_engine.ocr.preprocessing as preprocessing_module
import audiodoc.document_engine.ocr.recognize as recognize_module
from audiodoc.document_engine.ocr import (
    extract_image_text,
)
from audiodoc.errors.messages import EXTRACTION_MESSAGES


def test_ocr_package_keeps_extract_image_text_entry_point(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("audiodoc.document_engine.ocr.ensure_ready", lambda _: None)
    monkeypatch.setattr(
        "audiodoc.document_engine.ocr.recognize_pages",
        lambda *_args, **_kwargs: "Recognized text",
    )

    output = io.BytesIO()
    Image.new("RGB", (2, 2), color="white").save(output, format="PNG")

    assert extract_image_text(output.getvalue()) == "Recognized text"


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
