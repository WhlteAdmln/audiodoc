# Copyright (c) 2026 Nikolai Zelensky

"""Tests for document engine ocr."""

import io

import pytest
from PIL import Image

from audiodoc.document_engine.ocr import (
    extract_image_text,
)


def test_ocr_package_keeps_extract_image_text_entry_point(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("audiodoc.document_engine.ocr.ensure_ready", lambda _: None)
    monkeypatch.setattr(
        "audiodoc.document_engine.ocr.recognize_pages",
        lambda *_args, **_kwargs: "Recognized text",
    )

    output = io.BytesIO()
    Image.new("RGB", (2, 2), color="white").save(output, format="PNG")

    expected_extract_image_text = "Recognized text"
    assert extract_image_text(output.getvalue()) == expected_extract_image_text
