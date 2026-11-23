# Copyright (c) 2026 Nikolai Zelensky

"""Tests for document engine pipeline."""

from __future__ import annotations

import asyncio
import io
import stat
import threading
import zipfile
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import IO, TYPE_CHECKING, Never, Self

import aiohttp
import pymupdf
import pytest
import starlette.formparsers

import audiodoc.document_engine.extractors.djvu as djvu_module
import audiodoc.document_engine.extractors.djvu.text_layer as text_layer_module
from audiodoc.common.work_queue import WorkQueue
from audiodoc.document_engine import (
    pipeline,
    process_document_sync,
    runner,
)
from audiodoc.document_engine import pipeline as pipeline_module
from audiodoc.document_engine.extractors import REGISTRY, _odf
from audiodoc.document_engine.extractors import pdf as pdf_module
from audiodoc.document_engine.extractors.djvu.tools import DjvuTools
from audiodoc.document_engine.guards import zip_archive as zip_guard
from audiodoc.errors.base import BackendError
from audiodoc.errors.documents import DocumentRejectedError, UnsupportedFormatError
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
from tests.support.server import live_server

__all__ = ["live_server"]

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tests.support.server import LiveServer

ZipEntry = tuple[str | zipfile.ZipInfo, bytes]


def _make_nested_archive() -> bytes:
    """Create a small nested ZIP archive."""
    nested = io.BytesIO()
    with zipfile.ZipFile(nested, "w") as inner:
        inner.writestr("nested.txt", b"nested")
    return nested.getvalue()


def _make_symlink_entry() -> ZipEntry:
    """Create a symbolic-link ZIP member."""
    link = zipfile.ZipInfo("word/link")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    return link, b"target"


def _limited_zip(
    monkeypatch: pytest.MonkeyPatch,
    limit_name: str,
    limit: int,
    entries: list[ZipEntry] | None = None,
) -> tuple[bytes, list[ZipEntry]]:
    """Create an archive with a reduced configured limit."""
    monkeypatch.setattr(zip_guard, limit_name, limit)
    return b"<d/>", entries or []


