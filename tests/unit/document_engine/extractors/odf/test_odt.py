# Copyright (c) 2026 Nikolai Zelensky

"""Tests for odf odt."""

from audiodoc.document_engine.extractors.odf import extract_odf
from audiodoc.document_engine.extractors.odf.odt import extract_odt
from tests.support.builders import create_odt
from tests.support.odf_documents import load_document


def test_odt_extracts_headings_and_paragraphs() -> None:
    text = extract_odf(create_odt(), "odt")

    expected_text = "ODT test\nDocument engine works!"
    assert text == expected_text, "ODF dispatch lost headings or paragraphs"


def test_extract_odt_reads_a_loaded_document() -> None:
    document = load_document(create_odt())

    text = extract_odt(document)

    expected_text = "ODT test\nDocument engine works!"
    assert text == expected_text, "the ODT extractor lost headings or paragraphs"
