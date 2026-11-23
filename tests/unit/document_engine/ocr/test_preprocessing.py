# Copyright (c) 2026 Nikolai Zelensky

"""Tests for ocr preprocessing."""

import pytest
from PIL import Image

from audiodoc.document_engine.ocr import preprocessing as ocr_preprocessing
from audiodoc.errors.documents import DocumentRejectedError


def test_prepare_image_returns_autocontrasted_grayscale() -> None:
    source = Image.new("RGB", (4, 4), color=(100, 100, 100))
    prepared = ocr_preprocessing._prepare_image(source)
    try:
        assert prepared.mode == "L"
        assert prepared.size == (4, 4)
    finally:
        prepared.close()
        source.close()


def test_prepare_image_rejects_excessive_pixel_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ocr_preprocessing, "MAX_IMAGE_PIXELS", 3)
    source = Image.new("RGB", (2, 2))
    try:
        with pytest.raises(DocumentRejectedError, match="превышен лимит пикселей"):
            ocr_preprocessing._prepare_image(source)
    finally:
        source.close()
