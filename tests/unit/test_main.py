# Copyright (c) 2026 Nikolai Zelensky

"""Tests for main."""

from __future__ import annotations

import asyncio
import multiprocessing
import os
import re
import threading
from contextlib import asynccontextmanager
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
from tests.support.whisper import loaded_model_holder, no_native_tools, silent_model
from tests.support.work_queues import QueueCapacity, measure_capacity

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable

    from fastapi import FastAPI

    from audiodoc.common.work_queue import WorkQueue

__all__ = ["fixture_live_server"]


class _TempDirectoryPermissionError(PermissionError):
    """Raised when temporary storage cannot be prepared."""

    def __init__(self) -> None:
        """Initialize the temporary storage error."""
        super().__init__("Temporary directory is not writable")


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


def _upload_path(tmp_path: Path, endpoint: str) -> Path:
    if endpoint.endswith("document"):
        document_path = tmp_path / "note.txt"
        document_path.write_text("Socket authentication test.", encoding="utf-8")
        return document_path
    audio_path = tmp_path / "voice.wav"
    audio_path.write_bytes(create_wav())
    return audio_path


def _pick_key(live_server: LiveServer, choice: str) -> str | None:
    keys = {
        "audio key": live_server.whisper_api_key,
        "document key": live_server.document_api_key,
        "audio key without last character": live_server.whisper_api_key[:-1],
        "document key with suffix": f"{live_server.document_api_key}-extra",
        "audio key in upper case": live_server.whisper_api_key.upper(),
    }
    return keys.get(choice)


async def _live_upload_status(url: str, file_path: Path, key: str | None) -> int:
    if key is None:
        return await _upload_without_authorization(url, file_path)
    status, _ = await upload_file(url, file_path, key)
    return status


async def _get_live(
    url: str, headers: dict[str, str] | None = None
) -> tuple[int, dict[str, str], dict[str, object]]:
    async with (
        aiohttp.ClientSession() as session,
        session.get(url, headers=headers) as response,
    ):
        is_json = response.content_type.endswith("json")
        body = await response.json() if is_json else {}
        lowered = {name.lower(): value for name, value in response.headers.items()}
        return response.status, lowered, body


@asynccontextmanager
async def _live_connection(
    live_server: LiveServer,
) -> AsyncIterator[tuple[asyncio.StreamReader, asyncio.StreamWriter]]:
    parsed_url = urlsplit(live_server.base_url)
    reader, writer = await asyncio.open_connection(parsed_url.hostname, parsed_url.port)
    try:
        yield reader, writer
    finally:
        writer.close()
        await writer.wait_closed()


async def _send_raw_request(live_server: LiveServer, request: bytes) -> bytes:
    async with _live_connection(live_server) as (reader, writer):
        writer.write(request)
        await writer.drain()
        return await asyncio.wait_for(reader.read(), timeout=5)


async def _send_partial_upload(
    live_server: LiveServer,
    request: bytes,
    body: bytes,
    rolled: threading.Event,
) -> bool:
    async with _live_connection(live_server) as (_reader, writer):
        writer.write(request)
        writer.write(f"{len(body):X}\r\n".encode("ascii"))
        writer.write(body)
        writer.write(b"\r\n")
        await writer.drain()
        return await asyncio.to_thread(rolled.wait, 5)


async def _hold_queue_slot(
    queue: WorkQueue,
    started: asyncio.Event,
    release: asyncio.Event,
) -> None:
    async with queue.slot():
        started.set()
        await release.wait()


async def _enter_slot(queue: WorkQueue) -> None:
    async with queue.slot():
        pass


async def _rejects_work(queue: WorkQueue) -> bool:
    try:
        await _enter_slot(queue)
    except ServerBusyError:
        return True
    return False


async def _stop_while_jobs_run(
    queues: tuple[WorkQueue, WorkQueue],
    started: list[asyncio.Event],
    stop: asyncio.Event,
    lifespan_task: asyncio.Task[None],
) -> tuple[bool, list[bool]]:
    await asyncio.gather(*(event.wait() for event in started))
    stop.set()
    await asyncio.sleep(0)
    stopped_early = lifespan_task.done()
    rejected = await asyncio.gather(*(_rejects_work(queue) for queue in queues))
    return stopped_early, list(rejected)


