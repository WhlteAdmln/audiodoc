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


class _FakePixmap:
    @staticmethod
    def tobytes(image_format: str) -> bytes:
        """Provide the ``tobytes`` behaviour the test relies on."""
        expected_image_format = "png"
        assert image_format == expected_image_format
        return b"fake-png"


class _FakePage:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.render_arguments = None
        self.rect = SimpleNamespace(width=595.276, height=841.89)

    def get_text(self, kind: str) -> str:
        """Provide the ``get_text`` behaviour the test relies on."""
        expected_kind = "text"
        assert kind == expected_kind
        return self.text

    def get_pixmap(self, **kwargs: object) -> object:
        """Provide the ``get_pixmap`` behaviour the test relies on."""
        self.render_arguments = kwargs
        return _FakePixmap()


class _FakeDocument:
    def __init__(self, pages: object, page_count: object | None = None) -> None:
        self.pages = pages
        self.page_count = len(pages) if page_count is None else page_count

    def __enter__(self) -> object:
        return self

    def __exit__(self, *_args: object) -> object:
        return False

    def __iter__(self) -> object:
        return iter(self.pages)


def test_pdf_extracts_existing_text_layer() -> None:
    text = extract_pdf(create_pdf())

    expected_fragment = "--- Страница 1 ---"
    assert expected_fragment in text
    expected_fragment = "PDF document test"
    assert expected_fragment in text


def test_pdf_uses_ocr_for_page_without_text_layer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = _FakePage()
    document = _FakeDocument([page])
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
    document = _FakeDocument([], page_count=MAX_DOCUMENT_PAGES + 1)
    monkeypatch.setattr(pdf_module.pymupdf, "open", lambda **_kwargs: document)

    with pytest.raises(
        DocumentRejectedError,
        match="\u0412 PDF слишком много страниц",
    ):
        extract_pdf(b"fake-pdf")


def test_pdf_render_dpi_is_reduced_for_oversized_page() -> None:
    # pylint: disable=protected-access  # the DPI fallback has no public seam
    page = _FakePage()
    page.rect = SimpleNamespace(width=200 * 72, height=200 * 72)
    expected_render_dpi = 31
    assert pdf_module._render_dpi(page) == expected_render_dpi  # noqa: SLF001


def test_pdf_rejects_page_that_cannot_fit_even_at_minimum_dpi() -> None:
    # pylint: disable=protected-access  # the DPI fallback has no public seam
    page = _FakePage()
    page.rect = SimpleNamespace(width=1000 * 72, height=1000 * 72)
    with pytest.raises(DocumentRejectedError, match="слишком велика"):
        pdf_module._render_dpi(page)  # noqa: SLF001


def test_pdf_marks_output_incomplete_when_pages_remain_after_exact_fit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _FakeDocument([_FakePage("abc"), _FakePage("def")])
    monkeypatch.setattr(pdf_module.pymupdf, "open", lambda **_kwargs: document)
    first_page_text = "--- Страница 1 ---\nabc"
    budget = TextBudget(len(first_page_text))
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    assert extract_pdf(b"fake-pdf", context=context) == first_page_text
    assert budget.truncated is True


def test_pdf_exact_fit_on_last_page_is_not_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _FakeDocument([_FakePage("abc")])
    monkeypatch.setattr(pdf_module.pymupdf, "open", lambda **_kwargs: document)
    first_page_text = "--- Страница 1 ---\nabc"
    budget = TextBudget(len(first_page_text))
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    assert extract_pdf(b"fake-pdf", context=context) == first_page_text
    assert budget.truncated is False
