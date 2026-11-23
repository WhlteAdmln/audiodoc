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

    expected_fragment = "Visible"
    assert expected_fragment in text
    expected_fragment = "Text"
    assert expected_fragment in text
    expected_fragment = "secret"
    assert expected_fragment not in text
    expected_fragment = "fallback"
    assert expected_fragment not in text
    expected_fragment = ".hidden"
    assert expected_fragment not in text
