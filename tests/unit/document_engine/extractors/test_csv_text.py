# Copyright (c) 2026 Nikolai Zelensky

"""Tests for extractors csv text."""

import pytest

from audiodoc.common import deadline as deadline_module
from audiodoc.common.deadline import Deadline, DeadlineExceededError
from audiodoc.common.text_budget import TextBudget
from audiodoc.document_engine.extractors.base import ExtractContext
from audiodoc.document_engine.extractors.csv_text import extract_csv
from tests.support.clock import FakeMonotonicClock


def _limited_context(limit: int) -> ExtractContext:
    return ExtractContext(budget=TextBudget(limit), deadline=Deadline(10))


@pytest.mark.parametrize(
    ("data", "expected_text"),
    [
        (
            b"Name;Value\nDocument engine;Works!\n",
            "Name | Value\nDocument engine | Works!",
        ),
        ("Имя\tВозраст\nАня\t30\n".encode(), "Имя | Возраст\nАня | 30"),
        (b"a|b\nc|d\n", "a | b\nc | d"),
    ],
    ids=["semicolon", "tab", "pipe"],
)
def test_detects_delimiter_and_joins_cells(data: bytes, expected_text: str) -> None:
    text = extract_csv(data)

    assert text == expected_text, "cells were not split on the detected delimiter"


def test_falls_back_to_the_excel_dialect_when_no_delimiter_is_found() -> None:
    text = extract_csv("один\n".encode())

    expected_text = "один"
    assert text == expected_text, "a single column was not read"


def test_keeps_a_single_column_that_a_letter_could_split() -> None:
    text = extract_csv(b"single\ncolumn\n")

    expected_text = "single\ncolumn"
    assert text == expected_text, "a letter was used as the delimiter"


def test_strips_the_byte_order_mark() -> None:
    data = "\N{BYTE ORDER MARK}имя;значение\nа;б\n".encode()

    text = extract_csv(data)

    expected_text = "имя | значение\nа | б"
    assert text == expected_text, "the byte order mark reached the text"


def test_replaces_invalid_utf8_bytes() -> None:
    text = extract_csv(b"ok,\xff\xfe\nfine,\xc3\n")

    replacement = "\N{REPLACEMENT CHARACTER}"
    expected_text = f"ok | {replacement * 2}\nfine | {replacement}"
    assert text == expected_text, "invalid bytes were not replaced"


def test_keeps_text_of_an_unterminated_quote() -> None:
    text = extract_csv(b'a,"bc\nd\n')

    expected_text = "a | bc\nd"
    assert text == expected_text, "an unterminated quote lost text"


def test_stops_at_an_exact_fit_when_another_row_follows() -> None:
    context = _limited_context(5)

    text = extract_csv(b"a,b\nc,d\n", context=context)

    expected_text = "a | b"
    assert text == expected_text, "text beyond the budget was returned"


def test_marks_truncation_when_another_row_follows_an_exact_fit() -> None:
    context = _limited_context(5)

    extract_csv(b"a,b\nc,d\n", context=context)

    assert context.budget.truncated is True, "the omitted row was not reported"


def test_exact_fit_at_end_of_file_is_not_truncated() -> None:
    context = _limited_context(11)

    extract_csv(b"a,b\nc,d\n", context=context)

    assert context.budget.truncated is False, "a complete file was truncated"


def test_stops_when_the_deadline_has_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = FakeMonotonicClock()
    monkeypatch.setattr(deadline_module, "time", clock)
    context = ExtractContext(budget=TextBudget(100), deadline=Deadline(1))
    clock.advance(2.5)

    with pytest.raises(DeadlineExceededError) as caught:
        extract_csv(b"x,y\n1,2\n", context=context)

    expected_message = "processing deadline exceeded"
    assert str(caught.value) == expected_message, "the expired deadline was ignored"
