# Copyright (c) 2026 Nikolai Zelensky
"""HTTP behavior tests using the real Uvicorn TCP server."""

from __future__ import annotations

import asyncio
import re
import tempfile
import threading
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

import aiohttp
import pytest
import starlette.formparsers

from audiodoc.api import ready as ready_module
from tests.support.bot_client import upload_file
from tests.support.builders import create_wav
from tests.support.server import LiveServer, LiveServerOptions, live_server

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["live_server"]


async def _upload_without_authorization(url: str, file_path: Path) -> int:
    with file_path.open("rb") as file_handle:
        form = aiohttp.FormData()
        form.add_field("file", file_handle, filename=file_path.name)
        async with (
            aiohttp.ClientSession() as session,
            session.post(url, data=form) as response,
        ):
            await response.read()
            return response.status


@pytest.mark.asyncio
async def test_live_socket_auth_rejects_missing_and_wrong_keys(
    live_server: LiveServer,
    tmp_path: Path,
) -> None:
    document_path = tmp_path / "note.txt"
    document_path.write_text("Socket authentication test.", encoding="utf-8")
    audio_path = tmp_path / "voice.ogg"
    audio_path.write_bytes(b"fake audio")

    document_url = f"{live_server.base_url}/process-document"
    transcribe_url = f"{live_server.base_url}/transcribe"

    document_status, _ = await upload_file(
        document_url,
        document_path,
        live_server.whisper_api_key,
    )
    transcribe_status, _ = await upload_file(
        transcribe_url,
        audio_path,
        live_server.document_api_key,
    )

    assert document_status == 401
    assert transcribe_status == 401
    assert await _upload_without_authorization(document_url, document_path) == 401
    assert await _upload_without_authorization(transcribe_url, audio_path) == 401


@pytest.mark.parametrize(
    "live_server",
    [
        LiveServerOptions(
            whisper_api_key="rotated-whisper-key, test-whisper-key",
            document_api_key="rotated-document-key, test-document-key",
        )
    ],
    indirect=True,
)
@pytest.mark.asyncio
async def test_live_socket_accepts_both_keys_during_rotation(
    live_server: LiveServer,
    tmp_path: Path,
) -> None:
    document_path = tmp_path / "note.txt"
    document_path.write_text("Key rotation test.", encoding="utf-8")
    audio_path = tmp_path / "voice.wav"
    audio_path.write_bytes(create_wav())

    for key in ("rotated-whisper-key", "test-whisper-key"):
        status, _ = await upload_file(
            f"{live_server.base_url}/transcribe",
            audio_path,
            key,
        )
        assert status == 200

    for key in ("rotated-document-key", "test-document-key"):
        status, _ = await upload_file(
            f"{live_server.base_url}/process-document",
            document_path,
            key,
        )
        assert status == 200


@pytest.mark.parametrize(
    "live_server",
    [
        LiveServerOptions(
            whisper_api_key="",
            document_api_key="",
            allow_unauthenticated=True,
        )
    ],
    indirect=True,
)
@pytest.mark.asyncio
async def test_allow_unauthenticated_accepts_uploads_without_keys(
    live_server: LiveServer,
    tmp_path: Path,
) -> None:
    document_path = tmp_path / "note.txt"
    document_path.write_text("Unauthenticated document.", encoding="utf-8")
    audio_path = tmp_path / "voice.wav"
    audio_path.write_bytes(create_wav())

    assert (
        await _upload_without_authorization(
            f"{live_server.base_url}/process-document",
            document_path,
        )
        == 200
    )
    assert (
        await _upload_without_authorization(
            f"{live_server.base_url}/transcribe",
            audio_path,
        )
        == 200
    )


@pytest.mark.asyncio
async def test_live_socket_health_ready_docs_and_request_ids(
    live_server: LiveServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ready_module,
        "_available_tesseract_languages",
        lambda: (False, []),
    )
    monkeypatch.setattr(ready_module.shutil, "which", lambda _name: None)

    async with aiohttp.ClientSession() as session:
        request_id = "socket-request-0001"
        async with session.get(
            f"{live_server.base_url}/health",
            headers={"X-Request-ID": request_id},
        ) as response:
            assert response.status == 200
            assert response.headers["x-request-id"] == request_id
            assert (await response.json())["status"] == "ok"

        async with session.get(f"{live_server.base_url}/health") as response:
            generated_id = response.headers["x-request-id"]
            assert re.fullmatch(r"[0-9a-f]{32}", generated_id)

        async with session.get(f"{live_server.base_url}/ready") as response:
            assert response.status == 200
            payload = await response.json()
            assert payload["tesseract"] is False
            assert payload["djvulibre"] is False

        async with session.get(f"{live_server.base_url}/docs") as response:
            assert response.status == 404

        async with session.get(f"{live_server.base_url}/openapi.json") as response:
            assert response.status == 404


