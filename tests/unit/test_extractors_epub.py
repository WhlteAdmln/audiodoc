# Copyright (c) 2026 Nikolai Zelensky
"""Изолированные тесты EPUB-экстрактора (этап A4)."""

from backend.document_engine.extractors.epub import extract_epub
from tests.builders import create_epub


def test_epub_extracts_chapter_content_and_skips_navigation():
    text = extract_epub(create_epub())

    assert "EPUB test" in text
    assert "Document engine works!" in text
