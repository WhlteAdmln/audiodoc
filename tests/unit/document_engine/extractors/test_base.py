# Copyright (c) 2026 Nikolai Zelensky

"""Tests for the shared extractor helpers."""

from hypothesis import given
from hypothesis import strategies as st

from audiodoc.common.deadline import Deadline
from audiodoc.common.text_budget import TextBudget
from audiodoc.document_engine.extractors.base import ExtractContext, add_rows


@given(
    rows=st.lists(st.text(max_size=12), max_size=40),
    max_rows=st.integers(min_value=1, max_value=30),
)
def test_add_rows_never_adds_more_than_max_rows(rows: list[str], max_rows: int) -> None:
    budget_limit = 9_973
    deadline_seconds = 47
    context = ExtractContext(TextBudget(budget_limit), Deadline(deadline_seconds))
    chunks: list[str] = []

    add_rows(chunks, context, rows, str, max_rows=max_rows)

    assert len(chunks) <= max_rows, "more rows were added than the row cap allows"
