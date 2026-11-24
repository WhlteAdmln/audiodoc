# Copyright (c) 2026 Nikolai Zelensky

"""Tests for main."""

from __future__ import annotations

import asyncio
import multiprocessing
import os
import re
import threading
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

import aiohttp
import pytest
import starlette.formparsers
from fastapi.testclient import TestClient

import audiodoc.main as main_module
import audiodoc.transcription.model as model_module
from audiodoc.api import ready as ready_module
from audiodoc.config import Settings, load_settings, settings
from audiodoc.document_engine.limits import MAX_CONCURRENT_DOCUMENTS
from audiodoc.errors.base import ServerBusyError
from audiodoc.transcription.model import ModelHolder
from tests.support.bot_client import upload_file
from tests.support.builders import create_wav
from tests.support.import_safety import check_import_safety
from tests.support.server import LiveServer, LiveServerOptions, fixture_live_server
from tests.support.spooled_files import TrackedSpooledTemporaryFile
from tests.support.whisper import no_native_tools, silent_model
from tests.support.work_queues import QueueCapacity, measure_capacity

if TYPE_CHECKING:
    from collections.abc import Iterable

    from fastapi import FastAPI

    from audiodoc.common.work_queue import WorkQueue

__all__ = ["fixture_live_server"]


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


class _TempDirectoryPermissionError(PermissionError):
    """Raised when temporary storage cannot be prepared."""

    def __init__(self) -> None:
        """Initialize the temporary storage error."""
        super().__init__("Temporary directory is not writable")


async def _hold_queue_slot(
    queue: WorkQueue,
    started: asyncio.Event,
    release: asyncio.Event,
) -> None:
    async with queue.slot():
        started.set()
        await release.wait()


async def _assert_queue_rejects_work(queue: WorkQueue) -> None:
    with pytest.raises(ServerBusyError):
        async with queue.slot():
            pytest.fail("Queue accepted a job during shutdown")


async def _send_and_read(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    request: bytes,
) -> bytes:
    writer.write(request)
    await writer.drain()
    return await asyncio.wait_for(reader.read(), timeout=5)


async def _send_partial_upload(
    writer: asyncio.StreamWriter,
    request: bytes,
    body: bytes,
    rolled: threading.Event,
) -> bool:
    writer.write(request)
    writer.write(f"{len(body):X}\r\n".encode("ascii"))
    writer.write(body)
    writer.write(b"\r\n")
    await writer.drain()
    return await asyncio.to_thread(rolled.wait, 5)


async def _run_lifespan_shutdown(application: FastAPI) -> None:
    document_queue = application.state.document_queue
    transcription_queue = application.state.transcription_queue
    started = [asyncio.Event(), asyncio.Event()]
    release_jobs = asyncio.Event()
    entered = asyncio.Event()
    stop = asyncio.Event()

    async def run_lifespan() -> None:
        async with main_module.lifespan(application):
            entered.set()
            await stop.wait()

    lifespan_task = asyncio.create_task(run_lifespan())
    await entered.wait()
    jobs = [
        asyncio.create_task(_hold_queue_slot(queue, event, release_jobs))
        for queue, event in zip(
            (document_queue, transcription_queue), started, strict=True
        )
    ]
    try:
        await _check_shutdown_waits_for_jobs(
            (document_queue, transcription_queue), started, stop, lifespan_task
        )
    finally:
        release_jobs.set()
        stop.set()
        await asyncio.gather(*jobs, lifespan_task)


async def _check_shutdown_waits_for_jobs(
    queues: tuple[object, object],
    started: list[asyncio.Event],
    stop: asyncio.Event,
    lifespan_task: asyncio.Task[None],
) -> None:
    await asyncio.gather(*(event.wait() for event in started))
    stop.set()
    await asyncio.sleep(0)
    assert not lifespan_task.done()
    await asyncio.gather(*(_assert_queue_rejects_work(queue) for queue in queues))


