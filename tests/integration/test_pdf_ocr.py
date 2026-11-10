# Copyright (c) 2026 Nikolai Zelensky
import importlib
import shutil
from typing import Protocol, cast

import pytest

from audiodoc.document_engine.extractors.pdf import extract_pdf
from tests.builders import create_scanned_pdf

pytestmark = pytest.mark.integration


class _PytesseractModule(Protocol):
    TesseractError: type[Exception]

    def get_languages(self, config: str = "") -> list[str]: ...


def test_pdf_text_layer_and_scanned_page_ocr(tmp_path):
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

    path = tmp_path / "test_scanned.pdf"
    path.write_bytes(create_scanned_pdf())

    text = extract_pdf(path.read_bytes())

    assert "This is a normal PDF text page" in text
    assert "Scanned PDF OCR Test" in text
    assert "This page has no text layer" in text