async def _observe_lifespan_shutdown(
    application: FastAPI,
) -> tuple[bool, list[bool]]:
    queues = (application.state.document_queue, application.state.transcription_queue)
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
        for queue, event in zip(queues, started, strict=True)
    ]
    try:
        observed = await _stop_while_jobs_run(queues, started, stop, lifespan_task)
    finally:
        release_jobs.set()
        stop.set()
        await asyncio.gather(*jobs, lifespan_task)
    return observed


def _patch_startup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(os, "umask", lambda _mask: 0o022)
    monkeypatch.setattr(
        main_module, "check_security_settings", lambda _configured: None
    )
    monkeypatch.setattr(main_module, "ensure_temp_dir", lambda: tmp_path)
    monkeypatch.setattr(main_module, "cleanup_stale_files", lambda: None)
    monkeypatch.setattr(
        model_module, "_build_model", lambda _configured_settings: silent_model()
    )


def _run_two_lifespans(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> dict[str, object]:
    first_settings = Settings(WHISPER_MODEL_SIZE="tiny")
    second_settings = Settings(WHISPER_MODEL_SIZE="base")
    received_settings: list[Settings] = []

    def build_model(configured_settings: Settings) -> object:
        received_settings.append(configured_settings)
        return silent_model()

    _patch_startup(monkeypatch, tmp_path)
    monkeypatch.setattr(model_module, "_build_model", build_model)

    applications = (
        main_module.create_app(first_settings),
        main_module.create_app(second_settings),
    )
    holders_before = [hasattr(app.state, "model_holder") for app in applications]
    holders: list[ModelHolder] = []
    loaded: list[bool] = []

    async def run_lifespans() -> list[bool]:
        for application in applications:
            async with main_module.lifespan(application):
                holders.append(application.state.model_holder)
                loaded.append(application.state.model_holder.is_loaded)
        queues = [
            queue
            for application in applications
            for queue in (
                application.state.transcription_queue,
                application.state.document_queue,
            )
        ]
        return list(await asyncio.gather(*(_rejects_work(queue) for queue in queues)))

    rejected_after = asyncio.run(run_lifespans())
    return {
        "holders_before": holders_before,
        "loaded": loaded,
        "rejected_after": rejected_after,
        "distinct": holders[0] is not holders[1],
        "kept": [
            application.state.model_holder is holder
            for application, holder in zip(applications, holders, strict=True)
        ],
        "received": received_settings == [first_settings, second_settings],
    }


def _record_startup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[list[tuple[str, object]], tuple[int, object], FastAPI]:
    events: list[tuple[str, object]] = []

    def record_temp_dir() -> Path:
        events.append(("temp", tmp_path))
        return tmp_path

    monkeypatch.setattr(os, "umask", lambda mask: events.append(("umask", mask)))
    monkeypatch.setattr(
        main_module,
        "check_security_settings",
        lambda configured: events.append(("security", configured)),
    )
    monkeypatch.setattr(main_module, "ensure_temp_dir", record_temp_dir)
    monkeypatch.setattr(
        main_module, "cleanup_stale_files", lambda: events.append(("cleanup", None))
    )
    monkeypatch.setattr(
        model_module, "_build_model", lambda _configured_settings: silent_model()
    )
    application = main_module.create_app()
    with TestClient(application) as client:
        response = client.get("/health")
    return events, (response.status_code, response.json()["loaded"]), application


def _fail_startup_on_temp_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[str, list[str]]:
    events: list[str] = []

    def fail_ensure_temp_dir() -> None:
        raise _TempDirectoryPermissionError

    def record_model(_configured_settings: Settings) -> object:
        events.append("model")
        return silent_model()

    monkeypatch.setattr(os, "umask", lambda _mask: 0o022)
    monkeypatch.setattr(
        main_module, "check_security_settings", lambda _configured: None
    )
    monkeypatch.setattr(main_module, "ensure_temp_dir", fail_ensure_temp_dir)
    monkeypatch.setattr(
        main_module, "cleanup_stale_files", lambda: events.append("cleanup")
    )
    monkeypatch.setattr(model_module, "_build_model", record_model)
    with (
        pytest.raises(PermissionError) as caught,
        TestClient(main_module.create_app()),
    ):
        pass
    return str(caught.value), events


def _queue_settings() -> Settings:
    return Settings(
        MAX_CONCURRENT_TRANSCRIPTIONS=3,
        MAX_WAITING_TRANSCRIPTIONS=2,
        MAX_WAITING_DOCUMENTS=1,
    )


@pytest.mark.parametrize("path", ["/docs", "/openapi.json", "/redoc"])
def test_hides_documentation_routes_by_default(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    monkeypatch.setattr(settings, "ENABLE_DOCS", False)
    client = TestClient(main_module.create_app())
    expected_status = 404
    assert client.get(path).status_code == expected_status, (
        f"{path} must not be served when documentation is disabled"
    )


def test_clears_documentation_urls_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ENABLE_DOCS", False)
    app = main_module.create_app()
    expected = (None, None, None)
    assert (app.docs_url, app.openapi_url, app.redoc_url) == expected, (
        "documentation URLs must be unset by default"
    )


def test_enables_documentation_for_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ENABLE_DOCS", True)
    app = main_module.create_app()
    actual = (
        app.docs_url,
        app.openapi_url,
        TestClient(app).get("/openapi.json").status_code,
    )
    expected = ("/docs", "/openapi.json", 200)
    assert actual == expected, "enabled documentation must be served"


def test_prefers_explicit_settings_over_process_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ENABLE_DOCS", False)
    app = main_module.create_app(Settings(ENABLE_DOCS=True))
    actual = (
        app.docs_url,
        app.openapi_url,
        TestClient(app).get("/openapi.json").status_code,
    )
    expected = ("/docs", "/openapi.json", 200)
    assert actual == expected, "explicit settings must win over process settings"


@pytest.mark.parametrize(
    ("endpoint", "key_choice"),
    [
        ("/process-document", "audio key"),
        ("/transcribe", "document key"),
        ("/process-document", "missing"),
        ("/transcribe", "missing"),
        ("/transcribe", "audio key without last character"),
        ("/process-document", "document key with suffix"),
        ("/transcribe", "audio key in upper case"),
    ],
)
@pytest.mark.asyncio
async def test_rejects_live_uploads_without_the_right_key(
    live_server: LiveServer,
    tmp_path: Path,
    endpoint: str,
    key_choice: str,
) -> None:
    status = await _live_upload_status(
        f"{live_server.base_url}{endpoint}",
        _upload_path(tmp_path, endpoint),
        _pick_key(live_server, key_choice),
    )
    expected_status = 401
    assert status == expected_status, f"{endpoint} accepted the {key_choice}"


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
@pytest.mark.parametrize(
    ("endpoint", "key"),
    [
        ("/transcribe", "rotated-whisper-key"),
        ("/transcribe", "test-whisper-key"),
        ("/process-document", "rotated-document-key"),
        ("/process-document", "test-document-key"),
    ],
)
@pytest.mark.asyncio
async def test_accepts_every_key_during_rotation(
    live_server: LiveServer,
    tmp_path: Path,
    endpoint: str,
    key: str,
) -> None:
    status = await _live_upload_status(
        f"{live_server.base_url}{endpoint}", _upload_path(tmp_path, endpoint), key
    )
    expected_status = 200
    assert status == expected_status, f"{endpoint} rejected rotated key {key}"


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
@pytest.mark.parametrize("endpoint", ["/process-document", "/transcribe"])
@pytest.mark.asyncio
async def test_accepts_uploads_without_keys_when_unauthenticated_is_allowed(
    live_server: LiveServer,
    tmp_path: Path,
    endpoint: str,
) -> None:
    status = await _live_upload_status(
        f"{live_server.base_url}{endpoint}", _upload_path(tmp_path, endpoint), None
    )
    expected_status = 200
    assert status == expected_status, f"{endpoint} rejected an unauthenticated upload"


@pytest.mark.asyncio
async def test_echoes_valid_request_id_on_live_health(
    live_server: LiveServer,
) -> None:
    request_id = "socket-request-0001"
    status, headers, body = await _get_live(
        f"{live_server.base_url}/health", {"X-Request-ID": request_id}
    )
    actual = (status, headers.get("x-request-id"), body.get("status"))
    expected = (200, request_id, "ok")
    assert actual == expected, "health must answer and echo the request ID"


@pytest.mark.parametrize(
    "supplied_id",
    [None, "short", "bad id with spaces!", "z" * 65, "../../etc/passwd"],
)
@pytest.mark.asyncio
async def test_generates_request_id_when_live_client_sends_none_or_invalid(
    live_server: LiveServer,
    supplied_id: str | None,
) -> None:
    headers = None if supplied_id is None else {"X-Request-ID": supplied_id}
    _status, response_headers, _body = await _get_live(
        f"{live_server.base_url}/health", headers
    )
    generated_id = response_headers.get("x-request-id", "")
    assert re.fullmatch(r"[0-9a-f]{32}", generated_id), (
        f"{supplied_id!r} produced request ID {generated_id!r}"
    )


@pytest.mark.asyncio
async def test_reports_missing_native_tools_on_live_ready(
    live_server: LiveServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ready_module, "check_native_tools", no_native_tools)
    status, _headers, body = await _get_live(f"{live_server.base_url}/ready")
    actual = (status, body.get("tesseract"), body.get("djvulibre"))
    expected = (200, False, False)
    assert actual == expected, "ready must report that native tools are missing"


@pytest.mark.parametrize("path", ["/docs", "/openapi.json"])
@pytest.mark.asyncio
async def test_hides_live_documentation_by_default(
    live_server: LiveServer, path: str
) -> None:
    status, _headers, _body = await _get_live(f"{live_server.base_url}{path}")
    expected_status = 404
    assert status == expected_status, f"{path} must be hidden on a live server"


@pytest.mark.parametrize(
    "live_server",
    [LiveServerOptions(enable_docs=True)],
    indirect=True,
)
@pytest.mark.parametrize("path", ["/docs", "/openapi.json"])
@pytest.mark.asyncio
async def test_serves_live_documentation_when_enabled(
    live_server: LiveServer, path: str
) -> None:
    async with (
        aiohttp.ClientSession() as session,
        session.get(f"{live_server.base_url}{path}") as response,
    ):
        status = response.status
    expected_status = 200
    assert status == expected_status, f"{path} must be served when enabled"


@pytest.mark.parametrize(
    "live_server",
    [LiveServerOptions(max_body_size=64)],
    indirect=True,
)
@pytest.mark.parametrize("declared_length", ["65", "9223372036854775807"])
@pytest.mark.asyncio
async def test_rejects_declared_live_body_over_limit(
    live_server: LiveServer, declared_length: str
) -> None:
    request_id = "declared-limit-0001"
    error_message = b"Request body too large"
    request = (
        "POST /process-document HTTP/1.1\r\n"
        "Host: 127.0.0.1\r\n"
        f"Authorization: Bearer {live_server.document_api_key}\r\n"
        "Content-Type: application/octet-stream\r\n"
        f"Content-Length: {declared_length}\r\n"
        f"X-Request-ID: {request_id}\r\n"
        "Connection: close\r\n"
        "\r\n"
    )
    response = await _send_raw_request(live_server, request.encode("ascii"))
    actual = (
        response.split(b"\r\n", maxsplit=1)[0].split(b" ")[1],
        f"x-request-id: {request_id}".encode() in response.lower(),
        error_message in response,
    )
    expected = (b"413", True, True)
    assert actual == expected, "an oversized declared body must get a tagged 413"


@pytest.mark.parametrize(
    "live_server",
    [LiveServerOptions(max_body_size=64)],
    indirect=True,
)
@pytest.mark.asyncio
async def test_rejects_chunked_live_body_over_limit(
    live_server: LiveServer,
) -> None:
    form = aiohttp.FormData()
    form.add_field("file", b"q" * 65, filename="note.txt", content_type="text/plain")
    headers = {"Authorization": f"Bearer {live_server.document_api_key}"}
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            f"{live_server.base_url}/process-document",
            data=form,
            chunked=True,
            headers=headers,
        ) as response,
    ):
        actual = (response.status, await response.json())
    expected = (413, {"detail": "Request body too large"})
    assert actual == expected, "an oversized chunked body must be rejected"


