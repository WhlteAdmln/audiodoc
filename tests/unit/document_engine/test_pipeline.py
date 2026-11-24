# Copyright (c) 2026 Nikolai Zelensky

"""Tests for document engine pipeline_module."""

from __future__ import annotations

import asyncio
import threading
import zipfile
from io import BytesIO
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from typing import IO, TYPE_CHECKING, Never

import aiohttp
import pymupdf
import pytest
import starlette.formparsers

import audiodoc.document_engine.extractors.djvu as djvu_module
import audiodoc.document_engine.extractors.djvu.text_layer as text_layer_module
from audiodoc.common.deadline import DeadlineExceededError
from audiodoc.common.work_queue import WorkQueue
from audiodoc.document_engine import pipeline as pipeline_module
from audiodoc.document_engine import (
    process_document_sync,
    runner,
)
from audiodoc.document_engine.extractors import REGISTRY
from audiodoc.document_engine.extractors import pdf as pdf_module
from audiodoc.document_engine.extractors.djvu.tools import DjvuTools
from audiodoc.document_engine.guards import zip_archive as zip_guard
from audiodoc.errors.base import BackendError
from audiodoc.errors.documents import (
    DocumentRejectedError,
    PayloadTooLargeError,
    ProcessingTimeoutError,
    UnsupportedFormatError,
)
from tests.support.builders import (
    create_docx,
    create_epub,
    create_fb2,
    create_odp,
    create_ods,
    create_odt,
    create_pdf,
    create_pptx,
    create_xlsx,
)
from tests.support.extractor_matrix import MATRIX, Builder
from tests.support.hostile_documents import (
    ZipEntry,
    billion_laughs_payload,
    lie_about_declared_size,
    make_nested_archive,
    make_symlink_entry,
    write_zip,
)
from tests.support.pymupdf_documents import FakeDocument, HugePdfPage
from tests.support.server import fixture_live_server

__all__ = ["fixture_live_server"]

if TYPE_CHECKING:
    from tests.support.server import LiveServer


def _limited_zip(
    monkeypatch: pytest.MonkeyPatch,
    limit_name: str,
    limit: int,
    entries: list[ZipEntry] | None = None,
) -> tuple[bytes, list[ZipEntry]]:
    """Create an archive with a reduced configured limit."""
    monkeypatch.setattr(zip_guard, limit_name, limit)
    return b"<d/>", entries or []


def _make_zip(attack: str, monkeypatch: pytest.MonkeyPatch) -> bytes:
    """Build a small DOCX-like archive containing one selected attack."""
    builders = {
        "zip_bomb": lambda: (b"A" * 4096, []),
        "too_many_entries": lambda: _limited_zip(
            monkeypatch,
            "MAX_ARCHIVE_FILES",
            3,
            [("word/extra.xml", b"<x/>")],
        ),
        "nested_archive": lambda: (
            b"<d/>",
            [("word/embedded.bin", make_nested_archive())],
        ),
        "nested_archive_extension": lambda: (
            b"<d/>",
            [("word/embedded.zip", b"not actually nested")],
        ),
        "path_traversal": lambda: (b"<d/>", [("../escape.txt", b"escape")]),
        "absolute_path": lambda: (
            b"<d/>",
            [(f"{Path.cwd().anchor}escape.txt", b"escape")],
        ),
        "windows_absolute_path": lambda: (
            b"<d/>",
            [(r"C:\escape.txt", b"escape")],
        ),
        "symlink": lambda: (b"<d/>", [make_symlink_entry()]),
        "file_size_limit": lambda: _limited_zip(
            monkeypatch,
            "MAX_ARCHIVE_FILE_SIZE",
            3,
        ),
        "unpacked_size_limit": lambda: _limited_zip(
            monkeypatch,
            "MAX_ARCHIVE_UNPACKED_SIZE",
            7,
            [("word/extra.bin", b"1234")],
        ),
        "declared_size_lie": lambda: (b"<d/>", []),
    }

    document, entries = builders[attack]()
    data = write_zip(document, entries)

    expected_attack = "declared_size_lie"
    if attack == expected_attack:
        return lie_about_declared_size(data)
    return data


