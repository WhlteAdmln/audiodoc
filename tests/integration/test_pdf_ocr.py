import shutil

import pytest

pytestmark = pytest.mark.integration

from backend.document_engine.extractors.pdf import extract_pdf
from tests.builders import create_scanned_pdf


def test_pdf_text_layer_and_scanned_page_ocr(tmp_path):
    if shutil.which("tesseract") is None:
        pytest.skip("Tesseract is not installed")

    import pytesseract

    try:
        languages = set(pytesseract.get_languages(config=""))
    except Exception as error:
        pytest.skip(f"Tesseract languages are unavailable: {error}")

    if not {"rus", "eng"}.issubset(languages):
        pytest.skip("Tesseract language packs rus and eng are required")

    path = tmp_path / "test_scanned.pdf"
    path.write_bytes(create_scanned_pdf())

    text = extract_pdf(path.read_bytes())

    assert "This is a normal PDF text page" in text
    assert "Scanned PDF OCR Test" in text
    assert "This page has no text layer" in text
