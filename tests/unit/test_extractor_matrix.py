# Copyright (c) 2026 Nikolai Zelensky
"""Table-driven extraction checks for every registered document format."""

import zipfile
from collections.abc import Callable
from io import BytesIO

import pymupdf
import pytest
from odf.draw import Page
from odf.opendocument import load as load_odf
from odf.text import H
from pptx import Presentation

import audiodoc.document_engine.extractors.djvu as djvu_module
import audiodoc.document_engine.extractors.djvu.text_layer as text_layer_module
from audiodoc.common.deadline import Deadline
from audiodoc.common.text_budget import TextBudget
from audiodoc.document_engine.extractors import REGISTRY
from audiodoc.document_engine.extractors.base import ExtractContext
from audiodoc.document_engine.extractors.djvu.tools import DjvuTools
from audiodoc.document_engine.extractors.odf.odp import extract_odp
from audiodoc.document_engine.extractors.pptx import extract_pptx
from audiodoc.document_engine.pipeline import process_document_sync
from audiodoc.errors.base import BackendError
from tests.builders import (
    create_csv,
    create_docx,
    create_epub,
    create_fb2,
    create_html,
    create_md,
    create_odp,
    create_ods,
    create_odt,
    create_pdf,
    create_pptx,
    create_rtf,
    create_txt,
    create_xlsx,
    create_xml,
)
from tests.support.builders import create_djvu

Builder = Callable[[], bytes]
UNICODE_TEXT = "Привет 😀"
PRIVATE_DETAIL = "PRIVATE_PARSER_DETAIL"

MATRIX: tuple[tuple[str, str, Builder, str], ...] = (
    ("pdf", ".pdf", create_pdf, "PDF document test"),
    ("docx", ".docx", create_docx, "DOCX test"),
    ("xlsx", ".xlsx", create_xlsx, "Document engine"),
    ("pptx", ".pptx", create_pptx, "PPTX test"),
    ("epub", ".epub", create_epub, "EPUB test"),
    ("fb2", ".fb2", create_fb2, "FB2 test"),
    ("djvu", ".djvu", create_djvu, "DJVU text layer"),
    ("odt", ".odt", create_odt, "ODT test"),
    ("ods", ".ods", create_ods, "Document engine"),
    ("odp", ".odp", create_odp, "ODP test"),
    ("txt", ".txt", create_txt, "TXT test"),
    ("md", ".md", create_md, "Markdown test"),
    ("csv", ".csv", create_csv, "Document engine"),
    ("html", ".html", create_html, "HTML test"),
    ("xml", ".xml", create_xml, "XML test"),
    ("rtf", ".rtf", create_rtf, "RTF test"),
)

TOLERANT_FORMATS = {"txt", "md", "csv", "html", "rtf"}

ARCHIVE_TEXT = {
    "docx": "DOCX test",
    "xlsx": "Document engine",
    "pptx": "PPTX test",
    "epub": "EPUB test",
    "odt": "ODT test",
    "ods": "Document engine",
    "odp": "ODP test",
}

ARCHIVE_CORRUPT_MEMBERS = {
    "docx": "word/document.xml",
    "xlsx": "xl/workbook.xml",
    "pptx": "ppt/presentation.xml",
    "epub": "META-INF/container.xml",
    "odt": "content.xml",
    "ods": "content.xml",
    "odp": "content.xml",
}


def _rewrite_archive(
    data: bytes,
    *,
    member_name: str | None = None,
    old_text: bytes | None = None,
    new_text: bytes,
) -> bytes:
    """Rewrite one archive member or replace text in archive members."""
    replacements = 0
    output = BytesIO()
    with (
        zipfile.ZipFile(BytesIO(data)) as source,
        zipfile.ZipFile(output, "w") as target,
    ):
        for member in source.infolist():
            payload = source.read(member.filename)
            if member_name == member.filename:
                payload = new_text
                replacements += 1
            elif old_text is not None:
                replacements += payload.count(old_text)
                payload = payload.replace(old_text, new_text)
            target.writestr(member, payload)
    assert replacements > 0
    return output.getvalue()