def _track_upload_files(
    monkeypatch: pytest.MonkeyPatch,
    directory: Path,
) -> list[IO[bytes]]:
    """Track multipart temporary files and force them to disk."""
    original = starlette.formparsers.SpooledTemporaryFile
    opened: list[IO[bytes]] = []

    def tracked(*args: object, **kwargs: object) -> IO[bytes]:
        kwargs["max_size"] = 1
        kwargs["dir"] = directory
        # pylint: disable-next=consider-using-with  # the caller owns the handle
        handle = original(*args, **kwargs)
        opened.append(handle)
        return handle

    monkeypatch.setattr(starlette.formparsers, "SpooledTemporaryFile", tracked)
    return opened


async def _post_document(
    server: LiveServer,
    data: bytes,
    filename: str,
) -> tuple[int, dict[str, object]]:
    form = aiohttp.FormData()
    form.add_field(
        "file",
        data,
        filename=filename,
        content_type="application/octet-stream",
    )
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            f"{server.base_url}/process-document",
            data=form,
            headers={"Authorization": f"Bearer {server.document_api_key}"},
        ) as response,
    ):
        payload = await response.json()
        return response.status, payload


def _upload_state(
    opened: list[IO[bytes]],
    directory: Path,
) -> dict[str, object]:
    return {
        "spooled": bool(opened),
        "closed": all(handle.closed for handle in opened),
        "left_files": sorted(path.name for path in directory.iterdir()),
    }


def _clean_rejection(detail: str) -> tuple[int, dict[str, str], dict[str, object]]:
    clean_upload = {"spooled": True, "closed": True, "left_files": []}
    return 400, {"detail": detail, "code": "document_rejected"}, clean_upload


UNICODE_TEXT = "Привет 😀"


PRIVATE_DETAIL = "PRIVATE_PARSER_DETAIL"


TOLERANT_FORMATS = frozenset({"txt", "md", "csv", "html", "rtf"})


ARCHIVE_TEXT = MappingProxyType(
    {
        "docx": "DOCX test",
        "xlsx": "Document engine",
        "pptx": "PPTX test",
        "epub": "EPUB test",
        "odt": "ODT test",
        "ods": "Document engine",
        "odp": "ODP test",
    }
)


ARCHIVE_CORRUPT_MEMBERS = MappingProxyType(
    {
        "docx": "word/document.xml",
        "xlsx": "xl/workbook.xml",
        "pptx": "ppt/presentation.xml",
        "epub": "META-INF/container.xml",
        "odt": "content.xml",
        "ods": "content.xml",
        "odp": "content.xml",
    }
)


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
    if replacements == 0:
        message = "nothing was rewritten in the archive"
        raise AssertionError(message)
    return output.getvalue()


def _corrupt_archive_crc(data: bytes, member_name: str) -> bytes:
    """Corrupt one ZIP member CRC while preserving format detection."""
    corrupted = bytearray(data)
    end_record = data.rfind(b"PK\x05\x06")
    if end_record < 0:
        message = "the archive has no end of central directory record"
        raise AssertionError(message)
    position = int.from_bytes(data[end_record + 16 : end_record + 20], "little")

    expected_data = b"PK\x01\x02"
    while data[position : position + 4] == expected_data:
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
    if not updated:
        message = "the PDF has no content stream"
        raise AssertionError(message)
    return result


def _unicode_document(filetype: str, builder: Builder) -> bytes:
    """Create a document containing Cyrillic text and an emoji."""
    data = builder()
    pdf_type = "pdf"
    if filetype == pdf_type:
        return _pdf_with_unicode_actual_text(data)
    djvu_type = "djvu"
    if filetype == djvu_type:
        return data
    if filetype in ARCHIVE_TEXT:
        return _rewrite_archive(
            data,
            old_text=ARCHIVE_TEXT[filetype].encode("utf-8"),
            new_text=UNICODE_TEXT.encode("utf-8"),
        )
    rtf_type = "rtf"
    if filetype == rtf_type:
        return data.replace(b"RTF test", UNICODE_TEXT.encode("utf-8"))

    old_text = {
        "txt": b"TXT test",
        "md": b"Markdown test",
        "csv": b"Document engine",
        "html": b"HTML test",
        "xml": b"XML test",
        "fb2": b"FB2 test",
    }[filetype]
    if old_text not in data:
        message = f"the {filetype} sample does not contain {old_text!r}"
        raise AssertionError(message)
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
    pdf_type = "pdf"
    if filetype == pdf_type:
        return f"%PDF-1.7\n{PRIVATE_DETAIL}".encode()
    djvu_type = "djvu"
    if filetype == djvu_type:
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


