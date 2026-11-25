# Copyright (c) 2026 Nikolai Zelensky

"""Tests for document engine result."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import audiodoc.document_engine.result as result_module
from audiodoc.document_engine.result import build_result, limit_text


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

    result = build_result("txt", "\tЁжик\n", truncated=True)

    expected_result = {
        "format": "txt",
        "text": "Ёжик",
        "characters": 4,
        "truncated": True,
    }
    assert result == expected_result, "the result does not have the response shape"


@given(
    text=st.text(max_size=8192),
    truncated=st.booleans(),
)
@settings(max_examples=200)
def test_document_text_normalization_is_idempotent(
    text: str,
    *,
    truncated: bool,
) -> None:
    first = build_result("txt", text, truncated=truncated)
    second = build_result(
        first["format"],
        first["text"],
        truncated=first["truncated"],
    )

    assert second == first, "normalizing a normalized result changed it"
