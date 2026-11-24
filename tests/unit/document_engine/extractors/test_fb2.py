# Copyright (c) 2026 Nikolai Zelensky
"""Unit tests for the FB2 extractor."""

import pytest

from audiodoc.document_engine.extractors.fb2 import extract_fb2
from audiodoc.document_engine.limits import MAX_EXTRACTED_TEXT_LENGTH
from audiodoc.errors.documents import DocumentRejectedError
from tests.support.builders import create_fb2


def test_fb2_extracts_titles_paragraphs_and_nested_text() -> None:
    text = extract_fb2(create_fb2())

    book_title = "FB2 test"
    assert book_title in text
    paragraph = "Document engine works!"
    assert paragraph in text
    emphasized_text = "Text with emphasis preserved."
    assert emphasized_text in text


def test_fb2_without_body_is_rejected() -> None:
    data = b"<FictionBook><description /></FictionBook>"

    with pytest.raises(
        DocumentRejectedError, match="\u0412 FB2 не найдено содержимое книги"
    ):
        extract_fb2(data)


def test_fb2_result_respects_global_text_limit() -> None:
    data = (
        b"<FictionBook><body><section><p>"
        + b"x" * (MAX_EXTRACTED_TEXT_LENGTH + 100)
        + b"</p></section></body></FictionBook>"
    )

    text = extract_fb2(data)
    assert text == "x" * MAX_EXTRACTED_TEXT_LENGTH
