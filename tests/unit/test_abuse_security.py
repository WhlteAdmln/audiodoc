# Copyright (c) 2026 Nikolai Zelensky
"""Offline regression tests for document abuse and process isolation."""

from __future__ import annotations

import io
import os
import stat
import sys
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import IO, TYPE_CHECKING, Any, Self

import aiohttp
import pytest
import starlette.formparsers
from PIL import Image

from backend.common import subprocess_runner
from backend.common.subprocess_runner import (
    SubprocessTimeoutError,
    run_limited,
)
from backend.document_engine import pipeline as pipeline_module
from backend.document_engine.extractors import pdf as pdf_module
from backend.document_engine.guards import zip_archive as zip_guard
from backend.document_engine.ocr import recognize as recognize_module
from backend.document_engine.ocr import tesseract as tesseract_module
from backend.errors.documents import DocumentRejectedError
from tests.support.server import LiveServer, live_server

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = ["live_server"]

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

    def tracked(*args: Any, **kwargs: Any) -> IO[bytes]:
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
        "detail": "Документ содержит повреждённый или недопустимый архив"
    }
    _assert_upload_clean(opened, live_server.temp_dir)


def test_zip_rejects_nonempty_member_with_zero_compressed_size() -> None:
    item = zipfile.ZipInfo("member.bin")
    item.file_size = 1
    item.compress_size = 0

    with pytest.raises(ValueError, match="Подозрительный размер сжатого файла"):
        zip_guard._validate_archive_entry(item, 0)


@pytest.mark.parametrize(
    "case",
    [
        (
            "MAX_ARCHIVE_FILE_SIZE",
            2,
            3,
            0,
            10,
            "Actual ZIP member size exceeds the limit",
        ),
        (
            "MAX_ARCHIVE_UNPACKED_SIZE",
            4,
            2,
            3,
            10,
            "Превышен общий лимит распакованного размера архива",
        ),
        (
            "MAX_ARCHIVE_COMPRESSION_RATIO",
            2,
            3,
            0,
            1,
            "Actual ZIP compression ratio is too high",
        ),
    ],
)
def test_zip_checks_actual_member_limits(
    case: tuple[str, int, int, int, int, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        limit_name,
        limit,
        actual_size,
        total_size,
        compressed_size,
        expected_message,
    ) = case
    monkeypatch.setattr(zip_guard, limit_name, limit)
    item = zipfile.ZipInfo("member.bin")
    item.compress_size = compressed_size

    with pytest.raises(ValueError, match=expected_message):
        zip_guard._validate_actual_member_size(item, actual_size, total_size)


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
    assert result == {"detail": "XML содержит запрещённые конструкции"}
    _assert_upload_clean(opened, live_server.temp_dir)


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
    assert result == {"detail": "Страница PDF слишком велика для безопасного OCR"}
    _assert_upload_clean(opened, live_server.temp_dir)


def _process_state(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _assert_process_reaped(pid: int) -> None:
    deadline = time.monotonic() + 5
    while _process_state(pid) and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not _process_state(pid), f"Process {pid} still exists after timeout"


def test_timeout_kills_process_group_and_reaps_children(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = subprocess_runner.tempfile.TemporaryFile
    opened: list[IO[bytes]] = []

    def tracked(*args: Any, **kwargs: Any) -> IO[bytes]:
        kwargs["dir"] = tmp_path
        handle = original(*args, **kwargs)
        opened.append(handle)
        return handle

    monkeypatch.setattr(subprocess_runner.tempfile, "TemporaryFile", tracked)
    pid_file = tmp_path / "processes.txt"
    script = (
        "import os, subprocess, sys, time\n"
        "from pathlib import Path\n"
        "child = subprocess.Popen("
        "[sys.executable, '-c', 'import time; time.sleep(30)'])\n"
        f"Path({str(pid_file)!r}).write_text(f'{{os.getpid()}} {{child.pid}}')\n"
        "time.sleep(30)\n"
    )

    with pytest.raises(SubprocessTimeoutError):
        run_limited([sys.executable, "-c", script], timeout=1, max_output=100)

    parent_pid, child_pid = map(int, pid_file.read_text().split())
    pid_file.unlink()
    _assert_process_reaped(parent_pid)
    _assert_process_reaped(child_pid)
    assert opened
    assert all(handle.closed for handle in opened)
    assert list(tmp_path.iterdir()) == []


def test_ocr_timeout_returns_clean_error_and_removes_image_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directories: list[Path] = []

    def timeout_runner(
        args: list[str],
        *,
        timeout: float,
    ) -> tuple[int, bytes, bytes]:
        image_path = Path(args[1])
        assert image_path.is_file()
        assert args[2:] == ["stdout", "-l", "eng", "--psm", "3"]
        assert timeout > 0
        directories.append(image_path.parent)
        raise SubprocessTimeoutError

    monkeypatch.setattr(tesseract_module, "_get_tesseract_command", lambda: "tesseract")
    monkeypatch.setattr(tesseract_module, "run_limited", timeout_runner)

    with (
        Image.new("RGB", (8, 8)) as image,
        pytest.raises(DocumentRejectedError) as error,
    ):
        recognize_module.recognize_pages(image, "eng")

    assert error.value.status_code == 400
    assert directories
    assert all(not directory.exists() for directory in directories)
