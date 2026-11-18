# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the deprecated `app:app` entry point bootstrap order."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI

import app as app_module


def test_app_loads_environment_before_creating_application(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure legacy `uvicorn app:app` units still read the `.env` file first."""
    events: list[str] = []
    application = FastAPI()

    def load_env_file() -> None:
        events.append("load_env_file")

    def create_app() -> FastAPI:
        events.append("create_app")
        return application

    modules = {
        "audiodoc.env_readers": SimpleNamespace(load_env_file=load_env_file),
        "audiodoc.main": SimpleNamespace(create_app=create_app),
    }

    def import_module(name: str) -> SimpleNamespace:
        events.append(f"import:{name}")
        return modules[name]

    monkeypatch.setattr(app_module, "import_module", import_module)

    assert app_module._create_compatibility_app() is application
    assert events == [
        "import:audiodoc.env_readers",
        "load_env_file",
        "import:audiodoc.main",
        "create_app",
    ]
