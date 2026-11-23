# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the client-facing message catalogs."""

from audiodoc.errors.messages import EXTRACTION_MESSAGES


def test_ocr_page_label_keeps_its_layout() -> None:
    expected_label = "--- Страница {index} ---\n"
    assert EXTRACTION_MESSAGES["ocr_page_label"] == expected_label, (
        "the OCR page label changed its text or trailing newline"
    )
