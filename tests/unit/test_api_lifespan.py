# Copyright (c) 2026 Nikolai Zelensky
"""Tests for app factory wiring and lifecycle; no real model is loaded."""

import asyncio
from collections.abc import Iterable
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.main as main_module
import backend.transcription.model as model_module
from app import app
from backend.api import ready as ready_module
from backend.common.work_queue import WorkQueue
from backend.config import Settings, load_settings, settings
from backend.document_engine.limits import MAX_CONCURRENT_DOCUMENTS
from backend.errors.base import ServerBusyError
from backend.transcription.model import ModelHolder


class FakeModel:
    def transcribe(self, *_args, **_kwargs):
        return iter([]), None


class _TempDirectoryPermissionError(PermissionError):
    """Raised when temporary storage cannot be prepared."""

    def __init__(self) -> None:
        """Initialize the temporary storage error."""
        super().__init__("Temporary directory is not writable")


def test_health_route_reports_model_state_without_starting_lifespan():
    application = main_module.create_app(
        Settings(WHISPER_MODEL_SIZE="small-test", WHISPER_MODEL_PATH="")
    )
    application.state.model_holder = ModelHolder(application.state.settings)

    response = TestClient(application).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "model": "small-test",
        "loaded": False,
    }


def test_health_route_reports_local_model_directory_name():
    application = main_module.create_app(
        Settings(WHISPER_MODEL_PATH="/srv/audiodoc/models/custom-whisper")
    )
    application.state.model_holder = ModelHolder(application.state.settings)

    response = TestClient(application).get("/health")

    assert response.status_code == 200
    assert response.json()["model"] == "custom-whisper"


def test_health_and_ready_use_application_model_holder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded_application = main_module.create_app()
    loaded_application.state.model_holder = ModelHolder(
        loaded_application.state.settings
    )
    monkeypatch.setattr(loaded_application.state.model_holder, "_model", object())

    monkeypatch.setattr(
        ready_module,
        "_available_tesseract_languages",
        lambda: (False, []),
    )
    monkeypatch.setattr(ready_module.shutil, "which", lambda _name: None)

    client = TestClient(loaded_application)

    health_response = client.get("/health")
    ready_response = client.get("/ready")

    assert health_response.status_code == 200
    assert health_response.json()["loaded"] is True
    assert ready_response.status_code == 200
    assert ready_response.json()["model_loaded"] is True

    unloaded_application = main_module.create_app()
    unloaded_application.state.model_holder = ModelHolder(
        unloaded_application.state.settings
    )
    monkeypatch.setattr(unloaded_application.state.model_holder, "_model", None)

    other_client = TestClient(unloaded_application)

    assert other_client.get("/health").json()["loaded"] is False
    assert other_client.get("/ready").json()["model_loaded"] is False


def test_app_registers_all_expected_routes():
    assert app.title == "audiodoc"
    # FastAPI/Starlette may expose included routers as internal wrapper
    # objects in app.routes. OpenAPI is the public, version-stable view of
    # the routes registered on the application.
    paths = app.openapi()["paths"]

    assert "get" in paths["/health"]
    assert "get" in paths["/ready"]
    assert "post" in paths["/transcribe"]
    assert "post" in paths["/process-document"]


def test_create_app_builds_independent_queues_from_settings() -> None:
    configured_settings = Settings(
        MAX_CONCURRENT_TRANSCRIPTIONS=3,
        MAX_WAITING_TRANSCRIPTIONS=2,
        MAX_WAITING_DOCUMENTS=1,
    )
    first_app = main_module.create_app(configured_settings)
    second_app = main_module.create_app(configured_settings)

    assert (
        first_app.state.transcription_queue is not second_app.state.transcription_queue
    )
    assert first_app.state.document_queue is not second_app.state.document_queue
    assert first_app.state.transcription_queue._workers == 3
    assert first_app.state.transcription_queue._max_waiting == 2
    assert first_app.state.document_queue._workers == MAX_CONCURRENT_DOCUMENTS
    assert first_app.state.document_queue._max_waiting == 1


