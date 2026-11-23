# Copyright (c) 2026 Nikolai Zelensky

"""Tests for extractors html."""

from audiodoc.document_engine.extractors.html import extract_html


def test_html_removes_non_content_elements() -> None:
    data = (
        b"<html><body><h1>Visible</h1><script>secret()</script>"
        b"<style>.hidden{}</style><noscript>fallback</noscript>"
        b"<p>Text</p></body></html>"
    )
    text = extract_html(data)

    assert "Visible" in text
    assert "Text" in text
    assert "secret" not in text
    assert "fallback" not in text
    assert ".hidden" not in text
