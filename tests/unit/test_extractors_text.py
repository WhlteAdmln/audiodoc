import pytest

# The public Document Engine package imports the full extractor registry. Keep
# collection clean on minimal environments and expose missing parser dependencies.
pytest.importorskip("ebooklib")
pytest.importorskip("striprtf")

from backend.document_engine import process_document_sync
from backend.errors.documents import UnsupportedFormatError

CASES = [
    (b"Hello! This is a TXT test.", "test.txt", "txt", "TXT test"),
    (
        b"# Test Markdown\n\nDocument engine works!",
        "test.md",
        "md",
        "Document engine",
    ),
    (
        b"<html><body><h1>Hello</h1><p>HTML test</p></body></html>",
        "test.html",
        "html",
        "HTML test",
    ),
    (
        b"<?xml version='1.0'?><root><item>XML test</item></root>",
        "test.xml",
        "xml",
        "XML test",
    ),
    (b"Name,Value\nDocument engine,Works!\n", "test.csv", "csv", "Document engine"),
    (b"{\\rtf1 RTF test}", "test.rtf", "rtf", "RTF test"),
]


@pytest.mark.parametrize(
    ("data", "name", "expected_format", "expected_text"),
    CASES,
)
def test_text_formats(data, name, expected_format, expected_text, tmp_path):
    path = tmp_path / name
    path.write_bytes(data)

    result = process_document_sync(path.read_bytes(), path.name)

    assert result["format"] == expected_format
    assert expected_text in result["text"]
    assert result["characters"] == len(result["text"])


def test_fb2_extraction(tmp_path):
    data = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'    <FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">\n'
        b"        <description><title-info><book-title>"
        b"Test Book</book-title></title-info></description>\n"
        b"        <body><section><p>FB2 Test Chapter</p>\n"
        b"        <p>Document engine works!</p></section></body>\n"
        b"    </FictionBook>"
    )
    path = tmp_path / "test.fb2"
    path.write_bytes(data)

    result = process_document_sync(path.read_bytes(), path.name)

    assert result["format"] == "fb2"
    assert "FB2 Test Chapter" in result["text"]
    assert "Document engine works!" in result["text"]


def test_standalone_image_is_rejected_by_document_engine():
    with pytest.raises(UnsupportedFormatError):
        process_document_sync(b"\x89PNG\r\n\x1a\n", "image.png")
