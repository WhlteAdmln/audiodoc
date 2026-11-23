# Copyright (c) 2026 Nikolai Zelensky

"""Tests for ocr preprocessing."""

import pytest
from PIL import Image

from audiodoc.document_engine.ocr import preprocessing as ocr_preprocessing
from audiodoc.errors.documents import DocumentRejectedError


def test_prepare_image_returns_autocontrasted_grayscale() -> None:
    # pylint: disable=protected-access  # pins the preprocessing step directly
    with (
        Image.new("RGB", (4, 4), color=(100, 100, 100)) as source,
        ocr_preprocessing._prepare_image(source) as prepared,  # noqa: SLF001
    ):
        actual = (prepared.mode, prepared.size)
    expected = ("L", (4, 4))
    assert actual == expected, "the image must become a same-sized grayscale"


def test_prepare_image_rejects_excessive_pixel_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # pylint: disable=protected-access  # pins the preprocessing step directly
    monkeypatch.setattr(ocr_preprocessing, "MAX_IMAGE_PIXELS", 3)
    with (
        Image.new("RGB", (2, 2)) as source,
        pytest.raises(DocumentRejectedError, match="превышен лимит пикселей"),
    ):
        ocr_preprocessing._prepare_image(source)  # noqa: SLF001