def _leaked_details(error: BackendError) -> list[str]:
    """Return the parser details or traceback markers a public error exposes."""
    texts = (str(error), getattr(error, "public_message", ""))
    markers = (PRIVATE_DETAIL, "Traceback")
    return [marker for marker in markers for text in texts if marker in text]


TEXT_CASES = (
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
)


OFFICE_CASES = (
    (create_docx, "test.docx", "docx", "Document engine works!"),
    (create_xlsx, "test.xlsx", "xlsx", "Document engine"),
    (create_pptx, "test.pptx", "pptx", "Document engine works!"),
    (create_odt, "test.odt", "odt", "Document engine works!"),
    (create_ods, "test.ods", "ods", "Document engine"),
    (create_odp, "test.odp", "odp", "Document engine works!"),
    (create_epub, "test.epub", "epub", "Document engine works!"),
    (create_fb2, "test.fb2", "fb2", "Document engine works!"),
    (create_pdf, "test.pdf", "pdf", "PDF document test"),
)


FORMAT_ROWS = tuple(
    pytest.param(filetype, extension, builder, id=filetype)
    for filetype, extension, builder, _text in MATRIX
)


TOLERANT_ROWS = tuple(row for row in FORMAT_ROWS if row.id in TOLERANT_FORMATS)


STRICT_ROWS = tuple(row for row in FORMAT_ROWS if row.id not in TOLERANT_FORMATS)


ZIP_ATTACKS = (
    "zip_bomb",
    "too_many_entries",
    "nested_archive",
    "nested_archive_extension",
    "path_traversal",
    "absolute_path",
    "windows_absolute_path",
    "symlink",
    "file_size_limit",
    "unpacked_size_limit",
    "declared_size_lie",
)


XML_ATTACKS = (
    billion_laughs_payload(),
    (
        b'<?xml version="1.0"?><!DOCTYPE root ['
        b'<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        b"<root>&xxe;</root>"
    ),
)


def _prepare_djvu(
    filetype: str,
    monkeypatch: pytest.MonkeyPatch,
    output: bytes = b"DJVU text layer works!",
    *,
    return_code: int = 0,
) -> None:
    """Replace DjVuLibre only when the row under test is the DjVu format."""
    djvu_type = "djvu"
    if filetype == djvu_type:
        _mock_djvu(monkeypatch, output, return_code=return_code)


@pytest.mark.asyncio
@pytest.mark.parametrize("attack", ZIP_ATTACKS)
async def test_rejects_zip_abuse_cleanly_and_removes_upload(
    attack: str,
    live_server: LiveServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pipeline_module,
        "detect_format",
        lambda _data, _filename: "docx",
    )
    opened = _track_upload_files(monkeypatch, live_server.temp_dir)
    status, payload = await _post_document(
        live_server,
        _make_zip(attack, monkeypatch),
        "malicious.docx",
    )

    outcome = (status, payload, _upload_state(opened, live_server.temp_dir))
    expected = _clean_rejection("Документ содержит повреждённый или недопустимый архив")
    assert outcome == expected, f"the {attack} archive was not rejected cleanly"


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", XML_ATTACKS, ids=["billion_laughs", "xxe"])
async def test_rejects_xml_entity_attacks_cleanly_and_removes_upload(
    payload: bytes,
    live_server: LiveServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pipeline_module,
        "detect_format",
        lambda _data, _filename: "xml",
    )
    opened = _track_upload_files(monkeypatch, live_server.temp_dir)
    status, result = await _post_document(live_server, payload, "attack.xml")

    outcome = (status, result, _upload_state(opened, live_server.temp_dir))
    expected = _clean_rejection("XML содержит запрещённые конструкции")
    assert outcome == expected, "an XML entity attack was not rejected cleanly"


@pytest.mark.asyncio
async def test_rejects_huge_pdf_page_cleanly_and_removes_upload(
    live_server: LiveServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pipeline_module,
        "detect_format",
        lambda _data, _filename: "pdf",
    )
    monkeypatch.setattr(
        pdf_module.pymupdf,
        "open",
        lambda **_kwargs: FakeDocument([HugePdfPage()]),
    )
    opened = _track_upload_files(monkeypatch, live_server.temp_dir)
    status, result = await _post_document(live_server, b"%PDF-huge-page", "huge.pdf")

    outcome = (status, result, _upload_state(opened, live_server.temp_dir))
    expected = _clean_rejection("Страница PDF слишком велика для безопасного OCR")
    assert outcome == expected, "a huge PDF page was not rejected cleanly"


