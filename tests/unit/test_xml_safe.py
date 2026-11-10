# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the hardened XML parser used by XML and FB2 extractors."""

import pytest

from audiodoc.document_engine.extractors.fb2 import extract_fb2
from audiodoc.document_engine.extractors.xml_text import extract_xml_text
from audiodoc.document_engine.guards.xml_safe import parse_xml
from audiodoc.errors.documents import DocumentRejectedError


@pytest.mark.parametrize(
    "payload",
    [
        b'<!DOCTYPE root [<!ENTITY x "expanded">]><root>&x;</root>',
        b'<!DOCTYPE FictionBook SYSTEM "file:///etc/passwd"><FictionBook/>',
    ],
)
def test_safe_parser_rejects_dtd_and_entity_declarations(payload):
    with pytest.raises(
        DocumentRejectedError, match="XML содержит запрещённые конструкции"
    ):
        parse_xml(payload)


def test_safe_parser_accepts_regular_xml():
    root = parse_xml(b"<?xml version='1.0'?><root><item>safe</item></root>")
    assert root.tag == "root"
    assert root.findtext("item") == "safe"


def test_safe_parser_maps_malformed_xml_to_safe_error():
    with pytest.raises(DocumentRejectedError, match="Некорректный XML-документ"):
        parse_xml(b"<root><unclosed></root>")


def test_xml_and_fb2_extractors_use_safe_parser():
    xml = b'<!DOCTYPE root [<!ENTITY x "expanded">]><root>&x;</root>'
    fb2 = (
        b'<!DOCTYPE FictionBook [<!ENTITY x "expanded">]>'
        b"<FictionBook><body><section><p>&x;</p></section></body></FictionBook>"
    )
    with pytest.raises(DocumentRejectedError):
        extract_xml_text(xml)
    with pytest.raises(DocumentRejectedError):
        extract_fb2(fb2)
