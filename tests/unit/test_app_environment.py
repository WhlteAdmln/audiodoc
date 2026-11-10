# Copyright (c) 2026 Nikolai Zelensky
"""Tests for application environment bootstrap order."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI

import app as app_module


def test_app_imports_main_without_loading_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure the compatibility entry point leaves environment loading to the CLI."""
    events: list[str] = []
    application = FastAPI()

    def create_app() -> FastAPI:
        events.append("create_app")
        return application

    main_module = SimpleNamespace(create_app=create_app)

    def import_module(name: str) -> SimpleNamespace:
        assert name == "audiodoc.main"
        events.append("import_main")
        return main_module

    monkeypatch.setattr(app_module, "import_module", import_module)

    assert app_module._create_compatibility_app() is application
    assert events == ["import_main", "create_app"]
