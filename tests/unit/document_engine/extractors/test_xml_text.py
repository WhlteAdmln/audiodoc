# Copyright (c) 2026 Nikolai Zelensky

"""Tests for extractors xml text."""

import pytest

from audiodoc.common import deadline as deadline_module
from audiodoc.common.deadline import Deadline, DeadlineExceededError
from audiodoc.common.text_budget import TextBudget
from audiodoc.document_engine.extractors.base import ExtractContext
from audiodoc.document_engine.extractors.xml_text import extract_xml_text
from audiodoc.errors.documents import DocumentRejectedError
from tests.support.clock import FakeMonotonicClock


def _limited_context(limit: int) -> ExtractContext:
    return ExtractContext(budget=TextBudget(limit), deadline=Deadline(10))


def test_extracts_element_text_in_document_order() -> None:
    data = b"<root>root text<child>child text</child></root>"

    text = extract_xml_text(data)

    expected_text = "root text\nchild text"
    assert text == expected_text, "element text is missing or out of order"


def test_keeps_tail_text_after_a_child_element() -> None:
    data = b"<note><em>Grieg</em> wrote it in 1874</note>"

    text = extract_xml_text(data)

    expected_text = "Grieg\nwrote it in 1874"
    assert text == expected_text, "tail text after a child element was dropped"


def test_orders_nested_tail_text_after_the_inner_elements() -> None:
    data = b"<p>Os<q>Bergen<i>7th</i>fjord</q>Troldhaugen</p>"

    text = extract_xml_text(data)

    expected_text = "Os\nBergen\n7th\nfjord\nTroldhaugen"
    assert text == expected_text, "nested tail text is out of document order"


def test_skips_comments_instructions_and_blank_nodes_but_keeps_cdata() -> None:
    data = (
        b"<r><?php system('id'); ?><!-- \xd0\xbf\xd0\xb0\xd1\x80\xd0\xbe\xd0\xbb\xd1"
        b"\x8c -->\xd1\x82\xd0\xb5\xd0\xba\xd1\x81\xd1\x82<![CDATA[<b>]]>"
        b"<e>\n\t </e></r>"
    )

    text = extract_xml_text(data)

    expected_text = "текст<b>"
    assert text == expected_text, "markup other than text reached the result"


def test_reads_deeply_nested_elements() -> None:
    depth = 20_000
    data = b"<a>" * depth + b"deep" + b"</a>" * depth

    text = extract_xml_text(data)

    expected_text = "deep"
    assert text == expected_text, "deep nesting broke extraction"


def test_rejects_entity_declarations() -> None:
    data = b'<!DOCTYPE root [<!ENTITY x "expanded">]><root>&x;</root>'

    with pytest.raises(DocumentRejectedError) as caught:
        extract_xml_text(data)

    expected_message = "XML содержит запрещённые конструкции"
    assert str(caught.value) == expected_message, "entities were not rejected"


def test_stops_at_an_exact_fit_when_another_text_node_follows() -> None:
    context = _limited_context(3)

    data = "<root>Мир<child>Welt</child></root>".encode()

    text = extract_xml_text(data, context=context)

    expected_text = "Мир"
    assert text == expected_text, "text beyond the budget was returned"


def test_marks_truncation_when_another_text_node_follows_an_exact_fit() -> None:
    context = _limited_context(3)

    extract_xml_text("<корень>Ära<z>zwölf</z></корень>".encode(), context=context)

    assert context.budget.truncated is True, "the omitted node was not reported"


def test_exact_fit_without_more_text_is_not_truncated() -> None:
    context = _limited_context(3)

    extract_xml_text(b"<root>abc</root>", context=context)

    assert context.budget.truncated is False, "a complete document was truncated"


def test_stops_when_the_deadline_has_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = FakeMonotonicClock()
    monkeypatch.setattr(deadline_module, "time", clock)
    context = ExtractContext(budget=TextBudget(100), deadline=Deadline(1))
    clock.advance(1.5)

    with pytest.raises(DeadlineExceededError) as caught:
        extract_xml_text(b"<root>late</root>", context=context)

    expected_message = "processing deadline exceeded"
    assert str(caught.value) == expected_message, "the expired deadline was ignored"