@pytest.mark.parametrize(
    "live_server",
    [LiveServerOptions(enable_docs=True)],
    indirect=True,
)
@pytest.mark.asyncio
async def test_live_socket_docs_are_available_when_enabled(
    live_server: LiveServer,
) -> None:
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{live_server.base_url}/docs") as response:
            assert response.status == 200
        async with session.get(f"{live_server.base_url}/openapi.json") as response:
            assert response.status == 200


@pytest.mark.parametrize(
    "live_server",
    [LiveServerOptions(max_body_size=64)],
    indirect=True,
)
@pytest.mark.asyncio
async def test_live_socket_rejects_declared_body_over_limit(
    live_server: LiveServer,
) -> None:
    parsed_url = urlsplit(live_server.base_url)
    assert parsed_url.hostname is not None
    assert parsed_url.port is not None
    reader, writer = await asyncio.open_connection(
        parsed_url.hostname,
        parsed_url.port,
    )
    request_id = "declared-limit-0001"
    request = (
        "POST /process-document HTTP/1.1\r\n"
        f"Host: {parsed_url.hostname}:{parsed_url.port}\r\n"
        f"Authorization: Bearer {live_server.document_api_key}\r\n"
        "Content-Type: application/octet-stream\r\n"
        "Content-Length: 65\r\n"
        f"X-Request-ID: {request_id}\r\n"
        "Connection: close\r\n"
        "\r\n"
    )
    try:
        writer.write(request.encode("ascii"))
        await writer.drain()
        response = await asyncio.wait_for(reader.read(), timeout=5)
    finally:
        writer.close()
        await writer.wait_closed()

    assert b" 413 " in response.split(b"\r\n", maxsplit=1)[0]
    assert f"x-request-id: {request_id}".encode() in response.lower()
    assert b"Request body too large" in response


@pytest.mark.parametrize(
    "live_server",
    [LiveServerOptions(max_body_size=64)],
    indirect=True,
)
@pytest.mark.asyncio
async def test_live_socket_rejects_chunked_body_over_limit(
    live_server: LiveServer,
) -> None:
    form = aiohttp.FormData()
    form.add_field(
        "file",
        b"x" * 65,
        filename="note.txt",
        content_type="text/plain",
    )
    headers = {
        "Authorization": f"Bearer {live_server.document_api_key}",
    }
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            f"{live_server.base_url}/process-document",
            data=form,
            chunked=True,
            headers=headers,
        ) as response,
    ):
        assert response.status == 413
        assert await response.json() == {"detail": "Request body too large"}


@pytest.mark.asyncio
async def test_client_disconnect_during_upload_closes_temporary_file(
    live_server: LiveServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rolled = threading.Event()
    closed = threading.Event()

    class TrackedSpooledTemporaryFile(tempfile.SpooledTemporaryFile):
        def write(self, value: bytes) -> int:
            written = super().write(value)
            if self._rolled:
                rolled.set()
            return written

        def close(self) -> None:
            try:
                super().close()
            finally:
                closed.set()

    def track_spooled_file(
        *args: object,
        **kwargs: object,
    ) -> tempfile.SpooledTemporaryFile:
        kwargs["max_size"] = 1
        return TrackedSpooledTemporaryFile(*args, **kwargs)

    monkeypatch.setattr(
        starlette.formparsers,
        "SpooledTemporaryFile",
        track_spooled_file,
    )

    parsed_url = urlsplit(live_server.base_url)
    assert parsed_url.hostname is not None
    assert parsed_url.port is not None
    _reader, writer = await asyncio.open_connection(
        parsed_url.hostname,
        parsed_url.port,
    )
    boundary = "incomplete-upload-boundary"
    multipart_body = (
        f"--{boundary}\r\n".encode("ascii")
        + b'Content-Disposition: form-data; name="file"; filename="voice.ogg"\r\n'
        + b"Content-Type: audio/ogg\r\n\r\n"
        + b"x" * (2 * 1024 * 1024)
    )
    request = (
        "POST /transcribe HTTP/1.1\r\n"
        f"Host: {parsed_url.hostname}:{parsed_url.port}\r\n"
        f"Authorization: Bearer {live_server.whisper_api_key}\r\n"
        f"Content-Type: multipart/form-data; boundary={boundary}\r\n"
        "Transfer-Encoding: chunked\r\n"
        "\r\n"
    )

    try:
        writer.write(request.encode("ascii"))
        writer.write(f"{len(multipart_body):X}\r\n".encode("ascii"))
        writer.write(multipart_body)
        writer.write(b"\r\n")
        await writer.drain()

        assert await asyncio.to_thread(rolled.wait, 5)
    finally:
        writer.close()
        await writer.wait_closed()

    assert await asyncio.to_thread(closed.wait, 5)
    assert list(live_server.temp_dir.iterdir()) == []
