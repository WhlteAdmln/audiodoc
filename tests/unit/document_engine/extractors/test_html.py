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

    visible_heading = "Visible"
    assert visible_heading in text
    visible_text = "Text"
    assert visible_text in text
    script_text = "secret"
    assert script_text not in text
    noscript_text = "fallback"
    assert noscript_text not in text
    style_rule = ".hidden"
    assert style_rule not in text