@pytest.mark.asyncio
async def test_closes_temporary_file_when_live_client_disconnects(
    live_server: LiveServer,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    rolled = threading.Event()
    closed = threading.Event()

    def track_spooled_file(**_kwargs: object) -> TrackedSpooledTemporaryFile:
        return TrackedSpooledTemporaryFile(tmp_path, rolled, closed)

    monkeypatch.setattr(
        starlette.formparsers, "SpooledTemporaryFile", track_spooled_file
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
        "Host: 127.0.0.1\r\n"
        f"Authorization: Bearer {live_server.whisper_api_key}\r\n"
        f"Content-Type: multipart/form-data; boundary={boundary}\r\n"
        "Transfer-Encoding: chunked\r\n"
        "\r\n"
    )
    rolled_in_time = await _send_partial_upload(
        live_server, request.encode("ascii"), multipart_body, rolled
    )
    actual = (
        rolled_in_time,
        await asyncio.to_thread(closed.wait, 5),
        list(live_server.temp_dir.iterdir()),
    )
    expected: tuple[bool, bool, list[Path]] = (True, True, [])
    assert actual == expected, "an abandoned upload must leave no temporary file"


def test_reports_model_state_on_health_without_lifespan() -> None:
    application = main_module.create_app(
        Settings(WHISPER_MODEL_SIZE="small-test", WHISPER_MODEL_PATH="")
    )
    application.state.model_holder = ModelHolder(application.state.settings)
    response = TestClient(application).get("/health")
    actual = (response.status_code, response.json())
    expected = (200, {"status": "ok", "model": "small-test", "loaded": False})
    assert actual == expected, "health must report the configured unloaded model"


def test_reports_local_model_directory_name_on_health() -> None:
    application = main_module.create_app(
        Settings(WHISPER_MODEL_PATH="/srv/audiodoc/models/custom-whisper")
    )
    application.state.model_holder = ModelHolder(application.state.settings)
    response = TestClient(application).get("/health")
    actual = (response.status_code, response.json()["model"])
    expected = (200, "custom-whisper")
    assert actual == expected, "health must name the local model directory"


@pytest.mark.parametrize(
    ("holder_state", "path", "field", "expected"),
    [
        ("loaded", "/health", "loaded", (200, True)),
        ("loaded", "/ready", "model_loaded", (200, True)),
        ("empty", "/health", "loaded", (200, False)),
        ("empty", "/ready", "model_loaded", (200, False)),
    ],
)
def test_reports_model_state_of_application_holder(
    monkeypatch: pytest.MonkeyPatch,
    holder_state: str,
    path: str,
    field: str,
    expected: tuple[int, bool],
) -> None:
    monkeypatch.setattr(ready_module, "check_native_tools", no_native_tools)
    application = main_module.create_app()
    holders = {"loaded": lambda: loaded_model_holder(object()), "empty": ModelHolder}
    application.state.model_holder = holders[holder_state]()
    response = TestClient(application).get(path)
    actual = (response.status_code, response.json()[field])
    assert actual == expected, f"{path} must report the application model state"


def test_registers_expected_routes() -> None:
    app = main_module.create_app()
    paths = app.openapi()["paths"]
    actual = (
        app.title,
        {path: sorted(paths[path]) for path in sorted(paths)},
    )
    expected: tuple[str, dict[str, list[str]]] = (
        "audiodoc",
        {
            "/health": ["get"],
            "/process-document": ["post"],
            "/ready": ["get"],
            "/transcribe": ["post"],
        },
    )
    assert actual == expected, "the application must expose exactly its API routes"


def test_builds_independent_queues_for_each_application() -> None:
    configured_settings = _queue_settings()
    first_app = main_module.create_app(configured_settings)
    second_app = main_module.create_app(configured_settings)
    actual = (
        first_app.state.transcription_queue is second_app.state.transcription_queue,
        first_app.state.document_queue is second_app.state.document_queue,
    )
    expected = (False, False)
    assert actual == expected, "every application must own its queues"


def test_sizes_transcription_queue_from_settings() -> None:
    app = main_module.create_app(_queue_settings())
    actual = measure_capacity(app.state.transcription_queue)
    expected = QueueCapacity(active=3, waiting=2)
    assert actual == expected, "the transcription queue ignored its settings"


def test_sizes_document_queue_from_settings() -> None:
    app = main_module.create_app(_queue_settings())
    actual = measure_capacity(app.state.document_queue)
    expected = QueueCapacity(active=MAX_CONCURRENT_DOCUMENTS, waiting=1)
    assert actual == expected, "the document queue ignored its settings"


@pytest.mark.parametrize(
    ("observation", "expected"),
    [
        ("holders_before", [False, False]),
        ("loaded", [True, True]),
        ("rejected_after", [True, True, True, True]),
        ("distinct", True),
        ("kept", [True, True]),
        ("received", True),
    ],
)
def test_gives_each_lifespan_its_own_model_holder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    observation: str,
    expected: object,
) -> None:
    observations = _run_two_lifespans(monkeypatch, tmp_path)
    assert observations[observation] == expected, (
        f"lifespan observation {observation} is wrong"
    )


