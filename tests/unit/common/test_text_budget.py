# Copyright (c) 2026 Nikolai Zelensky

"""Tests for common text budget."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from audiodoc.common.text_budget import TextBudget


@given(
    limit=st.integers(min_value=1, max_value=1024),
    chunks=st.lists(st.text(max_size=256), max_size=16),
    separator_length=st.integers(min_value=0, max_value=8),
)
@settings(max_examples=200)
def test_text_budget_never_exceeds_limit_and_reports_exact_truncation(
    limit: int,
    chunks: list[str],
    separator_length: int,
) -> None:
    budget = TextBudget(limit)
    truncated_so_far = False

    for chunk in chunks:
        piece = budget.add(chunk, separator_length=separator_length)
        if len(piece) < len(chunk):
            truncated_so_far = True

        assert budget.truncated is truncated_so_far
        assert budget.used <= limit


def test_text_budget_truncates_a_single_oversized_chunk() -> None:
    budget = TextBudget(10)
    expected_piece = "Длинный_те"
    assert budget.add("Длинный_текст №20!!") == expected_piece
    expected_used = 10
    assert budget.used == expected_used
    assert budget.exhausted is True
    assert budget.truncated is True


def test_text_budget_accounts_for_newline_between_chunks() -> None:
    budget = TextBudget(5)
    parts = [budget.add("Чай"), budget.add("Tee!")]
    expected_text = "Чай\nT"
    assert "\n".join(part for part in parts if part) == expected_text
    expected_used = 5
    assert budget.used == expected_used
    assert budget.exhausted is True


def test_text_budget_rejects_invalid_limits_and_chunks() -> None:
    with pytest.raises(ValueError, match="limit must be a positive integer"):
        TextBudget(0)
    with pytest.raises(TypeError, match="text must be a string"):
        TextBudget(5).add(b"bytes")  # type: ignore[arg-type]  # wrong type on purpose


def test_text_budget_is_not_truncated_when_text_exactly_fits() -> None:
    budget = TextBudget(5)

    expected_add = "12345"
    assert budget.add("12345") == expected_add
    expected_used = 5
    assert budget.used == expected_used
    assert budget.exhausted is True
    assert budget.truncated is False


def test_text_budget_is_truncated_when_text_exceeds_limit_by_one() -> None:
    budget = TextBudget(5)

    expected_add = "12345"
    assert budget.add("123456") == expected_add
    expected_used = 5
    assert budget.used == expected_used
    assert budget.exhausted is True
    assert budget.truncated is True


def test_text_budget_can_mark_source_as_incomplete_when_extraction_stops() -> None:
    budget = TextBudget(5)
    budget.add("12345")

    budget.mark_truncated()

    assert budget.exhausted is True
    assert budget.truncated is True
