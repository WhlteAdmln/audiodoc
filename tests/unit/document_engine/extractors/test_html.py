# Copyright (c) 2026 Nikolai Zelensky

"""Tests for extractors html."""

import pytest

from audiodoc.document_engine.extractors.html import extract_html


@pytest.fixture(name="extracted_text")
def fixture_extracted_text() -> str:
    """Extract text from a page with content and non-content elements."""
    data = (
        b"<html><body><h1>Visible</h1><script>secret()</script>"
        b"<style>.hidden{}</style><noscript>fallback</noscript>"
        b"<p>Text</p></body></html>"
    )
    return extract_html(data)


@pytest.mark.parametrize("visible_text", ["Visible", "Text"])
def test_html_keeps_content_elements(extracted_text: str, visible_text: str) -> None:
    assert visible_text in extracted_text, f"content text {visible_text!r} is missing"


@pytest.mark.parametrize("hidden_text", ["secret", "fallback", ".hidden"])
def test_html_removes_non_content_elements(
    extracted_text: str,
    hidden_text: str,
) -> None:
    assert hidden_text not in extracted_text, (
        f"non-content text {hidden_text!r} was extracted"
    )
