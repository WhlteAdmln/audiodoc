# Copyright (c) 2026 Nikolai Zelensky
import sys
from collections.abc import Callable
from types import ModuleType

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from audiodoc.api import ready as ready_module
from audiodoc.config import settings
from audiodoc.transcription.model import ModelHolder


class _FakeTesseractError(RuntimeError):
    pass


class _UnexpectedTesseractError(Exception):
    pass


def _install_fake_pytesseract(
    monkeypatch: pytest.MonkeyPatch,
    get_languages: Callable[..., list[str]],
) -> None:
    module = ModuleType("pytesseract")
    module.__dict__.update(
        {
            "TesseractError": _FakeTesseractError,
            "get_languages": get_languages,
        }
    )
    monkeypatch.setitem(sys.modules, "pytesseract", module)
    monkeypatch.setattr(
        ready_module.shutil,
        "which",
        lambda _name: "/usr/bin/tesseract",
    )


@pytest.mark.parametrize("error_type", [OSError, _FakeTesseractError])
def test_available_tesseract_languages_handles_expected_errors(
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[Exception],
) -> None:
    def fail_get_languages(*, config: str) -> list[str]:
        raise error_type()

    _install_fake_pytesseract(monkeypatch, fail_get_languages)

    assert ready_module._available_tesseract_languages() == (True, [])


def test_available_tesseract_languages_handles_missing_pytesseract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "pytesseract", None)
    monkeypatch.setattr(
        ready_module.shutil,
        "which",
        lambda _name: "/usr/bin/tesseract",
    )

    assert ready_module._available_tesseract_languages() == (True, [])


def test_available_tesseract_languages_propagates_unexpected_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_get_languages(*, config: str) -> list[str]:
        raise _UnexpectedTesseractError

    _install_fake_pytesseract(monkeypatch, fail_get_languages)

    with pytest.raises(_UnexpectedTesseractError):
        ready_module._available_tesseract_languages()


def create_ready_app():
    app = FastAPI()
    app.state.model_holder = ModelHolder()
    app.include_router(ready_module.router)
    return app


def test_ready_is_public_and_reports_native_dependencies(monkeypatch):
    monkeypatch.setattr(settings, "DOCUMENT_API_KEY", "document-ready-test-key")
    monkeypatch.setattr(
        ready_module,
        "_available_tesseract_languages",
        lambda: (True, ["eng", "rus"]),
    )
    monkeypatch.setattr(
        ready_module.shutil,
        "which",
        lambda name: f"/usr/bin/{name}",
    )
    application = create_ready_app()
    monkeypatch.setattr(application.state.model_holder, "_model", object())
    client = TestClient(application)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "tesseract": True,
        "languages": ["eng", "rus"],
        "djvulibre": True,
        "model_loaded": True,
    }


def test_ready_reports_missing_programs_without_raising(monkeypatch):
    monkeypatch.setattr(settings, "DOCUMENT_API_KEY", "document-ready-test-key")
    monkeypatch.setattr(
        ready_module,
        "_available_tesseract_languages",
        lambda: (False, []),
    )
    monkeypatch.setattr(
        ready_module.shutil,
        "which",
        {"djvused": "/usr/bin/djvused"}.get,
    )
    application = create_ready_app()
    monkeypatch.setattr(application.state.model_holder, "_model", None)

    response = TestClient(application).get(
        "/ready",
        headers={"Authorization": "Bearer document-ready-test-key"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "tesseract": False,
        "languages": [],
        "djvulibre": False,
        "model_loaded": False,
    }


@pytest.mark.parametrize(
    "missing_tool",
    ["tesseract", "djvutxt", "djvused", "ddjvu"],
)
def test_ready_reports_each_missing_native_tool(
    monkeypatch: pytest.MonkeyPatch,
    missing_tool: str,
) -> None:
    _install_fake_pytesseract(monkeypatch, lambda **_kwargs: ["eng"])

    def fake_which(name: str) -> str | None:
        return None if name == missing_tool else f"/usr/bin/{name}"

    monkeypatch.setattr(ready_module.shutil, "which", fake_which)
    application = create_ready_app()
    monkeypatch.setattr(application.state.model_holder, "_model", None)

    response = TestClient(application).get("/ready")

    tesseract_available = missing_tool != "tesseract"
    djvulibre_available = missing_tool not in {
        "djvutxt",
        "djvused",
        "ddjvu",
    }

    assert response.status_code == 200
    assert response.json() == {
        "tesseract": tesseract_available,
        "languages": ["eng"] if tesseract_available else [],
        "djvulibre": djvulibre_available,
        "model_loaded": False,
    }
