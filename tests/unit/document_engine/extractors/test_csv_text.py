# Copyright (c) 2026 Nikolai Zelensky

"""Tests for extractors csv text."""

from importlib import import_module
from typing import Never

import pytest

from audiodoc.common.deadline import Deadline
from audiodoc.common.text_budget import TextBudget
from audiodoc.document_engine.extractors.base import ExtractContext
from audiodoc.document_engine.extractors.csv_text import extract_csv


def test_csv_detects_delimiter_and_joins_cells() -> None:
    data = b"Name;Value\nDocument engine;Works!\n"
    expected_extract_csv = "Name | Value\nDocument engine | Works!"
    assert extract_csv(data) == expected_extract_csv


def test_csv_falls_back_to_excel_dialect_when_sniffer_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    csv_module = import_module("audiodoc.document_engine.extractors.csv_text")

    def fail_sniff(*_args: object, **_kwargs: object) -> Never:
        raise csv_module.csv.Error

    monkeypatch.setattr(csv_module.csv.Sniffer, "sniff", fail_sniff)
    expected_extract_csv = "one | two\nthree | four"
    assert extract_csv(b"one,two\nthree,four") == expected_extract_csv


def test_csv_marks_truncation_when_another_row_follows_an_exact_fit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    csv_module = import_module("audiodoc.document_engine.extractors.csv_text")
    monkeypatch.setattr(
        csv_module.csv.Sniffer, "sniff", lambda *_args, **_kwargs: csv_module.csv.excel
    )
    budget = TextBudget(3)
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    expected_extract_csv = "abc"
    assert extract_csv(b"abc\ndef\n", context=context) == expected_extract_csv
    assert budget.truncated is True


def test_csv_exact_fit_at_end_of_file_is_not_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    csv_module = import_module("audiodoc.document_engine.extractors.csv_text")
    monkeypatch.setattr(
        csv_module.csv.Sniffer, "sniff", lambda *_args, **_kwargs: csv_module.csv.excel
    )
    budget = TextBudget(3)
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    expected_extract_csv = "abc"
    assert extract_csv(b"abc\n", context=context) == expected_extract_csv
    assert budget.truncated is False