def test_prepares_storage_in_order_during_startup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events, _health, application = _record_startup(monkeypatch, tmp_path)
    expected = [
        ("umask", 0o077),
        ("security", application.state.settings),
        ("temp", tmp_path),
        ("cleanup", None),
    ]
    assert events == expected, "startup must restrict umask before touching storage"


def test_loads_model_during_startup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _events, health, _application = _record_startup(monkeypatch, tmp_path)
    expected = (200, True)
    assert health == expected, "health must report the model loaded after startup"


@pytest.mark.parametrize(
    ("audio_keys", "document_keys", "expected_secrets"),
    [
        ("audio-secret", "document-secret", ("audio-secret", "document-secret")),
        (
            " new-audio-7Q , old-audio-2x,,",
            "doc-ключ-ß",
            ("new-audio-7Q", "old-audio-2x", "doc-ключ-ß"),
        ),
    ],
)
def test_redacts_every_configured_api_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    audio_keys: str,
    document_keys: str,
    expected_secrets: tuple[str, ...],
) -> None:
    configured_settings = load_settings(
        {"AUDIODOC_AUDIO_KEY": audio_keys, "AUDIODOC_DOCUMENT_KEY": document_keys}
    )
    application = main_module.create_app(configured_settings)
    logging_calls: list[tuple[str, tuple[str, ...]]] = []

    def capture_logging(level: str, secrets: Iterable[str]) -> None:
        logging_calls.append((level, tuple(secrets)))

    monkeypatch.setattr(main_module, "configure_logging", capture_logging)
    monkeypatch.setattr(os, "umask", lambda _mask: 0o077)
    monkeypatch.setattr(main_module, "ensure_temp_dir", lambda: tmp_path)
    monkeypatch.setattr(main_module, "cleanup_stale_files", lambda: None)
    monkeypatch.setattr(
        model_module, "_build_model", lambda _configured_settings: silent_model()
    )
    with TestClient(application):
        pass
    expected = [("INFO", expected_secrets)]
    assert logging_calls == expected, "every configured key must be redacted"


