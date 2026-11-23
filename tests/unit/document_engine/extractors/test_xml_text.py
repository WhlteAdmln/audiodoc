# Copyright (c) 2026 Nikolai Zelensky

"""Tests for extractors xml text."""

from audiodoc.common.deadline import Deadline
from audiodoc.common.text_budget import TextBudget
from audiodoc.document_engine.extractors.base import ExtractContext
from audiodoc.document_engine.extractors.xml_text import extract_xml_text


def test_xml_extracts_element_text_in_document_order() -> None:
    data = b"<root>root text<child>child text</child></root>"
    assert extract_xml_text(data) == "root text\nchild text"


def test_xml_marks_truncation_when_another_text_node_follows_an_exact_fit() -> None:
    budget = TextBudget(3)
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    assert (
        extract_xml_text(b"<root>abc<child>def</child></root>", context=context)
        == "abc"
    )
    assert budget.truncated is True


def test_xml_exact_fit_without_more_text_is_not_truncated() -> None:
    budget = TextBudget(3)
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    assert extract_xml_text(b"<root>abc</root>", context=context) == "abc"
    assert budget.truncated is False
