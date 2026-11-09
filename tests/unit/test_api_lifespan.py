# Copyright (c) 2026 Nikolai Zelensky
"""Tests for app factory wiring and lifecycle; no real model is loaded."""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import backend.main as main_module
import backend.transcription.model as model_module
from backend.config import settings
from backend.errors.base import ServerBusyError
from backend.main import app
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
    monkeypatch.setattr(settings, "WHISPER_MODEL_SIZE", "small-test")
    monkeypatch.setattr(settings, "WHISPER_MODEL_PATH", "")
    monkeypatch.setattr(model_holder, "_model", None)

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "model": "small-test",
        "loaded": False,
    }


def test_health_route_reports_local_model_directory_name(monkeypatch):
    monkeypatch.setattr(
        settings, "WHISPER_MODEL_PATH", "/srv/audiodoc/models/custom-whisper"
    )
    monkeypatch.setattr(model_holder, "_model", None)

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["model"] == "custom-whisper"


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
    monkeypatch.setattr(model_module, "_build_model", FakeModel)
    monkeypatch.setattr(model_holder, "_model", None)

    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["loaded"] is True

    assert events == [
        ("umask", 0o077),
        ("security", settings),
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
        lambda: events.append("model") or FakeModel(),
    )
    monkeypatch.setattr(model_holder, "_model", None)

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
    monkeypatch.setattr(model_module, "_build_model", FakeModel)
    monkeypatch.setattr(model_holder, "_model", None)

    async def run_lifecycle() -> None:
        job_started = asyncio.Event()
        release_job = asyncio.Event()
        context = main_module.lifespan(main_module.create_app())
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