@pytest.mark.parametrize(
    ("filetype", "extension", "builder", "expected_text"),
    MATRIX,
    ids=[row[0] for row in MATRIX],
)
def test_extracts_registered_format_from_valid_sample(
    filetype: str,
    extension: str,
    builder: Builder,
    expected_text: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare_djvu(filetype, monkeypatch)

    result = process_document_sync(builder(), f"sample{extension}")

    outcome = (result["format"], expected_text in result["text"])
    expected = (filetype, True)
    assert outcome == expected, f"the valid {filetype} sample was not extracted"


@pytest.mark.parametrize(("filetype", "extension", "builder"), FORMAT_ROWS)
def test_rejects_empty_input_without_leaking_details(
    filetype: str,
    extension: str,
    builder: Builder,
) -> None:
    _ = builder

    with pytest.raises(BackendError) as caught:
        process_document_sync(b"", f"sample{extension}")

    expected_empty: list[str] = []
    assert _leaked_details(caught.value) == expected_empty, (
        f"the empty {filetype} error leaks details"
    )


@pytest.mark.parametrize(("filetype", "extension", "builder"), TOLERANT_ROWS)
def test_extracts_some_text_from_corrupt_tolerant_format(
    filetype: str,
    extension: str,
    builder: Builder,
) -> None:

    result = process_document_sync(
        _corrupt_document(filetype, builder), f"broken{extension}"
    )

    outcome = (result["format"], bool(result["text"]))
    expected = (filetype, True)
    assert outcome == expected, f"the corrupt {filetype} input gave no text"


@pytest.mark.parametrize(("filetype", "extension", "builder"), STRICT_ROWS)
def test_rejects_corrupt_strict_format_without_leaking_details(
    filetype: str,
    extension: str,
    builder: Builder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare_djvu(filetype, monkeypatch, return_code=1)
    corrupt = _corrupt_document(filetype, builder)

    with pytest.raises(BackendError) as caught:
        process_document_sync(corrupt, f"corrupt{extension}")

    expected_empty: list[str] = []
    assert _leaked_details(caught.value) == expected_empty, (
        f"the corrupt {filetype} error leaks parser details"
    )


@pytest.mark.parametrize(("filetype", "extension", "builder"), FORMAT_ROWS)
def test_keeps_cyrillic_and_emoji_text(
    filetype: str,
    extension: str,
    builder: Builder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare_djvu(filetype, monkeypatch, UNICODE_TEXT.encode("utf-8"))

    result = process_document_sync(
        _unicode_document(filetype, builder), f"юникод{extension}"
    )

    assert UNICODE_TEXT in result["text"], f"the {filetype} text lost Unicode"


@pytest.mark.parametrize(("filetype", "extension", "builder"), FORMAT_ROWS)
def test_truncates_registered_format_to_character_hint(
    filetype: str,
    extension: str,
    builder: Builder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare_djvu(filetype, monkeypatch, b"Document text longer than the limit")
    limit = 5

    result = process_document_sync(
        builder(), f"limited{extension}", max_characters=limit
    )

    outcome = (result["characters"] <= limit, result["truncated"])
    expected = (True, True)
    assert outcome == expected, f"the {filetype} text ignored the character hint"


@pytest.mark.parametrize(
    ("builder", "filename", "expected_format", "expected_text"),
    OFFICE_CASES,
    ids=[row[2] for row in OFFICE_CASES],
)
def test_extracts_text_from_office_and_pdf_formats(
    builder: Builder,
    filename: str,
    expected_format: str,
    expected_text: str,
) -> None:
    result = process_document_sync(builder(), filename)

    outcome = (
        result["format"],
        expected_text in result["text"],
        result["characters"] == len(result["text"]),
    )
    expected = (expected_format, True, True)
    assert outcome == expected, f"the {expected_format} result is wrong"


def test_labels_presentation_slides() -> None:
    result = process_document_sync(create_pptx(), "deck.pptx")

    slide_header = "--- Слайд 1 ---"
    assert slide_header in result["text"], "the slide header is missing"


@pytest.mark.parametrize(
    ("data", "name", "expected_format", "expected_text"),
    TEXT_CASES,
    ids=[row[2] for row in TEXT_CASES],
)
def test_extracts_text_from_text_formats(
    data: bytes,
    name: str,
    expected_format: str,
    expected_text: str,
) -> None:
    result = process_document_sync(data, name)

    outcome = (
        result["format"],
        expected_text in result["text"],
        result["characters"] == len(result["text"]),
    )
    expected = (expected_format, True, True)
    assert outcome == expected, f"the {expected_format} result is wrong"


def test_extracts_fb2_chapter_title_and_text() -> None:
    data = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'    <FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">\n'
        b"        <description><title-info><book-title>"
        b"Test Book</book-title></title-info></description>\n"
        b"        <body><section><p>FB2 Test Chapter</p>\n"
        b"        <p>Document engine works!</p></section></body>\n"
        b"    </FictionBook>"
    )

    result = process_document_sync(data, "test.fb2")

    chapter_title = "FB2 Test Chapter"
    chapter_text = "Document engine works!"
    outcome = (
        result["format"],
        chapter_title in result["text"],
        chapter_text in result["text"],
    )
    expected = ("fb2", True, True)
    assert outcome == expected, "the FB2 chapter title or text is missing"


def test_rejects_standalone_image() -> None:
    with pytest.raises(UnsupportedFormatError) as caught:
        process_document_sync(b"\x89PNG\r\n\x1a\n", "image.png")

    expected_message = "Формат не поддерживается Document Engine"
    assert caught.value.public_message == expected_message, "a PNG was accepted"


def test_registry_contains_all_supported_document_formats() -> None:
    expected_formats = {
        "pdf",
        "docx",
        "xlsx",
        "pptx",
        "epub",
        "fb2",
        "djvu",
        "odt",
        "ods",
        "odp",
        "txt",
        "md",
        "csv",
        "html",
        "xml",
        "rtf",
    }

    assert set(REGISTRY) == expected_formats, "the registry formats changed"


def test_registry_reads_markdown_as_plain_text() -> None:
    assert REGISTRY["txt"] is REGISTRY["md"], "Markdown has its own extractor"


def test_odf_registry_entries_dispatch_to_the_correct_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fake_extract_odf(
        data: object,
        filetype: object,
        **_kwargs: object,
    ) -> object:
        calls.append((data, filetype))
        return ""

    monkeypatch.setattr(
        "audiodoc.document_engine.extractors.extract_odf",
        fake_extract_odf,
    )

    for kind in ("odt", "ods", "odp"):
        REGISTRY[kind](b"odf")

    expected = [(b"odf", "odt"), (b"odf", "ods"), (b"odf", "odp")]
    assert calls == expected, "each ODF registry entry must pass its own file type"


def test_dispatches_registered_extractor_and_builds_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pipeline_module, "detect_format", lambda _data, _name: "txt")
    monkeypatch.setitem(
        pipeline_module.REGISTRY,
        "txt",
        lambda _data, **_kwargs: "  extracted text  ",
    )

    result = pipeline_module.process_document_sync(b"payload", "note.txt")

    expected = {
        "format": "txt",
        "text": "extracted text",
        "characters": 14,
        "truncated": False,
    }
    assert result == expected, "the extractor text was not built into a result"


def test_validates_zip_before_calling_extractor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = []
    monkeypatch.setattr(pipeline_module, "detect_format", lambda _data, _name: "docx")
    monkeypatch.setattr(
        pipeline_module,
        "validate_zip_archive",
        lambda _data: events.append("validated"),
    )
    monkeypatch.setitem(
        pipeline_module.REGISTRY,
        "docx",
        lambda _data, **_kwargs: events.append("extracted") or "word",
    )

    result = pipeline_module.process_document_sync(b"zip payload", "note.docx")

    outcome = (events, result["format"], result["text"], result["truncated"])
    expected = (["validated", "extracted"], "docx", "word", False)
    assert outcome == expected, "the archive was not validated before extraction"


def test_rejects_empty_document() -> None:
    with pytest.raises(DocumentRejectedError) as caught:
        process_document_sync(b"", "empty.txt")

    expected_message = "Документ пуст"
    assert caught.value.public_message == expected_message, "an empty file passed"


def test_rejects_undetected_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline_module, "detect_format", lambda _data, _name: None)

    with pytest.raises(UnsupportedFormatError) as caught:
        process_document_sync(b"image", "image.png")

    expected_code = "unsupported_format"
    assert caught.value.code == expected_code, "an undetected format was accepted"


def test_rejects_detected_format_without_extractor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pipeline_module, "detect_format", lambda _data, _name: "exe")

    with pytest.raises(UnsupportedFormatError) as caught:
        process_document_sync(b"MZ\x90\x00", "setup.exe")

    expected_code = "unsupported_format"
    assert caught.value.code == expected_code, "a format without extractor passed"


