# Copyright (c) 2026 Nikolai Zelensky

"""Tests for extractors plain."""

from audiodoc.document_engine.extractors.plain import extract_plain


def test_plain_extracts_utf8_and_removes_bom() -> None:
    assert extract_plain(b"\xef\xbb\xbfHello\nworld") == "Hello\nworld"


def test_plain_replaces_invalid_utf8_bytes() -> None:
    assert extract_plain(b"hello\xffworld") == "hello\ufffdworld"
