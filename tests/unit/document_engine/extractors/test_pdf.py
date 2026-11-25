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


@pytest.fixture(name="ocr_page")
def fixture_ocr_page(monkeypatch: pytest.MonkeyPatch) -> FakePage:
    """Open a one-page PDF without a text layer whose OCR returns padded text."""
    page = FakePage()
    document = FakeDocument([page])
    monkeypatch.setattr(pdf_module.pymupdf, "open", lambda **_kwargs: document)
    monkeypatch.setattr(
        pdf_module,
        "extract_image_text",
        lambda _image_data, **_kwargs: " OCR result ",
    )
    return page


@pytest.mark.parametrize(
    "expected_fragment",
    ["--- Страница 1 ---", "PDF document test"],
)
def test_pdf_extracts_existing_text_layer(expected_fragment: str) -> None:
    text = extract_pdf(create_pdf())

    assert expected_fragment in text, "the text layer and its page header must remain"


@pytest.mark.usefixtures("ocr_page")
def test_pdf_uses_ocr_for_page_without_text_layer() -> None:
    text = extract_pdf(b"fake-pdf")

    expected_text = "--- Страница 1 ---\nOCR result"
    assert text == expected_text, "a page without a text layer must be recognized"


def test_pdf_renders_page_without_text_layer_at_default_dpi(
    ocr_page: FakePage,
) -> None:
    extract_pdf(b"fake-pdf")

    expected_render_arguments = {"dpi": 200, "alpha": False}
    assert ocr_page.render_arguments == expected_render_arguments, (
        "an A4 page must be rendered at the default DPI"
    )


def test_pdf_rejects_too_many_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    document = FakeDocument([], page_count=MAX_DOCUMENT_PAGES + 1)
    monkeypatch.setattr(pdf_module.pymupdf, "open", lambda **_kwargs: document)

    with pytest.raises(DocumentRejectedError) as error:
        extract_pdf(b"fake-pdf")

    expected_message = "\u0412 PDF слишком много страниц"
    assert str(error.value) == expected_message, (
        "a PDF over the page limit must be rejected"
    )


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
    with pytest.raises(DocumentRejectedError) as error:
        extract_pdf(b"%PDF-giant")
    expected_message = "Страница PDF слишком велика для безопасного OCR"
    assert str(error.value) == expected_message, (
        "a page too large for the minimum DPI must be rejected"
    )


def test_pdf_marks_output_incomplete_when_pages_remain_after_exact_fit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = FakeDocument([FakePage("Пролог\tI"), FakePage("Epilogue ii")])
    monkeypatch.setattr(pdf_module.pymupdf, "open", lambda **_kwargs: document)
    first_page_text = "--- Страница 1 ---\nПролог\tI"
    budget = TextBudget(len(first_page_text))
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    text = extract_pdf(b"fake-pdf", context=context)

    expected_result = (first_page_text, True)
    assert (text, budget.truncated) == expected_result, (
        "the first page must fill the budget and the remaining page must truncate it"
    )


def test_pdf_exact_fit_on_last_page_is_not_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = FakeDocument([FakePage("Kapitel ZWÖLF")])
    monkeypatch.setattr(pdf_module.pymupdf, "open", lambda **_kwargs: document)
    first_page_text = "--- Страница 1 ---\nKapitel ZWÖLF"
    budget = TextBudget(len(first_page_text))
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    text = extract_pdf(b"fake-pdf", context=context)

    expected_result = (first_page_text, False)
    assert (text, budget.truncated) == expected_result, (
        "a last page that exactly fits must be complete and not truncated"
    )
