# Copyright (c) 2026 Nikolai Zelensky
"""Isolated tests for the EPUB extractor (A4 stage)."""

import pytest

from audiodoc.document_engine.extractors.epub import extract_epub
from tests.support.builders import create_epub


@pytest.mark.parametrize("fragment", ["EPUB test", "Document engine works!"])
def test_epub_extracts_chapter_content_and_skips_navigation(fragment: str) -> None:
    text = extract_epub(create_epub())

    assert fragment in text, "the chapter content is missing"
