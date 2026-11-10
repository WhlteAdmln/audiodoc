# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the O(1)-per-chunk output budget."""

import pytest

from audiodoc.common.text_budget import TextBudget


def test_text_budget_truncates_a_single_oversized_chunk():
    budget = TextBudget(10)
    assert budget.add("a" * 20) == "a" * 10
    assert budget.used == 10
    assert budget.exhausted is True
    assert budget.truncated is True


def test_text_budget_accounts_for_newline_between_chunks():
    budget = TextBudget(5)
    parts = [budget.add("abc"), budget.add("def")]
    assert "\n".join(part for part in parts if part) == "abc\nd"
    assert budget.used == 5
    assert budget.exhausted is True


def test_text_budget_rejects_invalid_limits_and_chunks():
    with pytest.raises(ValueError, match="limit must be a positive integer"):
        TextBudget(0)
    with pytest.raises(TypeError, match="text must be a string"):
        TextBudget(5).add(b"bytes")  # type: ignore[arg-type]


def test_text_budget_is_not_truncated_when_text_exactly_fits():
    budget = TextBudget(5)

    assert budget.add("12345") == "12345"
    assert budget.used == 5
    assert budget.exhausted is True
    assert budget.truncated is False


def test_text_budget_is_truncated_when_text_exceeds_limit_by_one():
    budget = TextBudget(5)

    assert budget.add("123456") == "12345"
    assert budget.used == 5
    assert budget.exhausted is True
    assert budget.truncated is True


def test_text_budget_can_mark_source_as_incomplete_when_extraction_stops():
    budget = TextBudget(5)
    budget.add("12345")

    budget.mark_truncated()

    assert budget.exhausted is True
    assert budget.truncated is True
