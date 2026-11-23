# Copyright (c) 2026 Nikolai Zelensky

"""Tests for ocr recognize."""

from __future__ import annotations

from pathlib import Path
from typing import Never

import pytest
from PIL import Image

from audiodoc.common.subprocess_runner import (
    SubprocessTimeoutError,
)
from audiodoc.document_engine.ocr import recognize as ocr_package_recognize
from audiodoc.document_engine.ocr import recognize as recognize_module
from audiodoc.document_engine.ocr import tesseract as tesseract_module
from audiodoc.errors.documents import DocumentRejectedError


class _UnexpectedImageCopyError(AssertionError):
    """Raised when OCR copies an oversized image frame."""

    def __init__(self) -> None:
        """Initialize the test assertion error."""
        super().__init__("copy must not be called for oversized frames")


class _OversizedImage:
    n_frames = 1
    width = 100
    height = 100

    def seek(self, _index: object) -> None:
        return None

    def copy(self) -> Never:
        raise _UnexpectedImageCopyError


def test_ocr_timeout_returns_clean_error_and_removes_image_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directories: list[Path] = []

    def timeout_runner(
        args: list[str],
        *,
        timeout: float,
    ) -> tuple[int, bytes, bytes]:
        image_path = Path(args[1])
        assert image_path.is_file()
        assert args[2:] == ["stdout", "-l", "eng", "--psm", "3"]
        assert timeout > 0
        directories.append(image_path.parent)
        raise SubprocessTimeoutError

    monkeypatch.setattr(tesseract_module, "_get_tesseract_command", lambda: "tesseract")
    monkeypatch.setattr(tesseract_module, "run_limited", timeout_runner)

    with (
        Image.new("RGB", (8, 8)) as image,
        pytest.raises(DocumentRejectedError) as error,
    ):
        recognize_module.recognize_pages(image, "eng")

    assert error.value.status_code == 400
    assert directories
    assert all(not directory.exists() for directory in directories)


def test_recognize_pages_preserves_page_headers_and_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DummyPrepared:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    class DummyImage:
        n_frames = 2
        width = 10
        height = 10

        def __init__(self) -> None:
            self.current_page = None

        def seek(self, page: object) -> None:
            self.current_page = page

        def copy(self) -> object:
            return object()

    prepared_images = []
    calls = []

    def prepare(_image: object) -> object:
        item = DummyPrepared()
        prepared_images.append(item)
        return item

    def recognize(
        _image: object, *, lang: object, config: object, timeout: object
    ) -> str:
        calls.append((lang, config, timeout))
        return f" page {len(calls)} "

    monkeypatch.setattr(ocr_package_recognize, "_prepare_image", prepare)
    monkeypatch.setattr(
        ocr_package_recognize.pytesseract,
        "image_to_string",
        recognize,
    )

    text = ocr_package_recognize.recognize_pages(DummyImage(), "rus+eng")

    assert text == "--- Страница 1 ---\npage 1\n\n--- Страница 2 ---\npage 2"
    assert calls == [("rus+eng", "--psm 3", 60)] * 2
    assert all(item.closed for item in prepared_images)


def test_ocr_rejects_oversized_frame_before_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(recognize_module, "MAX_IMAGE_PIXELS", 99)
    with pytest.raises(DocumentRejectedError, match="лимит пикселей"):
        recognize_module.recognize_pages(_OversizedImage(), "eng")