def test_rejects_document_one_byte_over_size_limit() -> None:
    oversized = b"q" * (50 * 1024 * 1024 + 1)

    with pytest.raises(PayloadTooLargeError) as caught:
        process_document_sync(oversized, "huge.txt")

    expected_status = 413
    assert caught.value.status_code == expected_status, "an oversized file passed"


def test_legacy_processor_shim_has_been_removed() -> None:
    processor_path = (
        Path(__file__).parents[3] / "audiodoc" / "document_engine" / "processor.py"
    )

    assert not processor_path.exists(), "the legacy processor module is back"


def test_async_runner_executes_sync_pipeline_in_a_worker_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    main_thread = threading.get_ident()
    calls = []

    def fake_process(
        data: object, filename: object, max_characters: object, deadline: object
    ) -> object:
        calls.append((data, filename, max_characters, deadline, threading.get_ident()))
        return {"format": "txt", "text": "ok", "characters": 2, "truncated": False}

    monkeypatch.setattr(runner, "process_document_sync", fake_process)

    result = asyncio.run(
        runner.process_document(
            b"body", "note.txt", queue=WorkQueue(workers=1, max_waiting=4)
        )
    )

    data, filename, max_characters, deadline, thread = calls[0]
    outcome = (
        result,
        (data, filename, max_characters),
        deadline is not None,
        thread != main_thread,
    )
    expected = (
        {"format": "txt", "text": "ok", "characters": 2, "truncated": False},
        (b"body", "note.txt", None),
        True,
        True,
    )
    assert outcome == expected, "the runner did not use a worker thread"


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (
            b"0123456789",
            {"format": "txt", "text": "01234", "characters": 5, "truncated": True},
        ),
        (
            b"12345",
            {"format": "txt", "text": "12345", "characters": 5, "truncated": False},
        ),
        (
            b"123456",
            {"format": "txt", "text": "12345", "characters": 5, "truncated": True},
        ),
    ],
    ids=["far_over_budget", "exact_budget", "one_over_budget"],
)
def test_applies_client_character_hint(
    data: bytes, expected: dict[str, object]
) -> None:
    result = process_document_sync(data, "note.txt", max_characters=5)

    assert result == expected, "the character hint was applied incorrectly"


