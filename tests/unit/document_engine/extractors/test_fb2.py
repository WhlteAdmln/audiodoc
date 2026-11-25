# Copyright (c) 2026 Nikolai Zelensky
"""Unit tests for the FB2 extractor."""

import pytest

from audiodoc.document_engine.extractors.fb2 import extract_fb2
from audiodoc.document_engine.limits import MAX_EXTRACTED_TEXT_LENGTH
from audiodoc.errors.documents import DocumentRejectedError
from tests.support.builders import create_fb2


def test_fb2_extracts_titles_paragraphs_and_nested_text() -> None:
    text = extract_fb2(create_fb2())

    expected_text = "FB2 test\nDocument engine works!\nText with emphasis preserved."
    assert text == expected_text, "titles, paragraphs or nested text were lost"


def test_fb2_without_body_is_rejected() -> None:
    data = b"<FictionBook><description /></FictionBook>"

    with pytest.raises(DocumentRejectedError) as caught:
        extract_fb2(data)

    expected_message = "\u0412 FB2 не найдено содержимое книги"
    assert str(caught.value) == expected_message, "FB2 without a body was accepted"


def test_fb2_result_respects_global_text_limit() -> None:
    data = (
        b"<FictionBook><body><section><p>"
        + b"x" * (MAX_EXTRACTED_TEXT_LENGTH + 100)
        + b"</p></section></body></FictionBook>"
    )

    text = extract_fb2(data)

    expected_text = "x" * MAX_EXTRACTED_TEXT_LENGTH
    assert text == expected_text, "the FB2 text exceeds the global limit"


def test_fb2_rejects_entity_declarations() -> None:
    data = (
        b'<!DOCTYPE FictionBook [<!ENTITY x "expanded">]>'
        b"<FictionBook><body><section><p>&x;</p></section></body></FictionBook>"
    )

    with pytest.raises(DocumentRejectedError) as caught:
        extract_fb2(data)

    expected_message = "XML содержит запрещённые конструкции"
    assert str(caught.value) == expected_message, "FB2 entities were not rejected"
