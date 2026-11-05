"""Изолированные тесты PDF-экстрактора (этап A4)."""

from types import SimpleNamespace

import pytest

import backend.document_engine.extractors.pdf as pdf_module
from backend.document_engine.limits import MAX_DOCUMENT_PAGES
from backend.document_engine.extractors.pdf import extract_pdf
from backend.errors.documents import DocumentRejectedError
from tests.builders import create_pdf


class _FakePixmap:
    def tobytes(self, image_format: str) -> bytes:
        assert image_format == "png"
        return b"fake-png"


class _FakePage:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.render_arguments = None
        self.rect = SimpleNamespace(width=595.276, height=841.89)

    def get_text(self, kind: str) -> str:
        assert kind == "text"
        return self.text

    def get_pixmap(self, **kwargs):
        self.render_arguments = kwargs
        return _FakePixmap()


class _FakeDocument:
    def __init__(self, pages, page_count=None) -> None:
        self.pages = pages
        self.page_count = len(pages) if page_count is None else page_count

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def __iter__(self):
        return iter(self.pages)


def test_pdf_extracts_existing_text_layer():
    text = extract_pdf(create_pdf())

    assert "--- Страница 1 ---" in text
    assert "PDF document test" in text


def test_pdf_uses_ocr_for_page_without_text_layer(monkeypatch):
    page = _FakePage()
    document = _FakeDocument([page])
    monkeypatch.setattr(pdf_module.pymupdf, "open", lambda **_kwargs: document)
    monkeypatch.setattr(
        pdf_module,
        "extract_image_text",
        lambda image_data, **_kwargs: " OCR result ",
    )

    text = extract_pdf(b"fake-pdf")

    assert text == "--- Страница 1 ---\nOCR result"
    assert page.render_arguments == {"dpi": 200, "alpha": False}


def test_pdf_rejects_too_many_pages(monkeypatch):
    document = _FakeDocument([], page_count=MAX_DOCUMENT_PAGES + 1)
    monkeypatch.setattr(pdf_module.pymupdf, "open", lambda **_kwargs: document)

    with pytest.raises(
        DocumentRejectedError,
        match="В PDF слишком много страниц",
    ):
        extract_pdf(b"fake-pdf")


def test_pdf_render_dpi_is_reduced_for_oversized_page():
    page = _FakePage()
    page.rect = SimpleNamespace(width=200 * 72, height=200 * 72)
    assert pdf_module._render_dpi(page) == 31


def test_pdf_rejects_page_that_cannot_fit_even_at_minimum_dpi():
    from backend.errors.documents import DocumentRejectedError

    page = _FakePage()
    page.rect = SimpleNamespace(width=1000 * 72, height=1000 * 72)
    with pytest.raises(DocumentRejectedError, match="слишком велика"):
        pdf_module._render_dpi(page)