@pytest.mark.parametrize(
    ("whisper_key", "document_key", "expected_message"),
    [
        ("", "document-test-key", "AUDIODOC_AUDIO_KEY"),
        (" , ,", "doc-key-7", "AUDIODOC_AUDIO_KEY"),
        ("audio-k1", "   ", "AUDIODOC_DOCUMENT_KEY"),
        ("shared-test-key", "shared-test-key", "must not share any key values"),
        (
            "old-audio, overlap-key",
            " overlap-key ,new-doc",
            "must not share any key values",
        ),
    ],
)
def test_refuses_to_start_with_invalid_api_keys(
    monkeypatch: pytest.MonkeyPatch,
    whisper_key: str,
    document_key: str,
    expected_message: str,
) -> None:
    monkeypatch.setattr(os, "umask", lambda _mask: 0o022)
    monkeypatch.setattr(settings, "AUDIODOC_AUDIO_KEY", whisper_key)
    monkeypatch.setattr(settings, "AUDIODOC_DOCUMENT_KEY", document_key)
    monkeypatch.setattr(settings, "ALLOW_UNAUTHENTICATED", False)
    with (
        pytest.raises(RuntimeError) as caught,
        TestClient(main_module.create_app()),
    ):
        pass
    assert expected_message in str(caught.value), (
        f"startup error {caught.value} does not mention {expected_message}"
    )


