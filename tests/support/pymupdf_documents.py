# Copyright (c) 2026 Nikolai Zelensky
"""Fake PyMuPDF documents, pages and pixmaps for PDF extraction tests."""

from collections.abc import Iterator, Sequence
from types import SimpleNamespace
from typing import Self


class FakePixmap:
    """Return fixed bytes for a rendered page."""

    @staticmethod
    def tobytes(image_format: str) -> bytes:
        """Return placeholder PNG bytes and accept only the PNG format."""
        expected_image_format = "png"
        assert image_format == expected_image_format
        return b"fake-png"


class FakePage:
    """Return a text layer and remember the arguments used to render the page."""

    def __init__(self, text: str = "") -> None:
        """Store the text layer of an A4 page."""
        self.text = text
        self.render_arguments: dict[str, object] | None = None
        self.rect = SimpleNamespace(width=595.276, height=841.89)

    def get_text(self, kind: str) -> str:
        """Return the text layer and accept only plain text extraction."""
        expected_kind = "text"
        assert kind == expected_kind
        return self.text

    def get_pixmap(self, **kwargs: object) -> FakePixmap:
        """Record the render arguments and return a fake pixmap."""
        self.render_arguments = kwargs
        return FakePixmap()


class HugePdfPage:
    """Describe a page too large to render, with an empty text layer."""

    rect = SimpleNamespace(width=72_000.0, height=72_000.0)

    @staticmethod
    def get_pixmap(**_kwargs: object) -> None:
        """Fail because a page this large must never be rendered."""
        raise AssertionError

    @staticmethod
    def get_text(kind: str) -> str:
        """Return an empty text layer and accept only plain text extraction."""
        expected_kind = "text"
        assert kind == expected_kind
        return ""


class FakeDocument:
    """Iterate over the given pages and report a page count."""

    def __init__(self, pages: Sequence[object], page_count: int | None = None) -> None:
        """Store the pages and the page count, which defaults to their number."""
        self.pages = pages
        self.page_count = len(pages) if page_count is None else page_count

    def __enter__(self) -> Self:
        """Return the document itself."""
        return self

    def __exit__(self, *_args: object) -> bool:
        """Leave exceptions to the caller."""
        return False

    def __iter__(self) -> Iterator[object]:
        """Iterate over the pages."""
        return iter(self.pages)