def _write_zip(document: bytes, entries: list[ZipEntry]) -> bytes:
    """Serialize supplied members into a small DOCX-like archive."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", document)
        archive.writestr("word/", b"")
        archive.writestr("word/empty.bin", b"")
        for name, payload in entries:
            archive.writestr(name, payload)
    return output.getvalue()


def _lie_about_declared_size(data: bytes) -> bytes:
    """Change the central-directory size without changing member contents."""
    corrupted = bytearray(data)
    position = data.find(b"PK\x01\x02")
    assert position >= 0
    corrupted[position + 24 : position + 28] = (1).to_bytes(4, "little")
    return bytes(corrupted)


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
            [("word/embedded.bin", _make_nested_archive())],
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
        "symlink": lambda: (b"<d/>", [_make_symlink_entry()]),
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
    data = _write_zip(document, entries)

    if attack == "declared_size_lie":
        return _lie_about_declared_size(data)
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
        assert isinstance(payload, dict)
        return response.status, payload


def _assert_upload_clean(
    opened: list[IO[bytes]],
    directory: Path,
) -> None:
    assert opened
    assert all(handle.closed for handle in opened)
    assert list(directory.iterdir()) == []


def _billion_laughs_payload() -> bytes:
    declarations = ['<!ENTITY lol "lol">']
    for index in range(1, 10):
        previous = "lol" if index == 1 else f"lol{index - 1}"
        expansion = f"&{previous};" * 10
        declarations.append(f'<!ENTITY lol{index} "{expansion}">')
    document = (
        '<?xml version="1.0"?><!DOCTYPE lolz ['
        + "".join(declarations)
        + "]><lolz>&lol9;</lolz>"
    )
    return document.encode()


class _HugePdfPage:
    rect = SimpleNamespace(width=72_000.0, height=72_000.0)

    def get_pixmap(self, **_kwargs: object) -> None:
        raise AssertionError

    def get_text(self, kind: str) -> str:
        assert kind == "text"
        return ""


class _HugePdfDocument:
    page_count = 1

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False

    def __iter__(self) -> Iterator[_HugePdfPage]:
        return iter([_HugePdfPage()])


UNICODE_TEXT = "Привет 😀"


PRIVATE_DETAIL = "PRIVATE_PARSER_DETAIL"


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


EXPECTED_FORMATS = {
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "attack",
    [
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
    ],
)
async def test_zip_abuse_returns_clean_error_and_removes_upload(
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

    assert status == 400, attack
    assert payload == {
        "detail": "Документ содержит повреждённый или недопустимый архив",
        "code": "document_rejected",
    }
    _assert_upload_clean(opened, live_server.temp_dir)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        _billion_laughs_payload(),
        (
            b'<?xml version="1.0"?><!DOCTYPE root ['
            b'<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
            b"<root>&xxe;</root>"
        ),
    ],
)
async def test_xml_entity_attacks_return_clean_error_and_remove_upload(
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

    assert status == 400
    assert result == {
        "detail": "XML содержит запрещённые конструкции",
        "code": "document_rejected",
    }
    _assert_upload_clean(opened, live_server.temp_dir)


@pytest.mark.asyncio
async def test_huge_pdf_page_returns_clean_error_and_removes_upload(
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
        lambda **_kwargs: _HugePdfDocument(),
    )
    opened = _track_upload_files(monkeypatch, live_server.temp_dir)
    status, result = await _post_document(live_server, b"fake-pdf", "huge.pdf")

    assert status == 400
    assert result == {
        "detail": "Страница PDF слишком велика для безопасного OCR",
        "code": "document_rejected",
    }
    _assert_upload_clean(opened, live_server.temp_dir)


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


@pytest.mark.parametrize(
    ("builder", "filename", "expected_format", "expected_text"),
    [
        (create_docx, "test.docx", "docx", "Document engine works!"),
        (create_xlsx, "test.xlsx", "xlsx", "Document engine"),
        (create_pptx, "test.pptx", "pptx", "Document engine works!"),
        (create_odt, "test.odt", "odt", "Document engine works!"),
        (create_ods, "test.ods", "ods", "Document engine"),
        (create_odp, "test.odp", "odp", "Document engine works!"),
        (create_epub, "test.epub", "epub", "Document engine works!"),
        (create_fb2, "test.fb2", "fb2", "Document engine works!"),
        (create_pdf, "test.pdf", "pdf", "PDF document test"),
    ],
)
def test_office_and_pdf_formats(
    builder: object,
    filename: object,
    expected_format: object,
    expected_text: object,
    tmp_path: Path,
) -> None:
    data = builder()
    path = tmp_path / filename
    path.write_bytes(data)

    result = process_document_sync(path.read_bytes(), path.name)

    assert result["format"] == expected_format
    assert expected_text in result["text"]
    if expected_format == "pptx":
        assert "--- Слайд 1 ---" in result["text"]
    assert result["characters"] == len(result["text"])


@pytest.mark.parametrize(
    ("data", "name", "expected_format", "expected_text"),
    CASES,
)
def test_text_formats(
    data: object,
    name: object,
    expected_format: object,
    expected_text: object,
    tmp_path: Path,
) -> None:
    path = tmp_path / name
    path.write_bytes(data)

    result = process_document_sync(path.read_bytes(), path.name)

    assert result["format"] == expected_format
    assert expected_text in result["text"]
    assert result["characters"] == len(result["text"])


def test_fb2_extraction(tmp_path: Path) -> None:
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


def test_standalone_image_is_rejected_by_document_engine() -> None:
    with pytest.raises(UnsupportedFormatError):
        process_document_sync(b"\x89PNG\r\n\x1a\n", "image.png")


def test_registry_contains_all_supported_document_formats() -> None:
    assert set(REGISTRY) == EXPECTED_FORMATS
    assert REGISTRY["txt"] is REGISTRY["md"]


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
        return filetype.upper()

    monkeypatch.setattr(
        "audiodoc.document_engine.extractors.extract_odf",
        fake_extract_odf,
    )

    # ODF adapters resolve the shared extract_odf function at call time.
    # Rebuild only the three entries to make their dispatch observable.
    for kind in ("odt", "ods", "odp"):
        assert _odf(kind)(b"odf") == kind.upper()

    assert calls == [(b"odf", "odt"), (b"odf", "ods"), (b"odf", "odp")]


def test_pipeline_dispatches_registered_extractor_and_builds_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pipeline, "detect_format", lambda _data, _name: "txt")
    monkeypatch.setitem(
        pipeline.REGISTRY,
        "txt",
        lambda _data, **_kwargs: "  extracted text  ",
    )

    assert pipeline.process_document_sync(b"payload", "note.txt") == {
        "format": "txt",
        "text": "extracted text",
        "characters": 14,
        "truncated": False,
    }


def test_pipeline_validates_zip_before_calling_extractor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = []
    monkeypatch.setattr(pipeline, "detect_format", lambda _data, _name: "docx")
    monkeypatch.setattr(
        pipeline,
        "validate_zip_archive",
        lambda _data: events.append("validated"),
    )
    monkeypatch.setitem(
        pipeline.REGISTRY,
        "docx",
        lambda _data, **_kwargs: events.append("extracted") or "word",
    )

    result = pipeline.process_document_sync(b"zip payload", "note.docx")

    assert events == ["validated", "extracted"]
    assert result["format"] == "docx"
    assert result["text"] == "word"
    assert result["truncated"] is False


def test_pipeline_preserves_safe_empty_and_unsupported_document_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(DocumentRejectedError, match="Документ пуст"):
        process_document_sync(b"", "empty.txt")

    monkeypatch.setattr(pipeline, "detect_format", lambda _data, _name: None)
    with pytest.raises(UnsupportedFormatError):
        process_document_sync(b"image", "image.png")


def test_legacy_processor_shim_has_been_removed() -> None:
    processor_path = (
        Path(__file__).parents[3] / "audiodoc" / "document_engine" / "processor.py"
    )
    assert not processor_path.exists()


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

    assert result == {
        "format": "txt",
        "text": "ok",
        "characters": 2,
        "truncated": False,
    }
    assert calls[0][:3] == (b"body", "note.txt", None)
    assert calls[0][3] is not None
    assert calls[0][4] != main_thread


def test_pipeline_applies_client_character_hint_and_marks_truncation() -> None:
    result = process_document_sync(b"0123456789", "note.txt", max_characters=5)
    assert result == {
        "format": "txt",
        "text": "01234",
        "characters": 5,
        "truncated": True,
    }


def test_pipeline_exact_budget_is_not_truncated() -> None:
    result = process_document_sync(b"12345", "note.txt", max_characters=5)

    assert result == {
        "format": "txt",
        "text": "12345",
        "characters": 5,
        "truncated": False,
    }


def test_pipeline_truncates_one_character_over_budget() -> None:
    result = process_document_sync(b"123456", "note.txt", max_characters=5)

    assert result == {
        "format": "txt",
        "text": "12345",
        "characters": 5,
        "truncated": True,
    }


def test_pipeline_rejects_invalid_character_hint() -> None:
    with pytest.raises(DocumentRejectedError, match="лимит длины текста"):
        process_document_sync(b"hello", "note.txt", max_characters=0)


def test_pipeline_hides_unexpected_extractor_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pipeline, "detect_format", lambda _data, _name: "txt")

    def fail_extractor(_data: object, **_kwargs: object) -> Never:
        error_message = "/private/path/to/parser-internal-error"
        raise RuntimeError(error_message)

    monkeypatch.setitem(pipeline.REGISTRY, "txt", fail_extractor)

    with pytest.raises(DocumentRejectedError) as error:
        process_document_sync(b"payload", "note.txt")

    assert error.value.public_message == (
        "\u041d\u0435 удалось прочитать документ: файл повреждён или имеет "
        "неподдерживаемую структуру"
    )
    assert "/private/path/to/parser-internal-error" not in error.value.public_message
