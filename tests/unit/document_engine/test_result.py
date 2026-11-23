# Copyright (c) 2026 Nikolai Zelensky

"""Tests for document engine result."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import audiodoc.document_engine.result as result_module
from audiodoc.document_engine.result import build_result, limit_text


def test_limit_text_and_build_result_preserve_response_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(result_module, "MAX_EXTRACTED_TEXT_LENGTH", 5)
    assert limit_text("123456") == "12345"
    assert build_result("txt", " hello ", truncated=True) == {
        "format": "txt",
        "text": "hello",
        "characters": 5,
        "truncated": True,
    }


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

    assert second == first
