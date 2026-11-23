# Copyright (c) 2026 Nikolai Zelensky

"""Tests for odf odt."""

from audiodoc.document_engine.extractors.odf import extract_odf
from audiodoc.document_engine.extractors.odf.odt import extract_odt
from tests.support.builders import create_odt
from tests.support.odf_documents import load_document


def test_odt_extracts_headings_and_paragraphs() -> None:
    data = create_odt()
    text = extract_odf(data, "odt")

    expected_text = "ODT test\nDocument engine works!"
    assert text == expected_text
    assert extract_odt(load_document(data)) == text
