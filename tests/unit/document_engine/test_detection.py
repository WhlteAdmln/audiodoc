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
def test_detects_format_from_signature_and_extension(
    data: object, filename: object, expected: object
) -> None:
    assert detect_format(data, filename) == expected, (
        f"{filename!r} was not detected as {expected!r}"
    )


def test_detects_docx_by_zip_contents() -> None:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("word/document.xml", "<document />")

    expected_detect_format = "docx"
    assert detect_format(output.getvalue(), "renamed.bin") == expected_detect_format, (
        "a ZIP archive with word/document.xml was not detected as DOCX"
    )


def test_exports_supported_document_formats() -> None:
    document_format = "pdf"
    assert document_format in SUPPORTED_FORMATS, "PDF is not a supported format"


def test_exports_image_extensions() -> None:
    image_extension = ".png"
    assert image_extension in IMAGE_EXTENSIONS, "PNG is not an image extension"


def test_exports_extension_map() -> None:
    expected_markdown = "md"
    assert extension_map["markdown"] == expected_markdown, (
        "the markdown extension does not map to md"
    )


def test_image_extension_check_still_precedes_file_signature() -> None:
    assert detect_format(b"%PDF-1.7 payload", "payload.png") is None, (
        "a PDF signature overrode the image extension"
    )


def test_signature_check_still_precedes_other_extension() -> None:
    expected_detect_format = "pdf"
    assert (
        detect_format(b"%PDF-1.7 payload", "payload.txt") == expected_detect_format
    ), "the text extension overrode the PDF signature"


def test_text_extension_mapping_is_preserved() -> None:
    expected_detect_format = "md"
    assert (
        detect_format(b"not really markdown", "payload.markdown")
        == expected_detect_format
    ), "the markdown extension was not mapped to md"


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

    assert detected is None or isinstance(detected, str), (
        f"detect_format returned {detected!r} instead of a format name or None"
    )


def test_mimetype_member_is_read_with_a_fixed_200_byte_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", b"0" * (4 * 1024 * 1024))

    original_read = zipfile.ZipExtFile.read
    requested_sizes = []

    def tracked_read(self: zipfile.ZipExtFile, n: int = -1) -> bytes:
        requested_sizes.append(n)
        return original_read(self, n)

    monkeypatch.setattr(zipfile.ZipExtFile, "read", tracked_read)
    detect_format(output.getvalue(), "unknown.zip")

    expected_sizes = [200]
    assert requested_sizes == expected_sizes, "mimetype was read without a limit"