def _corrupt_archive_crc(data: bytes, member_name: str) -> bytes:
    """Corrupt one ZIP member CRC while preserving format detection."""
    corrupted = bytearray(data)
    end_record = data.rfind(b"PK\x05\x06")
    assert end_record >= 0
    position = int.from_bytes(data[end_record + 16 : end_record + 20], "little")

    while data[position : position + 4] == b"PK\x01\x02":
        name_length = int.from_bytes(data[position + 28 : position + 30], "little")
        extra_length = int.from_bytes(data[position + 30 : position + 32], "little")
        comment_length = int.from_bytes(data[position + 32 : position + 34], "little")
        name = data[position + 46 : position + 46 + name_length].decode("utf-8")
        if name == member_name:
            corrupted[position + 16] ^= 1
            return bytes(corrupted)
        position += 46 + name_length + extra_length + comment_length

    message = f"ZIP member not found: {member_name}"
    raise AssertionError(message)


def _pdf_with_unicode_actual_text(data: bytes) -> bytes:
    """Add Unicode ActualText to a PDF content stream."""
    document = pymupdf.open(stream=data, filetype="pdf")
    encoded = UNICODE_TEXT.encode("utf-16-be").hex().upper().encode("ascii")
    prefix = b"/Span << /ActualText <FEFF" + encoded + b">>> BDC\n"
    updated = False
    for page in document:
        for xref in page.get_contents():
            content = document.xref_stream(xref)
            if content is not None:
                document.update_stream(xref, prefix + content + b"\nEMC\n")
                updated = True
    result = document.tobytes()
    document.close()
    assert updated
    return result


def _unicode_document(filetype: str, builder: Builder) -> bytes:
    """Create a document containing Cyrillic text and an emoji."""
    data = builder()
    if filetype == "pdf":
        return _pdf_with_unicode_actual_text(data)
    if filetype == "djvu":
        return data
    if filetype in ARCHIVE_TEXT:
        return _rewrite_archive(
            data,
            old_text=ARCHIVE_TEXT[filetype].encode("utf-8"),
            new_text=UNICODE_TEXT.encode("utf-8"),
        )
    if filetype == "rtf":
        return data.replace(b"RTF test", UNICODE_TEXT.encode("utf-8"))

    old_text = {
        "txt": b"TXT test",
        "md": b"Markdown test",
        "csv": b"Document engine",
        "html": b"HTML test",
        "xml": b"XML test",
        "fb2": b"FB2 test",
    }[filetype]
    assert old_text in data
    return data.replace(old_text, UNICODE_TEXT.encode("utf-8"))


def _corrupt_document(filetype: str, builder: Builder) -> bytes:
    """Create malformed input while preserving format detection."""
    if filetype in {"odt", "ods", "odp"}:
        return _corrupt_archive_crc(
            builder(),
            ARCHIVE_CORRUPT_MEMBERS[filetype],
        )
    if filetype in ARCHIVE_CORRUPT_MEMBERS:
        return _rewrite_archive(
            builder(),
            member_name=ARCHIVE_CORRUPT_MEMBERS[filetype],
            new_text=f"<broken>{PRIVATE_DETAIL}".encode(),
        )
    if filetype == "pdf":
        return f"%PDF-1.7\n{PRIVATE_DETAIL}".encode()
    if filetype == "djvu":
        return b"AT&TFORM\x00\x00\x00\x04BAD!"
    return {
        "fb2": f"<FictionBook><body><p>{PRIVATE_DETAIL}".encode(),
        "xml": f"<?xml version='1.0'?><root>{PRIVATE_DETAIL}".encode(),
        "txt": b"\xffbroken",
        "md": b"\xffbroken",
        "csv": b'"unterminated,\xff\n',
        "html": b"<html><body><p>broken",
        "rtf": b"{\\rtf1\\ansi broken \xff}",
    }[filetype]


