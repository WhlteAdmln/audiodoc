# Copyright (c) 2026 Nikolai Zelensky

"""Tests for extractors plain."""

from audiodoc.document_engine.extractors.plain import extract_plain


def test_plain_extracts_utf8_and_removes_bom() -> None:
    expected_extract_plain = "Hello\nworld"
    assert extract_plain(b"\xef\xbb\xbfHello\nworld") == expected_extract_plain


def test_plain_replaces_invalid_utf8_bytes() -> None:
    expected_extract_plain = "hello\ufffdworld"
    assert extract_plain(b"hello\xffworld") == expected_extract_plain
