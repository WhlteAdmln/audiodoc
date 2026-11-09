# Copyright (c) 2026 Nikolai Zelensky
"""Tests for app factory wiring and lifecycle; no real model is loaded."""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import backend.main as main_module
import backend.transcription.model as model_module
from app import app
from backend.api import ready as ready_module
from backend.config import Settings, settings
from backend.errors.base import ServerBusyError
from backend.transcription.model import model_holder


class FakeModel:
    def transcribe(self, *_args, **_kwargs):
        return iter([]), None


class _TempDirectoryPermissionError(PermissionError):
    """Raised when temporary storage cannot be prepared."""

    def __init__(self) -> None:
        """Initialize the temporary storage error."""
        super().__init__("Temporary directory is not writable")


def test_health_route_reports_model_state_without_starting_lifespan(monkeypatch):
    application = main_module.create_app(
        Settings(WHISPER_MODEL_SIZE="small-test", WHISPER_MODEL_PATH="")
    )
    monkeypatch.setattr(application.state.model_holder, "_model", None)

    response = TestClient(application).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "model": "small-test",
        "loaded": False,
    }


def test_health_route_reports_local_model_directory_name(monkeypatch):
    application = main_module.create_app(
        Settings(WHISPER_MODEL_PATH="/srv/audiodoc/models/custom-whisper")
    )
    monkeypatch.setattr(application.state.model_holder, "_model", None)

    response = TestClient(application).get("/health")

    assert response.status_code == 200
    assert response.json()["model"] == "custom-whisper"


def test_health_and_ready_use_application_model_holder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(model_holder, "_model", None)

    loaded_application = main_module.create_app()
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
    monkeypatch.setattr(model_holder, "_model", object())
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


def test_create_app_does_not_mutate_global_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    monkeypatch.setattr(
        main_module.document_queue,
        "set_max_waiting",
        calls.append,
    )

    main_module.create_app(Settings(MAX_WAITING_DOCUMENTS=2))

    assert calls == []


def test_create_app_creates_independent_model_holders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_settings = Settings(WHISPER_MODEL_SIZE="tiny")
    second_settings = Settings(WHISPER_MODEL_SIZE="base")
    received_settings: list[Settings] = []

    def build_model(configured_settings: Settings) -> FakeModel:
        received_settings.append(configured_settings)
        return FakeModel()

    monkeypatch.setattr(model_module, "_build_model", build_model)

    first_app = main_module.create_app(first_settings)
    second_app = main_module.create_app(second_settings)

    assert first_app.state.model_holder is not second_app.state.model_holder
    assert first_app.state.model_holder is not model_holder
    assert first_app.state.model_holder.is_loaded is False
    assert second_app.state.model_holder.is_loaded is False

    first_app.state.model_holder.load()
    second_app.state.model_holder.load()

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
    monkeypatch.setattr(settings, "WHISPER_API_KEY", whisper_key)
    monkeypatch.setattr(settings, "DOCUMENT_API_KEY", document_key)
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

    async def run_lifecycle() -> None:
        application = main_module.create_app()
        job_started = asyncio.Event()
        release_job = asyncio.Event()
        context = main_module.lifespan(application)
        await context.__aenter__()

        async def running_job() -> None:
            async with main_module.document_queue.slot():
                job_started.set()
                await release_job.wait()

        job = asyncio.create_task(running_job())
        shutdown: asyncio.Task[None] | None = None

        try:
            await job_started.wait()

            async def stop_lifespan() -> None:
                await context.__aexit__(None, None, None)

            shutdown = asyncio.create_task(stop_lifespan())
            await asyncio.sleep(0)

            assert not shutdown.done()

            with pytest.raises(ServerBusyError):
                async with main_module.document_queue.slot():
                    pytest.fail("Queue accepted a job during shutdown")

            release_job.set()
            await job
            await shutdown
        finally:
            release_job.set()
            await job
            if shutdown is None:
                await context.__aexit__(None, None, None)
            else:
                await shutdown

    asyncio.run(run_lifecycle())
