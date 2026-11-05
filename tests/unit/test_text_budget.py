"""Tests for the O(1)-per-chunk output budget."""

import pytest

from backend.common.text_budget import TextBudget


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
    with pytest.raises(ValueError):
        TextBudget(0)
    with pytest.raises(TypeError):
        TextBudget(5).add(b"bytes")  # type: ignore[arg-type]
