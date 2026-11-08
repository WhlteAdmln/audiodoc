import importlib
import shutil
from typing import Protocol, cast

import pytest

from backend.document_engine.ocr import extract_image_text
from tests.builders import create_ocr_image

pytestmark = pytest.mark.integration


class _PytesseractModule(Protocol):
    TesseractError: type[Exception]

    def get_languages(self, config: str = "") -> list[str]: ...


def test_ocr_recognizes_text_from_image():
    if shutil.which("tesseract") is None:
        pytest.skip("Tesseract is not installed")

    try:
        pytesseract = cast(
            "_PytesseractModule",
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

    assert "Document Engine" in text
    assert "Hello" in text