def test_docs_and_openapi_routes_are_disabled_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ENABLE_DOCS", False)
    app = main_module.create_app()
    client = TestClient(app)

    expected_status_code = 404
    assert client.get("/docs").status_code == expected_status_code
    expected_status_code = 404
    assert client.get("/openapi.json").status_code == expected_status_code
    assert app.docs_url is None
    assert app.openapi_url is None


def test_docs_route_can_be_enabled_for_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ENABLE_DOCS", True)
    app = main_module.create_app()
    client = TestClient(app)

    expected_docs_url = "/docs"
    assert app.docs_url == expected_docs_url
    expected_openapi_url = "/openapi.json"
    assert app.openapi_url == expected_openapi_url
    expected_status_code = 200
    assert client.get("/openapi.json").status_code == expected_status_code


def test_create_app_uses_explicit_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ENABLE_DOCS", False)
    app = main_module.create_app(Settings(ENABLE_DOCS=True))
    client = TestClient(app)

    expected_docs_url = "/docs"
    assert app.docs_url == expected_docs_url
    expected_openapi_url = "/openapi.json"
    assert app.openapi_url == expected_openapi_url
    expected_status_code = 200
    assert client.get("/openapi.json").status_code == expected_status_code


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

    expected_document_status = 401
    assert document_status == expected_document_status
    expected_transcribe_status = 401
    assert transcribe_status == expected_transcribe_status
    expected_number = 401
    assert (
        await _upload_without_authorization(document_url, document_path)
        == expected_number
    )
    expected_number = 401
    assert (
        await _upload_without_authorization(transcribe_url, audio_path)
        == expected_number
    )


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
        expected_status = 200
        assert status == expected_status

    for key in ("rotated-document-key", "test-document-key"):
        status, _ = await upload_file(
            f"{live_server.base_url}/process-document",
            document_path,
            key,
        )
        expected_status = 200
        assert status == expected_status


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

    expected_number = 200
    assert (
        await _upload_without_authorization(
            f"{live_server.base_url}/process-document",
            document_path,
        )
        == expected_number
    )
    expected_number = 200
    assert (
        await _upload_without_authorization(
            f"{live_server.base_url}/transcribe",
            audio_path,
        )
        == expected_number
    )


@pytest.mark.asyncio
async def test_live_socket_health_ready_docs_and_request_ids(
    live_server: LiveServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ready_module, "check_native_tools", no_native_tools)

    async with aiohttp.ClientSession() as session:
        request_id = "socket-request-0001"
        async with session.get(
            f"{live_server.base_url}/health",
            headers={"X-Request-ID": request_id},
        ) as response:
            expected_health_status = 200
            assert response.status == expected_health_status
            assert response.headers["x-request-id"] == request_id
            expected_health_state = "ok"
            assert (await response.json())["status"] == expected_health_state

        async with session.get(f"{live_server.base_url}/health") as response:
            generated_id = response.headers["x-request-id"]
            assert re.fullmatch(r"[0-9a-f]{32}", generated_id)

        async with session.get(f"{live_server.base_url}/ready") as response:
            expected_ready_status = 200
            assert response.status == expected_ready_status
            payload = await response.json()
            assert payload["tesseract"] is False
            assert payload["djvulibre"] is False

        async with session.get(f"{live_server.base_url}/docs") as response:
            expected_docs_status = 404
            assert response.status == expected_docs_status

        async with session.get(f"{live_server.base_url}/openapi.json") as response:
            expected_openapi_status = 404
            assert response.status == expected_openapi_status


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
            expected_status = 200
            assert response.status == expected_status
        async with session.get(f"{live_server.base_url}/openapi.json") as response:
            expected_status = 200
            assert response.status == expected_status


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
        response = await _send_and_read(reader, writer, request.encode("ascii"))
    finally:
        writer.close()
        await writer.wait_closed()

    status_line = b" 413 "
    assert status_line in response.split(b"\r\n", maxsplit=1)[0]
    assert f"x-request-id: {request_id}".encode() in response.lower()
    error_message = b"Request body too large"
    assert error_message in response


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
        expected_status = 413
        assert response.status == expected_status
        assert await response.json() == {"detail": "Request body too large"}


