# Copyright (c) 2026 Nikolai Zelensky

"""Tests for document engine result."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import audiodoc.document_engine.result as result_module
from audiodoc.common.text_budget import StopReason
from audiodoc.document_engine.result import (
    ExtractionOutcome,
    build_result,
    limit_text,
)


def test_limit_text_cuts_text_to_the_maximum_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(result_module, "MAX_EXTRACTED_TEXT_LENGTH", 5)

    text = limit_text("№7Юg≠x")

    expected_limit_text = "№7Юg≠"
    assert text == expected_limit_text, "the text was not cut to the maximum length"


def test_build_result_preserves_response_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(result_module, "MAX_EXTRACTED_TEXT_LENGTH", 5)

    outcome = ExtractionOutcome(
        format="txt", text="\tЁжик\n", stop_reason=StopReason.TEXT_LIMIT
    )

    result = build_result(outcome)

    expected_result = {
        "format": "txt",
        "text": "Ёжик",
        "characters": 4,
        "truncated": True,
    }
    assert result == expected_result, "the result does not have the response shape"


@given(
    text=st.text(max_size=8192),
    stop_reason=st.sampled_from(StopReason),
)
@settings(max_examples=200)
def test_document_text_normalization_is_idempotent(
    text: str,
    stop_reason: StopReason,
) -> None:
    first = build_result(
        ExtractionOutcome(format="txt", text=text, stop_reason=stop_reason)
    )
    second = build_result(
        ExtractionOutcome(
            format=first["format"], text=first["text"], stop_reason=stop_reason
        )
    )

    assert second == first, "normalizing a normalized result changed it"


@pytest.mark.parametrize(
    ("stop_reason", "expected_truncated"),
    [
        (StopReason.NONE, False),
        (StopReason.TEXT_LIMIT, True),
        (StopReason.PAGE_LIMIT, True),
    ],
)
def test_build_result_reports_truncation_for_a_stop_reason(
    stop_reason: StopReason,
    *,
    expected_truncated: bool,
) -> None:
    outcome = ExtractionOutcome(format="odt", text="Глава 9", stop_reason=stop_reason)

    result = build_result(outcome)

    assert result["truncated"] is expected_truncated, "truncated does not match"