def test_lifespan_creates_independent_model_holders(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    first_settings = Settings(WHISPER_MODEL_SIZE="tiny")
    second_settings = Settings(WHISPER_MODEL_SIZE="base")
    received_settings: list[Settings] = []
    holders: list[ModelHolder] = []

    def build_model(configured_settings: Settings) -> FakeModel:
        received_settings.append(configured_settings)
        return FakeModel()

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

    first_holder, second_holder = holders
    assert first_holder is not second_holder
    assert first_app.state.model_holder is first_holder
    assert second_app.state.model_holder is second_holder
    assert received_settings == [first_settings, second_settings]


def test_lifespan_checks_configuration_prepares_storage_and_loads_model(
    monkeypatch, tmp_path
):
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
        lambda _configured_settings: FakeModel(),
    )

    with TestClient(application) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["loaded"] is True

    assert events == [
        ("umask", 0o077),
        ("security", application.state.settings),
        ("temp", tmp_path),
        ("cleanup", None),
    ]


def test_lifespan_logs_one_legacy_key_warning_and_redacts_new_secrets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    configured_settings = load_settings(
        {
            "WHISPER_API_KEY": "legacy-audio",
            "DOCUMENT_API_KEY": "legacy-document",
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
        lambda _configured_settings: FakeModel(),
    )

    with caplog.at_level("WARNING"), TestClient(application):
        pass

    warning_lines = [
        record.getMessage()
        for record in caplog.records
        if "Deprecated API key environment variables" in record.getMessage()
    ]
    assert len(warning_lines) == 1
    assert "WHISPER_API_KEY" in warning_lines[0]
    assert "DOCUMENT_API_KEY" in warning_lines[0]
    assert logging_calls == [
        ("INFO", ("legacy-audio", "legacy-document")),
    ]


@pytest.mark.parametrize(
    ("whisper_key", "document_key", "expected_message"),
    [
        ("", "document-test-key", "WHISPER_API_KEY"),
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
        lambda _configured_settings: events.append("model") or FakeModel(),
    )

    with (
        pytest.raises(
            PermissionError,
            match="Temporary directory is not writable",
        ),
        TestClient(main_module.create_app()),
    ):
        pass

    assert events == []


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
        lambda _configured_settings: FakeModel(),
    )

    application = main_module.create_app()
    asyncio.run(_run_lifespan_shutdown(application))


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


async def _run_lifespan_shutdown(application: FastAPI) -> None:
    document_queue = application.state.document_queue
    transcription_queue = application.state.transcription_queue
    document_job_started = asyncio.Event()
    transcription_job_started = asyncio.Event()
    release_jobs = asyncio.Event()
    context = main_module.lifespan(application)
    await context.__aenter__()

    document_job = asyncio.create_task(
        _hold_queue_slot(document_queue, document_job_started, release_jobs)
    )
    transcription_job = asyncio.create_task(
        _hold_queue_slot(
            transcription_queue,
            transcription_job_started,
            release_jobs,
        )
    )
    shutdown: asyncio.Task[None] | None = None

    try:
        await asyncio.gather(
            document_job_started.wait(),
            transcription_job_started.wait(),
        )

        async def stop_lifespan() -> None:
            await context.__aexit__(None, None, None)

        shutdown = asyncio.create_task(stop_lifespan())
        await asyncio.sleep(0)

        assert not shutdown.done()
        await asyncio.gather(
            _assert_queue_rejects_work(document_queue),
            _assert_queue_rejects_work(transcription_queue),
        )

        release_jobs.set()
        await asyncio.gather(document_job, transcription_job)
        await shutdown
    finally:
        release_jobs.set()
        await asyncio.gather(document_job, transcription_job)
        if shutdown is None:
            await context.__aexit__(None, None, None)
        else:
            await shutdown
