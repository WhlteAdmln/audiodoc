# Copyright (c) 2026 Nikolai Zelensky
import sys
from collections.abc import Callable
from types import ModuleType

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from audiodoc.api import ready as ready_module
from audiodoc.config import settings
from audiodoc.document_engine import diagnostics as diagnostics_module
from audiodoc.document_engine.extractors.djvu.tools import DjvuTools
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


def _set_native_tool_lookup(
    monkeypatch: pytest.MonkeyPatch,
    missing: str | None = None,
) -> None:
    """Control native executable discovery in diagnostics tests."""
    monkeypatch.setattr(
        diagnostics_module.shutil,
        "which",
        lambda name: None if name == missing else f"/usr/bin/{name}",
    )


@pytest.mark.parametrize("error_type", [OSError, _FakeTesseractError])
def test_check_native_tools_handles_tesseract_language_errors(
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[Exception],
) -> None:
    def fail_get_languages(*, config: str) -> list[str]:
        raise error_type()

    _install_fake_pytesseract(monkeypatch, fail_get_languages)
    _set_native_tool_lookup(monkeypatch)

    status = diagnostics_module.check_native_tools()

    assert status.tesseract == "/usr/bin/tesseract"
    assert status.languages == ()
    assert status.djvulibre


def test_check_native_tools_reports_available_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_pytesseract(
        monkeypatch,
        lambda **_kwargs: ["rus", "eng", "eng"],
    )
    _set_native_tool_lookup(monkeypatch)

    status = diagnostics_module.check_native_tools()

    assert status.tesseract == "/usr/bin/tesseract"
    assert status.languages == ("eng", "rus")
    assert status.djvu_tools == DjvuTools(
        "/usr/bin/djvutxt",
        "/usr/bin/djvused",
        "/usr/bin/ddjvu",
    )
    assert status.djvulibre


def test_check_native_tools_handles_missing_pytesseract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "pytesseract", None)
    _set_native_tool_lookup(monkeypatch)

    status = diagnostics_module.check_native_tools()

    assert status.tesseract == "/usr/bin/tesseract"
    assert status.languages == ()
    assert status.djvulibre


def test_check_native_tools_propagates_unexpected_tesseract_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_get_languages(*, config: str) -> list[str]:
        raise _UnexpectedTesseractError

    _install_fake_pytesseract(monkeypatch, fail_get_languages)
    _set_native_tool_lookup(monkeypatch)

    with pytest.raises(_UnexpectedTesseractError):
        diagnostics_module.check_native_tools()


def test_check_native_tools_reports_missing_tesseract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "pytesseract", None)
    _set_native_tool_lookup(monkeypatch, missing="tesseract")

    status = diagnostics_module.check_native_tools()

    assert status.tesseract is None
    assert status.languages == ()
    assert status.djvulibre


@pytest.mark.parametrize("missing_tool", ["djvutxt", "djvused", "ddjvu"])
def test_check_native_tools_reports_each_missing_djvu_tool(
    monkeypatch: pytest.MonkeyPatch,
    missing_tool: str,
) -> None:
    _install_fake_pytesseract(monkeypatch, lambda **_kwargs: ["eng", "rus"])
    _set_native_tool_lookup(monkeypatch, missing=missing_tool)

    status = diagnostics_module.check_native_tools()

    assert status.tesseract == "/usr/bin/tesseract"
    assert status.djvulibre is False
    assert getattr(status.djvu_tools, missing_tool) is None


def create_ready_app():
    app = FastAPI()
    app.state.model_holder = ModelHolder()
    app.include_router(ready_module.router)
    return app


def test_ready_is_public_and_reports_native_dependencies(monkeypatch):
    monkeypatch.setattr(settings, "DOCUMENT_API_KEY", "document-ready-test-key")
    monkeypatch.setattr(
        ready_module,
        "check_native_tools",
        lambda: diagnostics_module.NativeToolsStatus(
            "/usr/bin/tesseract",
            ("eng", "rus"),
            DjvuTools("/usr/bin/djvutxt", "/usr/bin/djvused", "/usr/bin/ddjvu"),
        ),
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
        "check_native_tools",
        lambda: diagnostics_module.NativeToolsStatus(
            None,
            (),
            DjvuTools(None, "/usr/bin/djvused", None),
        ),
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
