# Copyright (c) 2026 Nikolai Zelensky

"""Tests for odf ods."""

import pytest

import audiodoc.document_engine.extractors.odf.ods as ods_module
from audiodoc.document_engine.extractors.odf import extract_odf
from audiodoc.document_engine.extractors.odf.ods import extract_ods
from tests.support.builders import create_ods
from tests.support.odf_documents import load_document


def test_ods_stops_at_configured_row_and_column_caps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ods_module, "MAX_SHEET_ROWS", 1)
    monkeypatch.setattr(ods_module, "MAX_SHEET_COLUMNS", 1)
    text = extract_odf(create_ods(), "ods")
    expected_text = "--- Лист: Test sheet ---\nName"
    assert text == expected_text, "the row and column caps were not applied"


def test_ods_extracts_sheet_names_and_rows() -> None:
    data = create_ods()
    text = extract_odf(data, "ods")

    expected_text = "--- Лист: Test sheet ---\nName | Value\nDocument engine | Works!"
    assert text == expected_text, "wrong sheet text from the ODF dispatcher"


def test_ods_extracts_sheet_names_and_rows_from_loaded_document() -> None:
    data = create_ods()

    text = extract_ods(load_document(data))

    expected_text = "--- Лист: Test sheet ---\nName | Value\nDocument engine | Works!"
    assert text == expected_text, "wrong sheet text from a loaded document"
