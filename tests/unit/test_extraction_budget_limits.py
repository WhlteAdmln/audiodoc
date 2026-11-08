# Copyright (c) 2026 Nikolai Zelensky
"""Tests for row/column caps and extractor use of the shared TextBudget."""

from typing import ClassVar

import backend.document_engine.extractors.odf.ods as ods_module
import backend.document_engine.extractors.xlsx as xlsx_module
from backend.common.deadline import Deadline
from backend.common.text_budget import TextBudget
from backend.document_engine.extractors.base import ExtractContext
from backend.document_engine.extractors.odf import extract_odf
from backend.document_engine.extractors.xlsx import extract_xlsx
from tests.builders import create_ods


def test_xlsx_passes_fixed_row_and_column_caps_to_openpyxl(monkeypatch):
    captured = {}

    class FakeSheet:
        title = "Capped"

        def iter_rows(self, *, max_row, max_col, values_only):
            captured.update(max_row=max_row, max_col=max_col, values_only=values_only)
            yield ("one", "two")
            yield ("three", "four")
            yield ("must not be read",)

    class FakeWorkbook:
        worksheets: ClassVar[list[FakeSheet]] = [FakeSheet()]

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr(xlsx_module, "MAX_SHEET_ROWS", 2)
    monkeypatch.setattr(xlsx_module, "MAX_SHEET_COLUMNS", 2)
    monkeypatch.setattr(
        xlsx_module, "load_workbook", lambda *_args, **_kwargs: FakeWorkbook()
    )

    text = extract_xlsx(
        b"workbook", context=ExtractContext(TextBudget(100), Deadline(10))
    )
    assert captured == {"max_row": 2, "max_col": 2, "values_only": True, "closed": True}
    assert "one | two" in text
    assert "three | four" in text
    assert "must not be read" not in text


def test_ods_stops_at_configured_row_and_column_caps(monkeypatch):
    monkeypatch.setattr(ods_module, "MAX_SHEET_ROWS", 1)
    monkeypatch.setattr(ods_module, "MAX_SHEET_COLUMNS", 1)
    text = extract_odf(create_ods(), "ods")
    assert text == "--- Лист: Test sheet ---\nName"
    assert "Value" not in text
    assert "Document engine" not in text
