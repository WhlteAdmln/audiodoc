# Copyright (c) 2026 Nikolai Zelensky

"""Tests for document engine detection."""

import io
import zipfile

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from audiodoc.document_engine.detection import detect_format
from audiodoc.document_engine.detection.formats import (
    IMAGE_EXTENSIONS,
    SUPPORTED_FORMATS,
    extension_map,
)


@pytest.mark.parametrize(
    ("data", "filename", "expected"),
    [
        (b"%PDF-1.7 test", "document.pdf", "pdf"),
        (b"{\\rtf1 test}", "document.rtf", "rtf"),
        (b"AT&TFORM", "document.djvu", "djvu"),
        (b"Hello, world!", "document.txt", "txt"),
        (b"# Markdown", "document.md", "md"),
        (b"<html><body>hello</body></html>", "document.html", "html"),
        (b"\x89PNG\r\n\x1a\n", "image.png", None),
        (b"GIF89a", "image.gif", None),
        (b"\xff\xd8\xff", "image.jpg", None),
    ],
)
def test_detect_format(data: object, filename: object, expected: object) -> None:
    assert detect_format(data, filename) == expected


def test_detect_docx_by_zip_contents() -> None:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("word/document.xml", "<document />")

    assert detect_format(output.getvalue(), "renamed.bin") == "docx"


def test_detection_package_exports_expected_format_collections() -> None:
    assert "pdf" in SUPPORTED_FORMATS
    assert ".png" in IMAGE_EXTENSIONS
    assert extension_map["markdown"] == "md"


def test_image_extension_check_still_precedes_file_signature() -> None:
    assert detect_format(b"%PDF-1.7 payload", "payload.png") is None


def test_signature_check_still_precedes_other_extension() -> None:
    assert detect_format(b"%PDF-1.7 payload", "payload.txt") == "pdf"


def test_text_extension_mapping_is_preserved() -> None:
    assert detect_format(b"not really markdown", "payload.markdown") == "md"


@given(
    data=st.one_of(
        st.binary(max_size=4096),
        st.binary(max_size=4094).map(lambda payload: b"PK" + payload),
    ),
    filename=st.one_of(st.none(), st.text(max_size=255)),
)
@settings(max_examples=200)
def test_detect_format_never_raises_for_random_bytes_and_names(
    data: bytes,
    filename: str | None,
) -> None:
    detected = detect_format(data, filename)

    assert detected is None or isinstance(detected, str)
