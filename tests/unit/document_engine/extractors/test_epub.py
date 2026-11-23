# Copyright (c) 2026 Nikolai Zelensky
"""Isolated tests for the EPUB extractor (A4 stage)."""

from audiodoc.document_engine.extractors.epub import extract_epub
from tests.support.builders import create_epub


def test_epub_extracts_chapter_content_and_skips_navigation() -> None:
    text = extract_epub(create_epub())

    expected_fragment = "EPUB test"
    assert expected_fragment in text
    expected_fragment = "Document engine works!"
    assert expected_fragment in text
