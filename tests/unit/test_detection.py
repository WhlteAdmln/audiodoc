import io
import zipfile

import pytest

from backend.document_engine.detection import detect_format


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
def test_detect_format(data, filename, expected):
    assert detect_format(data, filename) == expected


def test_detect_docx_by_zip_contents():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("word/document.xml", "<document />")

    assert detect_format(output.getvalue(), "renamed.bin") == "docx"