@pytest.mark.asyncio
async def test_client_disconnect_during_upload_closes_temporary_file(
    live_server: LiveServer,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    rolled = threading.Event()
    closed = threading.Event()

    def track_spooled_file(**_kwargs: object) -> TrackedSpooledTemporaryFile:
        return TrackedSpooledTemporaryFile(tmp_path, rolled, closed)

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
        rolled_in_time = await _send_partial_upload(
            writer, request.encode("ascii"), multipart_body, rolled
        )
    finally:
        writer.close()
        await writer.wait_closed()

    assert rolled_in_time
    assert await asyncio.to_thread(closed.wait, 5)
    expected_empty = []
    assert list(live_server.temp_dir.iterdir()) == expected_empty, (
        "expected an empty list"
    )


def test_health_route_reports_model_state_without_starting_lifespan() -> None:
    application = main_module.create_app(
        Settings(WHISPER_MODEL_SIZE="small-test", WHISPER_MODEL_PATH="")
    )
    application.state.model_holder = ModelHolder(application.state.settings)

    response = TestClient(application).get("/health")

    expected_status_code = 200
    assert response.status_code == expected_status_code
    assert response.json() == {
        "status": "ok",
        "model": "small-test",
        "loaded": False,
    }


def test_health_route_reports_local_model_directory_name() -> None:
    application = main_module.create_app(
        Settings(WHISPER_MODEL_PATH="/srv/audiodoc/models/custom-whisper")
    )
    application.state.model_holder = ModelHolder(application.state.settings)

    response = TestClient(application).get("/health")

    expected_status_code = 200
    assert response.status_code == expected_status_code
    expected_model = "custom-whisper"
    assert response.json()["model"] == expected_model


def test_health_and_ready_use_application_model_holder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded_application = main_module.create_app()
    loaded_application.state.model_holder = ModelHolder(
        loaded_application.state.settings
    )
    monkeypatch.setattr(loaded_application.state.model_holder, "_model", object())

    monkeypatch.setattr(ready_module, "check_native_tools", no_native_tools)

    client = TestClient(loaded_application)

    health_response = client.get("/health")
    ready_response = client.get("/ready")

    expected_status_code = 200
    assert health_response.status_code == expected_status_code
    assert health_response.json()["loaded"] is True
    expected_status_code = 200
    assert ready_response.status_code == expected_status_code
    assert ready_response.json()["model_loaded"] is True

    unloaded_application = main_module.create_app()
    unloaded_application.state.model_holder = ModelHolder(
        unloaded_application.state.settings
    )
    monkeypatch.setattr(unloaded_application.state.model_holder, "_model", None)

    other_client = TestClient(unloaded_application)

    assert other_client.get("/health").json()["loaded"] is False
    assert other_client.get("/ready").json()["model_loaded"] is False


def test_app_registers_all_expected_routes() -> None:
    app = main_module.create_app()
    expected_title = "audiodoc"
    assert app.title == expected_title
    paths = app.openapi()["paths"]

    health_method = "get"
    assert health_method in paths["/health"]
    ready_method = "get"
    assert ready_method in paths["/ready"]
    transcribe_method = "post"
    assert transcribe_method in paths["/transcribe"]
    document_method = "post"
    assert document_method in paths["/process-document"]


def _queue_settings() -> Settings:
    return Settings(
        MAX_CONCURRENT_TRANSCRIPTIONS=3,
        MAX_WAITING_TRANSCRIPTIONS=2,
        MAX_WAITING_DOCUMENTS=1,
    )


def test_create_app_builds_independent_queues_from_settings() -> None:
    configured_settings = _queue_settings()
    first_app = main_module.create_app(configured_settings)
    second_app = main_module.create_app(configured_settings)
    actual = (
        first_app.state.transcription_queue is second_app.state.transcription_queue,
        first_app.state.document_queue is second_app.state.document_queue,
    )
    expected = (False, False)
    assert actual == expected, "every application must own its queues"


def test_create_app_sizes_transcription_queue_from_settings() -> None:
    app = main_module.create_app(_queue_settings())
    actual = measure_capacity(app.state.transcription_queue)
    expected = QueueCapacity(active=3, waiting=2)
    assert actual == expected, "the transcription queue ignored its settings"


def test_create_app_sizes_document_queue_from_settings() -> None:
    app = main_module.create_app(_queue_settings())
    actual = measure_capacity(app.state.document_queue)
    expected = QueueCapacity(active=MAX_CONCURRENT_DOCUMENTS, waiting=1)
    assert actual == expected, "the document queue ignored its settings"


def test_lifespan_creates_independent_model_holders(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    first_settings = Settings(WHISPER_MODEL_SIZE="tiny")
    second_settings = Settings(WHISPER_MODEL_SIZE="base")
    received_settings: list[Settings] = []
    holders: list[ModelHolder] = []

    def build_model(configured_settings: Settings) -> object:
        received_settings.append(configured_settings)
        return silent_model()

    monkeypatch.setattr(main_module.os, "umask", lambda _mask: 0o022)
    monkeypatch.setattr(
        main_module, "check_security_settings", lambda _configured: None
    )
    monkeypatch.setattr(main_module, "ensure_temp_dir", lambda: tmp_path)
    monkeypatch.setattr(main_module, "cleanup_stale_files", lambda: None)
    monkeypatch.setattr(model_module, "_build_model", build_model)

    first_app = main_module.create_app(first_settings)
    second_app = main_module.create_app(second_settings)
    queues = [
        first_app.state.transcription_queue,
        first_app.state.document_queue,
        second_app.state.transcription_queue,
        second_app.state.document_queue,
    ]

    assert not hasattr(first_app.state, "model_holder")
    assert not hasattr(second_app.state, "model_holder")
    assert queues[0] is not queues[2]
    assert queues[1] is not queues[3]

    async def run_lifespans() -> None:
        async with main_module.lifespan(first_app):
            holders.append(first_app.state.model_holder)
            assert first_app.state.model_holder.is_loaded is True
        async with main_module.lifespan(second_app):
            holders.append(second_app.state.model_holder)
            assert second_app.state.model_holder.is_loaded is True

        for queue in queues:
            with pytest.raises(ServerBusyError):
                async with queue.slot():
                    pytest.fail("Queue accepted work after its application stopped")

    asyncio.run(run_lifespans())

    first_holder, second_holder = holders[0], holders[1]
    assert first_holder is not second_holder
    assert first_app.state.model_holder is first_holder
    assert second_app.state.model_holder is second_holder
    assert received_settings == [first_settings, second_settings]


def test_lifespan_checks_configuration_prepares_storage_and_loads_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events = []

    monkeypatch.setattr(
        main_module.os, "umask", lambda mask: events.append(("umask", mask))
    )
    monkeypatch.setattr(
        main_module,
        "check_security_settings",
        lambda configured: events.append(("security", configured)),
    )
    monkeypatch.setattr(
        main_module,
        "ensure_temp_dir",
        lambda: events.append(("temp", tmp_path)) or tmp_path,
    )
    monkeypatch.setattr(
        main_module,
        "cleanup_stale_files",
        lambda: events.append(("cleanup", None)),
    )

    application = main_module.create_app()
    monkeypatch.setattr(
        model_module,
        "_build_model",
        lambda _configured_settings: silent_model(),
    )

    with TestClient(application) as client:
        response = client.get("/health")
        expected_status_code = 200
        assert response.status_code == expected_status_code
        assert response.json()["loaded"] is True

    assert events == [
        ("umask", 0o077),
        ("security", application.state.settings),
        ("temp", tmp_path),
        ("cleanup", None),
    ]


def test_lifespan_redacts_configured_api_keys(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configured_settings = load_settings(
        {
            "AUDIODOC_AUDIO_KEY": "audio-secret",
            "AUDIODOC_DOCUMENT_KEY": "document-secret",
        }
    )
    application = main_module.create_app(configured_settings)
    logging_calls: list[tuple[str, tuple[str, ...]]] = []

    def capture_logging(level: str, secrets: Iterable[str]) -> None:
        logging_calls.append((level, tuple(secrets)))

    monkeypatch.setattr(main_module, "configure_logging", capture_logging)
    monkeypatch.setattr(main_module.os, "umask", lambda _mask: 0o077)
    monkeypatch.setattr(main_module, "ensure_temp_dir", lambda: tmp_path)
    monkeypatch.setattr(main_module, "cleanup_stale_files", lambda: None)
    monkeypatch.setattr(
        model_module,
        "_build_model",
        lambda _configured_settings: silent_model(),
    )

    with TestClient(application):
        pass

    assert logging_calls == [
        ("INFO", ("audio-secret", "document-secret")),
    ]


@pytest.mark.parametrize(
    ("whisper_key", "document_key", "expected_message"),
    [
        ("", "document-test-key", "AUDIODOC_AUDIO_KEY"),
        (
            "shared-test-key",
            "shared-test-key",
            "must not share any key values",
        ),
    ],
)
def test_lifespan_rejects_invalid_api_keys(
    monkeypatch: pytest.MonkeyPatch,
    whisper_key: str,
    document_key: str,
    expected_message: str,
) -> None:
    monkeypatch.setattr(main_module.os, "umask", lambda _mask: 0o022)
    monkeypatch.setattr(settings, "AUDIODOC_AUDIO_KEY", whisper_key)
    monkeypatch.setattr(settings, "AUDIODOC_DOCUMENT_KEY", document_key)
    monkeypatch.setattr(settings, "ALLOW_UNAUTHENTICATED", False)

    with (
        pytest.raises(RuntimeError, match=expected_message),
        TestClient(main_module.create_app()),
    ):
        pass


def test_lifespan_fails_when_temp_directory_is_not_writable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    def fail_ensure_temp_dir() -> None:
        raise _TempDirectoryPermissionError

    monkeypatch.setattr(main_module.os, "umask", lambda _mask: 0o022)
    monkeypatch.setattr(
        main_module,
        "check_security_settings",
        lambda _configured: None,
    )
    monkeypatch.setattr(main_module, "ensure_temp_dir", fail_ensure_temp_dir)
    monkeypatch.setattr(
        main_module,
        "cleanup_stale_files",
        lambda: events.append("cleanup"),
    )
    monkeypatch.setattr(
        model_module,
        "_build_model",
        lambda _configured_settings: events.append("model") or silent_model(),
    )

    with (
        pytest.raises(
            PermissionError,
            match="Temporary directory is not writable",
        ),
        TestClient(main_module.create_app()),
    ):
        pass

    expected_empty = []
    assert events == expected_empty, "expected an empty list"


def test_lifespan_waits_for_running_job_before_shutdown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(main_module.os, "umask", lambda _mask: 0o077)
    monkeypatch.setattr(
        main_module,
        "check_security_settings",
        lambda _configured: None,
    )
    monkeypatch.setattr(main_module, "ensure_temp_dir", lambda: tmp_path)
    monkeypatch.setattr(main_module, "cleanup_stale_files", lambda: None)
    monkeypatch.setattr(
        model_module,
        "_build_model",
        lambda _configured_settings: silent_model(),
    )

    application = main_module.create_app()
    asyncio.run(_run_lifespan_shutdown(application))


def test_import_audiodoc_main_has_no_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = Path(__file__).resolve().parents[2]
    path = os.environ.get("PATH", os.defpath)

    for name in tuple(os.environ):
        monkeypatch.delenv(name, raising=False)

    clean_environment = {
        "HOME": str(tmp_path),
        "PATH": path,
        "PYTHONPATH": str(project_root),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "TMPDIR": str(tmp_path),
    }
    for name, value in clean_environment.items():
        monkeypatch.setenv(name, value)

    context = multiprocessing.get_context("spawn")
    process = context.Process(
        target=check_import_safety,
        args=(str(tmp_path),),
    )

    process.start()
    process.join(timeout=30)

    if process.is_alive():
        process.terminate()
        process.join()
        pytest.fail("Import safety child process timed out")

    assert process.exitcode == 0
