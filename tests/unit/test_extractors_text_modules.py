"""Изолированные unit-тесты экстракторов текстовых форматов этапа A4."""

import pytest

from backend.document_engine.extractors.csv_text import extract_csv
from backend.document_engine.extractors.html import extract_html
from backend.document_engine.extractors.plain import extract_plain
from backend.document_engine.extractors.xml_text import extract_xml_text


def test_plain_extracts_utf8_and_removes_bom():
    assert extract_plain(b"\xef\xbb\xbfHello\nworld") == "Hello\nworld"


def test_plain_replaces_invalid_utf8_bytes():
    assert extract_plain(b"hello\xffworld") == "hello\ufffdworld"


def test_html_removes_non_content_elements():
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


def test_xml_extracts_element_text_in_document_order():
    data = b"<root>root text<child>child text</child></root>"
    assert extract_xml_text(data) == "root text\nchild text"


def test_csv_detects_delimiter_and_joins_cells():
    data = b"Name;Value\nDocument engine;Works!\n"
    assert extract_csv(data) == "Name | Value\nDocument engine | Works!"


def test_csv_falls_back_to_excel_dialect_when_sniffer_fails(monkeypatch):
    import backend.document_engine.extractors.csv_text as csv_module

    def fail_sniff(*_args, **_kwargs):
        raise csv_module.csv.Error("cannot determine dialect")

    monkeypatch.setattr(csv_module.csv.Sniffer, "sniff", fail_sniff)
    assert extract_csv(b"one,two\nthree,four") == "one | two\nthree | four"


def test_rtf_extractor_preserves_plain_text():
    pytest.importorskip("striprtf")
    from backend.document_engine.extractors.rtf import extract_rtf

    assert "RTF test" in extract_rtf(b"{\\rtf1 RTF test}")
