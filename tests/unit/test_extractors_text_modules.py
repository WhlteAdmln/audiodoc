"""Изолированные unit-тесты экстракторов текстовых форматов этапа A4."""

from importlib import import_module

import pytest

from backend.common.deadline import Deadline
from backend.common.text_budget import TextBudget
from backend.document_engine.extractors.base import ExtractContext
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
    csv_module = import_module("backend.document_engine.extractors.csv_text")

    def fail_sniff(*_args, **_kwargs):
        raise csv_module.csv.Error

    monkeypatch.setattr(csv_module.csv.Sniffer, "sniff", fail_sniff)
    assert extract_csv(b"one,two\nthree,four") == "one | two\nthree | four"


def test_rtf_extractor_preserves_plain_text():
    pytest.importorskip("striprtf")
    rtf_module = import_module("backend.document_engine.extractors.rtf")
    assert "RTF test" in rtf_module.extract_rtf(b"{\\rtf1 RTF test}")


def test_csv_marks_truncation_when_another_row_follows_an_exact_fit(monkeypatch):
    csv_module = import_module("backend.document_engine.extractors.csv_text")
    monkeypatch.setattr(
        csv_module.csv.Sniffer, "sniff", lambda *_args, **_kwargs: csv_module.csv.excel
    )
    budget = TextBudget(3)
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    assert extract_csv(b"abc\ndef\n", context=context) == "abc"
    assert budget.truncated is True


def test_csv_exact_fit_at_end_of_file_is_not_truncated(monkeypatch):
    csv_module = import_module("backend.document_engine.extractors.csv_text")
    monkeypatch.setattr(
        csv_module.csv.Sniffer, "sniff", lambda *_args, **_kwargs: csv_module.csv.excel
    )
    budget = TextBudget(3)
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    assert extract_csv(b"abc\n", context=context) == "abc"
    assert budget.truncated is False


def test_xml_marks_truncation_when_another_text_node_follows_an_exact_fit():
    budget = TextBudget(3)
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    assert (
        extract_xml_text(b"<root>abc<child>def</child></root>", context=context)
        == "abc"
    )
    assert budget.truncated is True


def test_xml_exact_fit_without_more_text_is_not_truncated():
    budget = TextBudget(3)
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    assert extract_xml_text(b"<root>abc</root>", context=context) == "abc"
    assert budget.truncated is False
