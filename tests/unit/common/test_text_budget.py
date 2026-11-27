# Copyright (c) 2026 Nikolai Zelensky

"""Tests for common text budget."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from audiodoc.common.text_budget import StopReason, TextBudget


@given(
    limit=st.integers(min_value=1, max_value=1024),
    chunks=st.lists(st.text(max_size=256), max_size=16),
    separator_length=st.integers(min_value=0, max_value=8),
)
@settings(max_examples=200)
def test_text_budget_never_exceeds_limit(
    limit: int,
    chunks: list[str],
    separator_length: int,
) -> None:
    budget = TextBudget(limit)
    overruns: list[int] = []

    for chunk in chunks:
        budget.add(chunk, separator_length=separator_length)
        if budget.used > limit:
            overruns.append(budget.used)

    expected_empty: list[int] = []
    assert overruns == expected_empty, "the budget must never use more than its limit"


@given(
    limit=st.integers(min_value=1, max_value=1024),
    chunks=st.lists(st.text(max_size=256), max_size=16),
    separator_length=st.integers(min_value=0, max_value=8),
)
@settings(max_examples=200)
def test_text_budget_reports_exact_truncation(
    limit: int,
    chunks: list[str],
    separator_length: int,
) -> None:
    budget = TextBudget(limit)
    truncated_so_far = False
    expected_flags: list[bool] = []
    reported_flags: list[bool] = []

    for chunk in chunks:
        piece = budget.add(chunk, separator_length=separator_length)
        truncated_so_far = truncated_so_far or len(piece) < len(chunk)
        expected_flags.append(truncated_so_far)
        reported_flags.append(budget.truncated)

    assert reported_flags == expected_flags, (
        "the truncation flag must turn on exactly when a chunk is cut"
    )


@given(
    limit=st.integers(min_value=1, max_value=256),
    chunks=st.lists(
        st.tuples(st.text(max_size=64), st.integers(min_value=0, max_value=6)),
        max_size=24,
    ),
)
@settings(max_examples=200)
def test_text_budget_keeps_joined_text_within_limit_for_any_separators(
    limit: int,
    chunks: list[tuple[str, int]],
) -> None:
    budget = TextBudget(limit)
    joined = ""

    for text, separator_length in chunks:
        piece = budget.add(text, separator_length=separator_length)
        if piece and joined:
            joined += "¶" * separator_length
        joined += piece

    assert len(joined) <= limit, "the accepted text with separators exceeds the limit"


@given(
    limit=st.integers(min_value=1, max_value=128),
    operations=st.lists(
        st.one_of(
            st.tuples(st.text(max_size=48), st.integers(min_value=0, max_value=4)),
            st.sampled_from([StopReason.TEXT_LIMIT, StopReason.PAGE_LIMIT]),
        ),
        max_size=24,
    ),
)
@settings(max_examples=200)
def test_text_budget_reports_truncation_exactly_when_it_has_a_stop_reason(
    limit: int,
    operations: list[tuple[str, int] | StopReason],
) -> None:
    budget = TextBudget(limit)
    reported_flags: list[bool] = []
    expected_flags: list[bool] = []

    for operation in operations:
        if isinstance(operation, StopReason):
            budget.mark_truncated(operation)
        else:
            budget.add(operation[0], separator_length=operation[1])
        reported_flags.append(budget.truncated)
        expected_flags.append(budget.stop_reason is not StopReason.NONE)

    assert reported_flags == expected_flags, (
        "the truncation flag disagrees with the stop reason"
    )


def test_text_budget_truncates_a_single_oversized_chunk() -> None:
    budget = TextBudget(10)
    expected_piece = "Длинный_те"
    assert budget.add("Длинный_текст №20!!") == expected_piece, (
        "an oversized chunk must be cut to the limit"
    )


def test_text_budget_is_full_and_truncated_after_an_oversized_chunk() -> None:
    budget = TextBudget(10)
    budget.add("Длинный_текст №20!!")
    expected_state = (10, True, True)
    assert (budget.used, budget.exhausted, budget.truncated) == expected_state, (
        "a cut chunk must fill the budget and mark it truncated"
    )


def test_text_budget_accounts_for_newline_between_chunks() -> None:
    budget = TextBudget(5)
    parts = [budget.add("Чай"), budget.add("Tee!")]
    expected_text = "Чай\nT"
    assert "\n".join(part for part in parts if part) == expected_text, (
        "the newline between chunks must count towards the limit"
    )


def test_text_budget_is_full_after_chunks_with_newline_reach_limit() -> None:
    budget = TextBudget(5)
    budget.add("Чай")
    budget.add("Tee!")
    expected_state = (5, True)
    assert (budget.used, budget.exhausted) == expected_state, (
        "chunks and the newline between them must fill the budget"
    )


def test_text_budget_rejects_non_positive_limit() -> None:
    with pytest.raises(ValueError, match="limit must be") as error:
        TextBudget(0)
    expected_message = "limit must be a positive integer"
    assert str(error.value) == expected_message, "a zero limit must be rejected"


def test_text_budget_rejects_non_string_chunk() -> None:
    with pytest.raises(TypeError, match="text must be") as error:
        TextBudget(5).add(b"bytes")  # type: ignore[arg-type]  # wrong type on purpose
    expected_message = "text must be a string"
    assert str(error.value) == expected_message, "a bytes chunk must be rejected"


def test_text_budget_returns_text_that_exactly_fits() -> None:
    budget = TextBudget(5)

    expected_add = "12345"
    assert budget.add("12345") == expected_add, (
        "text that exactly fits must be accepted whole"
    )


def test_text_budget_is_not_truncated_when_text_exactly_fits() -> None:
    budget = TextBudget(5)
    budget.add("12345")

    expected_state = (5, True, False)
    assert (budget.used, budget.exhausted, budget.truncated) == expected_state, (
        "text that exactly fits must fill the budget without truncation"
    )


def test_text_budget_cuts_text_that_exceeds_limit_by_one() -> None:
    budget = TextBudget(5)

    expected_add = "12345"
    assert budget.add("123456") == expected_add, (
        "text one character over the limit must lose its last character"
    )


def test_text_budget_is_truncated_when_text_exceeds_limit_by_one() -> None:
    budget = TextBudget(5)
    budget.add("123456")

    expected_state = (5, True, True)
    assert (budget.used, budget.exhausted, budget.truncated) == expected_state, (
        "text one character over the limit must fill the budget and truncate"
    )


def test_text_budget_can_mark_source_as_incomplete_when_extraction_stops() -> None:
    budget = TextBudget(5)
    budget.add("12345")

    budget.mark_truncated(StopReason.PAGE_LIMIT)

    expected_state = (True, True)
    assert (budget.exhausted, budget.truncated) == expected_state, (
        "a marked budget must stay full and become truncated"
    )


def test_text_budget_has_no_stop_reason_when_text_fits() -> None:
    budget = TextBudget(12)
    budget.add("Окно 3")

    assert budget.stop_reason is StopReason.NONE, "a fitting chunk set a stop reason"


def test_text_budget_records_text_limit_when_a_chunk_is_cut() -> None:
    budget = TextBudget(4)
    budget.add("Brücke-77")

    assert budget.stop_reason is StopReason.TEXT_LIMIT, "a cut chunk was not recorded"


def test_text_budget_records_text_limit_when_a_chunk_follows_a_full_budget() -> None:
    budget = TextBudget(3)
    budget.add("Ёлк")
    budget.add("z9")

    assert budget.stop_reason is StopReason.TEXT_LIMIT, "a dropped chunk was missed"


def test_text_budget_records_page_limit_when_marked() -> None:
    budget = TextBudget(6)
    budget.add("Лист_1")

    budget.mark_truncated(StopReason.PAGE_LIMIT)

    assert budget.stop_reason is StopReason.PAGE_LIMIT, "the page limit was not kept"


def test_text_budget_keeps_the_first_stop_reason() -> None:
    budget = TextBudget(2)
    budget.add("Qwerty")

    budget.mark_truncated(StopReason.PAGE_LIMIT)

    assert budget.stop_reason is StopReason.TEXT_LIMIT, "a later reason replaced it"


def test_text_budget_rejects_marking_without_a_stop_reason() -> None:
    budget = TextBudget(8)
    with pytest.raises(ValueError, match="reason must") as error:
        budget.mark_truncated(StopReason.NONE)
    expected_message = "reason must name the limit that stopped extraction"
    assert str(error.value) == expected_message, "an empty stop reason was accepted"
