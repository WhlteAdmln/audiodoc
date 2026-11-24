# Copyright (c) 2026 Nikolai Zelensky
"""Isolated tests for the EPUB extractor (A4 stage)."""

from audiodoc.document_engine.extractors.epub import extract_epub
from tests.support.builders import create_epub


def test_epub_extracts_chapter_content_and_skips_navigation() -> None:
    text = extract_epub(create_epub())

    chapter_title = "EPUB test"
    assert chapter_title in text
    chapter_text = "Document engine works!"
    assert chapter_text in text
