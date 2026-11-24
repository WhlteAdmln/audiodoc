# Copyright (c) 2026 Nikolai Zelensky

"""Tests for common limited upload."""

import asyncio
import contextlib
import io
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException

import audiodoc.common.limited_upload as upload_limits
from audiodoc.common.limited_upload import read_upload_limited, save_upload_limited


def _upload(data: bytes, filename: str = "договор.pdf") -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename=filename)


@pytest.fixture(name="small_chunks")
def fixture_small_chunks(monkeypatch: pytest.MonkeyPatch) -> int:
    """Read uploads in small chunks so a few bytes span several reads."""
    chunk_size = 3
    monkeypatch.setattr(upload_limits, "CHUNK_SIZE", chunk_size)
    return chunk_size


@pytest.mark.parametrize(
    "data", [b"", b"\x00", b"12345", b"\xff\xfe\x00\r\n"], ids=repr
)
def test_read_returns_upload_within_limit(data: bytes) -> None:
    result = asyncio.run(read_upload_limited(_upload(data), 5))

    assert result == data, "an upload within the limit changed"


@pytest.mark.usefixtures("small_chunks")
def test_read_joins_several_chunks() -> None:
    data = b"\x00ab\ncd\xfeg"

    result = asyncio.run(read_upload_limited(_upload(data), len(data)))

    assert result == data, "chunks were lost or reordered"


@pytest.mark.parametrize(("size", "limit"), [(6, 5), (1, 0), (3 * 1024 * 1024, 1)])
def test_read_rejects_upload_over_limit(size: int, limit: int) -> None:
    with pytest.raises(HTTPException) as caught:
        asyncio.run(read_upload_limited(_upload(b"z" * size), limit))

    expected_status_code = 413
    assert caught.value.status_code == expected_status_code, "oversized read accepted"


@pytest.mark.usefixtures("small_chunks")
def test_read_rejects_when_a_later_chunk_crosses_the_limit() -> None:
    with pytest.raises(HTTPException) as caught:
        asyncio.run(read_upload_limited(_upload(b"abcdefg"), 6))

    expected_status_code = 413
    assert caught.value.status_code == expected_status_code, "the limit was crossed"


@pytest.mark.parametrize(
    ("limit", "expected_detail"),
    [
        (5, "Файл слишком большой. Максимальный размер: 0 МБ."),
        (7 * 1024 * 1024, "Файл слишком большой. Максимальный размер: 7 МБ."),
    ],
)
def test_read_reports_limit_in_megabytes(limit: int, expected_detail: str) -> None:
    with pytest.raises(HTTPException) as caught:
        asyncio.run(read_upload_limited(_upload(b"q" * (limit + 1)), limit))

    assert caught.value.detail == expected_detail, "wrong user-facing message"


def test_save_writes_upload_within_limit(tmp_path: Path) -> None:
    data = b"\x00OggS\xff" * 7
    target = tmp_path / "voice.ogg"
    asyncio.run(save_upload_limited(_upload(data), target, len(data)))

    written = target.read_bytes()

    assert written == data, "saved bytes differ from the upload"


@pytest.mark.usefixtures("small_chunks")
def test_save_returns_number_of_written_bytes(tmp_path: Path) -> None:
    data = b"RIFF\x00\x01wave"

    saved = asyncio.run(save_upload_limited(_upload(data), tmp_path / "a.wav", 64))

    assert saved == len(data), "wrong byte count"


@pytest.mark.usefixtures("small_chunks")
def test_save_rejects_upload_over_limit(tmp_path: Path) -> None:
    with pytest.raises(HTTPException) as caught:
        asyncio.run(save_upload_limited(_upload(b"1234567"), tmp_path / "v.ogg", 5))

    expected_status_code = 413
    assert caught.value.status_code == expected_status_code, "oversized save accepted"


@pytest.mark.usefixtures("small_chunks")
def test_save_stops_before_the_chunk_that_crosses_the_limit(tmp_path: Path) -> None:
    target = tmp_path / "voice.ogg"
    with contextlib.suppress(HTTPException):
        asyncio.run(save_upload_limited(_upload(b"abcdefgh"), target, 5))

    written = target.read_bytes()

    expected_written = b"abc"
    assert written == expected_written, "bytes past the limit reached the disk"


@given(
    data=st.binary(max_size=4096),
    limit=st.integers(min_value=0, max_value=1024),
    chunk_size=st.integers(min_value=1, max_value=97),
)
@settings(max_examples=200)
def test_save_never_writes_more_than_limit(
    tmp_path_factory: pytest.TempPathFactory, data: bytes, limit: int, chunk_size: int
) -> None:
    destination = tmp_path_factory.mktemp("upload") / "upload.bin"
    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(upload_limits, "CHUNK_SIZE", chunk_size)
        with contextlib.suppress(HTTPException):
            asyncio.run(save_upload_limited(_upload(data), destination, limit))

    assert destination.stat().st_size <= limit, "the file grew past the limit"


@given(data=st.data(), chunk_size=st.integers(min_value=1, max_value=97))
@settings(max_examples=100)
def test_save_keeps_every_upload_that_fits(
    tmp_path_factory: pytest.TempPathFactory, data: st.DataObject, chunk_size: int
) -> None:
    payload = data.draw(st.binary(max_size=2048))
    limit = data.draw(st.integers(min_value=len(payload), max_value=4096))
    destination = tmp_path_factory.mktemp("upload") / "upload.bin"
    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(upload_limits, "CHUNK_SIZE", chunk_size)
        asyncio.run(save_upload_limited(_upload(payload), destination, limit))

    assert destination.read_bytes() == payload, "an upload that fits was changed"
