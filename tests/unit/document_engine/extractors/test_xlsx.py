# Copyright (c) 2026 Nikolai Zelensky

"""Tests for extractors xlsx."""

import pytest

import audiodoc.document_engine.extractors.xlsx as xlsx_module
from audiodoc.common.deadline import Deadline
from audiodoc.common.text_budget import TextBudget
from audiodoc.document_engine.extractors.base import ExtractContext
from audiodoc.document_engine.extractors.xlsx import extract_xlsx
from tests.support.builders import create_xlsx
from tests.support.openpyxl_workbooks import FakeSheet, FakeWorkbook


def test_xlsx_passes_fixed_row_and_column_caps_to_openpyxl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sheet = FakeSheet(
        "Capped", [("one", "two"), ("three", "four"), ("must not be read",)]
    )
    workbook = FakeWorkbook([sheet])
    monkeypatch.setattr(xlsx_module, "MAX_SHEET_ROWS", 2)
    monkeypatch.setattr(xlsx_module, "MAX_SHEET_COLUMNS", 2)
    monkeypatch.setattr(
        xlsx_module, "load_workbook", lambda *_args, **_kwargs: workbook
    )

    text = extract_xlsx(
        b"workbook", context=ExtractContext(TextBudget(100), Deadline(10))
    )
    assert {**sheet.read_arguments, "closed": workbook.closed} == {
        "max_row": 2,
        "max_col": 2,
        "values_only": True,
        "closed": True,
    }
    first_row = "one | two"
    assert first_row in text
    second_row = "three | four"
    assert second_row in text
    capped_row = "must not be read"
    assert capped_row not in text


def test_xlsx_extracts_sheet_name_and_rows() -> None:
    text = extract_xlsx(create_xlsx())

    assert isinstance(text, str)
    sheet_header = "--- Лист: Test sheet ---"
    assert sheet_header in text
    header_row = "Name | Value"
    assert header_row in text
    data_row = "Document engine | Works!"
    assert data_row in text