def _mock_djvu(
    monkeypatch: pytest.MonkeyPatch,
    output: bytes = b"DJVU text layer works!",
    *,
    return_code: int = 0,
) -> None:
    """Replace DjVuLibre discovery and execution with deterministic responses."""
    tools = DjvuTools("djvutxt", "djvused", "ddjvu")
    monkeypatch.setattr(djvu_module, "find_djvu_tools", lambda: tools)
    monkeypatch.setattr(
        text_layer_module,
        "run_limited",
        lambda *_args, **_kwargs: (
            return_code,
            output,
            PRIVATE_DETAIL.encode(),
        ),
    )


def _assert_clean_error(error: BackendError) -> None:
    """Ensure a public error does not expose parser details or a traceback."""
    message = str(error)
    assert PRIVATE_DETAIL not in message
    assert "Traceback" not in message
    assert PRIVATE_DETAIL not in getattr(error, "public_message", "")


def test_registered_formats_have_matrix_rows() -> None:
    """Require exactly one matrix row for every registered extractor."""
    matrix_formats = [row[0] for row in MATRIX]
    assert len(matrix_formats) == len(set(matrix_formats))
    assert set(REGISTRY) == set(matrix_formats)


@pytest.mark.parametrize(
    ("filetype", "extension", "builder", "expected_text"),
    MATRIX,
    ids=[row[0] for row in MATRIX],
)
def test_registered_extractor_matrix(
    filetype: str,
    extension: str,
    builder: Builder,
    expected_text: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise normal, empty, malformed, Unicode, and limited input per format."""
    if filetype == "djvu":
        _mock_djvu(monkeypatch)

    normal = process_document_sync(builder(), f"sample{extension}")
    assert normal["format"] == filetype
    assert expected_text in normal["text"]

    with pytest.raises(BackendError) as empty_error:
        process_document_sync(b"", f"sample{extension}")
    _assert_clean_error(empty_error.value)

    if filetype == "djvu":
        _mock_djvu(monkeypatch, return_code=1)
    corrupt = _corrupt_document(filetype, builder)
    if filetype in TOLERANT_FORMATS:
        converted = process_document_sync(corrupt, f"sample{extension}")
        assert converted["format"] == filetype
        assert converted["text"]
    else:
        with pytest.raises(BackendError) as corrupt_error:
            process_document_sync(corrupt, f"sample{extension}")
        _assert_clean_error(corrupt_error.value)

    if filetype == "djvu":
        _mock_djvu(monkeypatch, UNICODE_TEXT.encode("utf-8"))
    unicode_result = process_document_sync(
        _unicode_document(filetype, builder),
        f"sample{extension}",
    )
    assert UNICODE_TEXT in unicode_result["text"]

    if filetype == "djvu":
        _mock_djvu(monkeypatch, b"Document text longer than the limit")
    limited = process_document_sync(
        builder(),
        f"sample{extension}",
        max_characters=5,
    )
    assert limited["characters"] <= 5
    assert limited["truncated"] is True


def test_pptx_extracts_table_rows_and_truncates_table_text() -> None:
    """Cover PPTX table rows and budget exhaustion inside a table."""
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    table = slide.shapes.add_table(1, 2, 0, 0, 3_000_000, 500_000).table
    table.cell(0, 0).text = "Name"
    table.cell(0, 1).text = "Value"
    output = BytesIO()
    presentation.save(output)
    data = output.getvalue()

    assert "Name | Value" in process_document_sync(data, "table.pptx")["text"]

    budget = TextBudget(20)
    context = ExtractContext(budget=budget, deadline=Deadline(10))
    extract_pptx(data, context=context)
    assert budget.truncated is True


def test_odp_extracts_headings_and_truncates_slide_text() -> None:
    """Cover ODP headings and truncation while extracting a slide."""
    document = load_odf(BytesIO(create_odp()))
    page = document.getElementsByType(Page)[0]
    page.addElement(H(outlinelevel=1, text="ODP heading"), check_grammar=False)

    assert "ODP heading" in extract_odp(document)

    budget = TextBudget(20)
    context = ExtractContext(budget=budget, deadline=Deadline(10))
    text = extract_odp(document, context=context)
    assert len(text) <= 20
    assert budget.truncated is True
