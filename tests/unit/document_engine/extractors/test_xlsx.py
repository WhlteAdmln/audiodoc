# Copyright (c) 2026 Nikolai Zelensky

"""Tests for extractors xlsx."""

from typing import ClassVar

import pytest

import audiodoc.document_engine.extractors.xlsx as xlsx_module
from audiodoc.common.deadline import Deadline
from audiodoc.common.text_budget import TextBudget
from audiodoc.document_engine.extractors.base import ExtractContext
from audiodoc.document_engine.extractors.xlsx import extract_xlsx
from tests.support.builders import create_xlsx


def test_xlsx_passes_fixed_row_and_column_caps_to_openpyxl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    class FakeSheet:
        """Stand in for the real FakeSheet object."""

        title = "Capped"

        @staticmethod
        def iter_rows(
            *, max_row: object, max_col: object, values_only: object
        ) -> object:
            """Provide the ``iter_rows`` behaviour the test relies on."""
            captured.update(max_row=max_row, max_col=max_col, values_only=values_only)
            yield ("one", "two")
            yield ("three", "four")
            yield ("must not be read",)

    class FakeWorkbook:
        """Stand in for the real FakeWorkbook object."""

        worksheets: ClassVar[list[FakeSheet]] = [FakeSheet()]

        @staticmethod
        def close() -> None:
            """Provide the ``close`` behaviour the test relies on."""
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
    expected_fragment = "one | two"
    assert expected_fragment in text
    expected_fragment = "three | four"
    assert expected_fragment in text
    expected_fragment = "must not be read"
    assert expected_fragment not in text


def test_xlsx_extracts_sheet_name_and_rows() -> None:
    text = extract_xlsx(create_xlsx())

    assert isinstance(text, str)
    expected_fragment = "--- Лист: Test sheet ---"
    assert expected_fragment in text
    expected_fragment = "Name | Value"
    assert expected_fragment in text
    expected_fragment = "Document engine | Works!"
    assert expected_fragment in text
