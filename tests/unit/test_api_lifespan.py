# Copyright (c) 2026 Nikolai Zelensky
"""Tests for app factory wiring and lifecycle; no real model is loaded."""

import pytest

pytest.importorskip("ebooklib")
pytest.importorskip("striprtf")

from fastapi.testclient import TestClient

import backend.main as main_module
import backend.transcription.model as model_module
from backend.config import settings
from backend.main import app
from backend.transcription.model import model_holder


class FakeModel:
    def transcribe(self, *_args, **_kwargs):
        return iter([]), None


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
