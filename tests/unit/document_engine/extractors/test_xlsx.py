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


@pytest.fixture(name="capped_workbook")
def fixture_capped_workbook(monkeypatch: pytest.MonkeyPatch) -> FakeWorkbook:
    """Serve a three-row workbook to the extractor with two-row and column caps."""
    sheet = FakeSheet(
        "Capped", [("one", "two"), ("three", "four"), ("must not be read",)]
    )
    workbook = FakeWorkbook([sheet])
    monkeypatch.setattr(xlsx_module, "MAX_SHEET_ROWS", 2)
    monkeypatch.setattr(xlsx_module, "MAX_SHEET_COLUMNS", 2)
    monkeypatch.setattr(
        xlsx_module, "load_workbook", lambda *_args, **_kwargs: workbook
    )
    return workbook


def test_xlsx_passes_fixed_row_and_column_caps_to_openpyxl(
    capped_workbook: FakeWorkbook,
) -> None:
    extract_xlsx(b"workbook", context=ExtractContext(TextBudget(100), Deadline(10)))

    sheet = capped_workbook.worksheets[0]
    expected_arguments = {
        "max_row": 2,
        "max_col": 2,
        "values_only": True,
        "closed": True,
    }
    assert {
        **sheet.read_arguments,
        "closed": capped_workbook.closed,
    } == expected_arguments, "the caps must reach openpyxl and the workbook close"


@pytest.mark.usefixtures("capped_workbook")
@pytest.mark.parametrize(
    ("row", "expected_count"),
    [("one | two", 1), ("three | four", 1), ("must not be read", 0)],
)
def test_xlsx_extracts_only_rows_within_caps(row: str, expected_count: int) -> None:
    text = extract_xlsx(
        b"workbook", context=ExtractContext(TextBudget(100), Deadline(10))
    )

    assert text.count(row) == expected_count, (
        "only rows within the caps must be extracted"
    )


@pytest.fixture(name="gapped_workbook")
def fixture_gapped_workbook(monkeypatch: pytest.MonkeyPatch) -> FakeWorkbook:
    """Serve a sheet whose row has an inner and trailing empty cells."""
    sheet = FakeSheet("Gaps", [("Kp", None, 7, "", None, None)])
    workbook = FakeWorkbook([sheet])
    monkeypatch.setattr(
        xlsx_module, "load_workbook", lambda *_args, **_kwargs: workbook
    )
    return workbook


@pytest.mark.usefixtures("gapped_workbook")
def test_xlsx_ends_row_at_last_non_empty_cell() -> None:
    text = extract_xlsx(
        b"workbook", context=ExtractContext(TextBudget(100), Deadline(10))
    )

    expected_text = "--- Лист: Gaps ---\nKp |  | 7"
    assert text == expected_text, "a row must keep inner gaps and end at its last cell"


def test_xlsx_extracts_workbook_rows_without_padding() -> None:
    text = extract_xlsx(create_xlsx())

    expected_text = "--- Лист: Test sheet ---\nName | Value\nDocument engine | Works!"
    assert text == expected_text, "rows of a real workbook must not be padded"


def test_xlsx_extracts_text_as_string() -> None:
    text = extract_xlsx(create_xlsx())

    assert isinstance(text, str), "the extractor must return text"


@pytest.mark.parametrize(
    "expected_fragment",
    ["--- Лист: Test sheet ---", "Name | Value", "Document engine | Works!"],
)
def test_xlsx_extracts_sheet_name_and_rows(expected_fragment: str) -> None:
    text = extract_xlsx(create_xlsx())

    assert expected_fragment in text, "the sheet header and rows must be extracted"