@pytest.mark.parametrize(
    "hint",
    [0, -7, True, 2_000_001, 3.5, "12"],
    ids=["zero", "negative", "bool", "over_server_limit", "float", "string"],
)
def test_rejects_invalid_character_hint(hint: object) -> None:
    with pytest.raises(DocumentRejectedError) as caught:
        process_document_sync(b"hello", "note.txt", max_characters=hint)

    expected_message = "Некорректный лимит длины текста"
    assert caught.value.public_message == expected_message, f"{hint!r} was accepted"


def test_hides_unexpected_extractor_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pipeline_module, "detect_format", lambda _data, _name: "txt")

    def fail_extractor(_data: object, **_kwargs: object) -> Never:
        error_message = "/private/path/to/parser-internal-error"
        raise RuntimeError(error_message)

    monkeypatch.setitem(pipeline_module.REGISTRY, "txt", fail_extractor)

    with pytest.raises(DocumentRejectedError) as caught:
        process_document_sync(b"payload", "note.txt")

    private_path = "/private/path"
    outcome = (caught.value.public_message, private_path in str(caught.value))
    expected_message = (
        "Не удалось прочитать документ: файл повреждён или имеет "
        "неподдерживаемую структуру"
    )
    expected = (expected_message, False)
    assert outcome == expected, "the extractor failure leaked its details"


def test_maps_deadline_expiration_to_safe_backend_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pipeline_module, "detect_format", lambda *_args: "txt")

    def check() -> Never:
        raise DeadlineExceededError

    expired_deadline = SimpleNamespace(check=check)

    with pytest.raises(ProcessingTimeoutError) as caught:
        process_document_sync(b"hello", "note.txt", deadline=expired_deadline)

    expected_code = "processing_timeout"
    assert caught.value.code == expected_code, "an expired deadline was not mapped"
