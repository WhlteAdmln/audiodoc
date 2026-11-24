# Copyright (c) 2026 Nikolai Zelensky
"""Isolated tests for the PDF extractor (A4 stage)."""

from types import SimpleNamespace

import pytest

import audiodoc.document_engine.extractors.pdf as pdf_module
from audiodoc.common.deadline import Deadline
from audiodoc.common.text_budget import TextBudget
from audiodoc.document_engine.extractors.base import ExtractContext
from audiodoc.document_engine.extractors.pdf import extract_pdf
from audiodoc.document_engine.limits import MAX_DOCUMENT_PAGES
from audiodoc.errors.documents import DocumentRejectedError
from tests.support.builders import create_pdf
from tests.support.pymupdf_documents import FakeDocument, FakePage


def test_pdf_extracts_existing_text_layer() -> None:
    text = extract_pdf(create_pdf())

    page_header = "--- Страница 1 ---"
    assert page_header in text
    page_text = "PDF document test"
    assert page_text in text


def test_pdf_uses_ocr_for_page_without_text_layer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = FakePage()
    document = FakeDocument([page])
    monkeypatch.setattr(pdf_module.pymupdf, "open", lambda **_kwargs: document)
    monkeypatch.setattr(
        pdf_module,
        "extract_image_text",
        lambda _image_data, **_kwargs: " OCR result ",
    )

    text = extract_pdf(b"fake-pdf")

    expected_text = "--- Страница 1 ---\nOCR result"
    assert text == expected_text
    assert page.render_arguments == {"dpi": 200, "alpha": False}


def test_pdf_rejects_too_many_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    document = FakeDocument([], page_count=MAX_DOCUMENT_PAGES + 1)
    monkeypatch.setattr(pdf_module.pymupdf, "open", lambda **_kwargs: document)

    with pytest.raises(
        DocumentRejectedError,
        match="\u0412 PDF слишком много страниц",
    ):
        extract_pdf(b"fake-pdf")


def test_pdf_reduces_render_dpi_for_oversized_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = FakePage()
    page.rect = SimpleNamespace(width=200 * 72, height=200 * 72)
    document = FakeDocument([page])
    monkeypatch.setattr(pdf_module.pymupdf, "open", lambda **_kwargs: document)
    monkeypatch.setattr(
        pdf_module,
        "extract_image_text",
        lambda _image_data, **_kwargs: "Скан 7",
    )
    extract_pdf(b"%PDF-oversized")
    expected_render_arguments = {"dpi": 31, "alpha": False}
    assert page.render_arguments == expected_render_arguments, (
        "an oversized page must be rendered at the reduced DPI"
    )


def test_pdf_rejects_page_that_cannot_fit_even_at_minimum_dpi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = FakePage()
    page.rect = SimpleNamespace(width=1000 * 72, height=1000 * 72)
    document = FakeDocument([page])
    monkeypatch.setattr(pdf_module.pymupdf, "open", lambda **_kwargs: document)
    with pytest.raises(DocumentRejectedError, match="слишком велика"):
        extract_pdf(b"%PDF-giant")


def test_pdf_marks_output_incomplete_when_pages_remain_after_exact_fit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = FakeDocument([FakePage("abc"), FakePage("def")])
    monkeypatch.setattr(pdf_module.pymupdf, "open", lambda **_kwargs: document)
    first_page_text = "--- Страница 1 ---\nabc"
    budget = TextBudget(len(first_page_text))
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    assert extract_pdf(b"fake-pdf", context=context) == first_page_text
    assert budget.truncated is True


def test_pdf_exact_fit_on_last_page_is_not_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = FakeDocument([FakePage("abc")])
    monkeypatch.setattr(pdf_module.pymupdf, "open", lambda **_kwargs: document)
    first_page_text = "--- Страница 1 ---\nabc"
    budget = TextBudget(len(first_page_text))
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    assert extract_pdf(b"fake-pdf", context=context) == first_page_text
    assert budget.truncated is False
