# Copyright (c) 2026 Nikolai Zelensky
"""Tests for log-safe rendering of untrusted values."""

from audiodoc.common.safe_log import log_safe


def test_log_safe_removes_line_breaks_and_non_printable_characters() -> None:
    expected = "user\\nname\\r?"

    value = log_safe("user\nname\r\x00", limit=30)

    assert value == expected, "line breaks or control characters were kept"
