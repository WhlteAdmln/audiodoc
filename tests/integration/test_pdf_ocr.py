# Copyright (c) 2026 Nikolai Zelensky
"""Integration tests for PDF text extraction and OCR."""

import importlib
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

from audiodoc.document_engine.extractors.pdf import extract_pdf
from tests.support.builders import create_scanned_pdf

if TYPE_CHECKING:
    from tests.support.tesseract import PytesseractModule

pytestmark = pytest.mark.integration


@pytest.fixture(name="scanned_pdf_text")
def fixture_scanned_pdf_text(tmp_path: Path) -> str:
    """Extract a PDF with a text layer page and a scanned page, or skip without OCR."""
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

    path = tmp_path / "test_scanned.pdf"
    path.write_bytes(create_scanned_pdf())

    return extract_pdf(path.read_bytes())


@pytest.mark.parametrize(
    "expected_fragment",
    [
        "This is a normal PDF text page",
        "Scanned PDF OCR Test",
        "This page has no text layer",
    ],
)
def test_extracts_pdf_text_layer_and_recognizes_scanned_page(
    scanned_pdf_text: str,
    expected_fragment: str,
) -> None:
    assert expected_fragment in scanned_pdf_text, (
        "the text layer and the recognized scanned page must be extracted"
    )
