# Copyright (c) 2026 Nikolai Zelensky
"""Integration tests for OCR of images."""

import importlib
import shutil
from typing import TYPE_CHECKING, cast

import pytest

from audiodoc.document_engine.ocr import extract_image_text
from tests.support.builders import create_ocr_image

if TYPE_CHECKING:
    from tests.support.tesseract import PytesseractModule

pytestmark = pytest.mark.integration


def test_ocr_recognizes_text_from_image() -> None:
    if shutil.which("tesseract") is None:
        pytest.skip("Tesseract is not installed")

    try:
        pytesseract = cast(
            "PytesseractModule",
            importlib.import_module("pytesseract"),
        )
    except ImportError as error:
        pytest.skip(f"Tesseract languages are unavailable: {error}")

    try:
        languages = set(pytesseract.get_languages(config=""))
    except (OSError, pytesseract.TesseractError) as error:
        pytest.skip(f"Tesseract languages are unavailable: {error}")

    if not {"rus", "eng"}.issubset(languages):
        pytest.skip("Tesseract language packs rus and eng are required")

    text = extract_image_text(create_ocr_image())

    expected_phrases = ["Document Engine", "Hello"]
    recognized_phrases = [phrase for phrase in expected_phrases if phrase in text]
    assert recognized_phrases == expected_phrases, f"OCR missed phrases in {text!r}"
