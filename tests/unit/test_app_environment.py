# Copyright (c) 2026 Nikolai Zelensky
"""Tests for application environment bootstrap order."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI

import app as app_module


def test_app_loads_environment_before_importing_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure dotenv loading precedes importing the application factory."""
    events: list[str] = []
    application = FastAPI()

    def load_env_file() -> None:
        events.append("load_env_file")

    def create_app() -> FastAPI:
        events.append("create_app")
        return application

    main_module = SimpleNamespace(create_app=create_app)

    def import_module(name: str) -> SimpleNamespace:
        assert name == "backend.main"
        events.append("import_main")
        return main_module

    monkeypatch.setattr(app_module, "load_env_file", load_env_file)
    monkeypatch.setattr(app_module, "import_module", import_module)

    assert app_module._create_compatibility_app() is application
    assert events == ["load_env_file", "import_main", "create_app"]
