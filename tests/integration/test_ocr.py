import shutil

import pytest

from backend.document_engine.ocr import extract_image_text
from tests.builders import create_ocr_image

pytestmark = pytest.mark.integration


def test_ocr_recognizes_text_from_image():
    if shutil.which("tesseract") is None:
        pytest.skip("Tesseract is not installed")

    import pytesseract

    try:
        languages = set(pytesseract.get_languages(config=""))
    except Exception as error:
        pytest.skip(f"Tesseract languages are unavailable: {error}")

    if not {"rus", "eng"}.issubset(languages):
        pytest.skip("Tesseract language packs rus and eng are required")

    text = extract_image_text(create_ocr_image())

    assert "Document Engine" in text
    assert "Hello" in text