def test_fails_startup_when_temp_directory_is_not_writable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message, _events = _fail_startup_on_temp_dir(monkeypatch)
    expected_message = "Temporary directory is not writable"
    assert message == expected_message, "startup must surface the storage error"


def test_skips_cleanup_and_model_when_temp_directory_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _message, events = _fail_startup_on_temp_dir(monkeypatch)
    expected_empty: list[str] = []
    assert events == expected_empty, "startup must stop before cleanup and model load"


def test_waits_for_running_jobs_before_shutdown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_startup(monkeypatch, tmp_path)
    stopped_early, _rejected = asyncio.run(
        _observe_lifespan_shutdown(main_module.create_app())
    )
    assert stopped_early is False, "shutdown must wait for running jobs"


def test_rejects_new_work_during_shutdown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_startup(monkeypatch, tmp_path)
    _stopped_early, rejected = asyncio.run(
        _observe_lifespan_shutdown(main_module.create_app())
    )
    expected = [True, True]
    assert rejected == expected, "both queues must refuse work during shutdown"


def test_imports_main_without_side_effects(
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
    process = context.Process(target=check_import_safety, args=(str(tmp_path),))
    process.start()
    process.join(timeout=30)
    if process.is_alive():
        process.terminate()
        process.join()
    expected_exit_code = 0
    assert process.exitcode == expected_exit_code, (
        "importing audiodoc.main had side effects or timed out"
    )
