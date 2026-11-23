# Copyright (c) 2026 Nikolai Zelensky

"""Tests for common limited upload."""

import asyncio
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException

import audiodoc.common.limited_upload as upload_limits
from audiodoc.common.limited_upload import read_upload_limited, save_upload_limited


def test_read_upload_limited_accepts_file_at_limit() -> None:
    upload = UploadFile(file=io.BytesIO(b"12345"), filename="a.txt")
    expected_run = b"12345"
    assert asyncio.run(read_upload_limited(upload, 5)) == expected_run


def test_read_upload_limited_rejects_file_over_limit() -> None:
    upload = UploadFile(file=io.BytesIO(b"123456"), filename="a.txt")
    with pytest.raises(HTTPException) as error:
        asyncio.run(read_upload_limited(upload, 5))
    expected_status_code = 413
    assert error.value.status_code == expected_status_code
    expected_detail = "Файл слишком большой. Максимальный размер: 0 МБ."
    assert error.value.detail == expected_detail


def test_save_upload_limited_rejects_file_over_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(upload_limits, "CHUNK_SIZE", 5)
    upload = UploadFile(file=io.BytesIO(b"123456"), filename="voice.ogg")
    target = tmp_path / "voice.ogg"
    with pytest.raises(HTTPException) as error:
        asyncio.run(save_upload_limited(upload, target, 5))
    expected_status_code = 413
    assert error.value.status_code == expected_status_code
    expected_read_bytes = b"12345"
    assert target.read_bytes() == expected_read_bytes


@given(
    data=st.binary(max_size=4096),
    limit=st.integers(min_value=1, max_value=1024),
)
@settings(max_examples=200)
def test_save_upload_limited_never_writes_more_than_limit(
    data: bytes,
    limit: int,
) -> None:
    with TemporaryDirectory() as temp_dir:
        destination = Path(temp_dir) / "upload.bin"
        upload = UploadFile(
            file=io.BytesIO(data),
            filename="upload.bin",
        )

        with patch.object(upload_limits, "CHUNK_SIZE", 32):
            if len(data) > limit:
                with pytest.raises(HTTPException) as error:
                    asyncio.run(save_upload_limited(upload, destination, limit))

                expected_status_code = 413
                assert error.value.status_code == expected_status_code
            else:
                saved = asyncio.run(save_upload_limited(upload, destination, limit))
                assert saved == len(data)

        assert destination.stat().st_size <= limit
