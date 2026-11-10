# Copyright (c) 2026 Nikolai Zelensky
"""Uvicorn-backed live server fixture for API support tests."""

from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
import uvicorn

from audiodoc.api.middleware import BodySizeLimitMiddleware
from audiodoc.config import Settings, settings
from audiodoc.main import create_app
from audiodoc.transcription import model as model_module
from audiodoc.transcription import temp_files

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from fastapi import FastAPI

_SERVER_EXITED_BEFORE_START = "Uvicorn stopped before startup completed"
_SERVER_START_TIMEOUT = "Uvicorn test server did not start"
_SERVER_SHUTDOWN_TIMEOUT = "Uvicorn test server did not stop"


@dataclass(frozen=True, slots=True)
class LiveServer:
    """Connection details and isolated resources for a live test server."""

    base_url: str
    whisper_api_key: str
    document_api_key: str
    temp_dir: Path


@dataclass(frozen=True, slots=True)
class LiveServerOptions:
    """Optional settings for an isolated live test server."""

    whisper_api_key: str = "test-whisper-key"
    document_api_key: str = "test-document-key"
    allow_unauthenticated: bool = False
    enable_docs: bool = False
    max_body_size: int | None = None


@dataclass(frozen=True, slots=True)
class _FakeSegment:
    text: str = "Test transcription"


@dataclass(frozen=True, slots=True)
class _FakeInfo:
    duration: float = 1.0
    language: str = "ru"


class _FakeWhisperModel:
    """Provide deterministic transcription without loading a real model."""

    def transcribe(
        self,
        audio: str,
        *,
        language: str | None,
        beam_size: int,
        vad_filter: bool,
    ) -> tuple[Iterator[_FakeSegment], _FakeInfo]:
        _ = (audio, language, beam_size, vad_filter)
        return iter((_FakeSegment(),)), _FakeInfo()


def _configure_live_server_settings(
    options: LiveServerOptions,
    monkeypatch: pytest.MonkeyPatch,
    temp_dir: Path,
) -> None:
    """Configure isolated application settings for a live test."""
    monkeypatch.setattr(settings, "WHISPER_API_KEY", options.whisper_api_key)
    monkeypatch.setattr(settings, "DOCUMENT_API_KEY", options.document_api_key)
    monkeypatch.setattr(
        settings, "ALLOW_UNAUTHENTICATED", options.allow_unauthenticated
    )
    monkeypatch.setattr(settings, "ENABLE_DOCS", options.enable_docs)
    monkeypatch.setattr(settings, "TEMP_DIR", str(temp_dir))
    monkeypatch.setattr(temp_files, "TEMP_DIR", temp_dir)

    def build_fake_model(
        _configured_settings: Settings | None,
    ) -> _FakeWhisperModel:
        return _FakeWhisperModel()

    monkeypatch.setattr(model_module, "_build_model", build_fake_model)


def _create_live_application(options: LiveServerOptions) -> FastAPI:
    """Create the application with optional test-specific body limits."""
    application = create_app()
    if options.max_body_size is not None:
        middleware = next(
            (
                item
                for item in application.user_middleware
                if item.cls is BodySizeLimitMiddleware
            ),
            None,
        )
        if middleware is None:
            raise AssertionError
        middleware.kwargs["max_body_size"] = options.max_body_size
    return application


@pytest.fixture
def live_server(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> Iterator[LiveServer]:
    """Run the real FastAPI application on an isolated loopback port."""
    options = getattr(request, "param", LiveServerOptions())
    if not isinstance(options, LiveServerOptions):
        raise TypeError

    _configure_live_server_settings(options, monkeypatch, tmp_path)

    whisper_api_key = options.whisper_api_key
    document_api_key = options.document_api_key
    host = "127.0.0.1"

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((host, 0))
        listener.listen()
        listener.setblocking(False)
        port = listener.getsockname()[1]

        config = uvicorn.Config(
            app=_create_live_application(options),
            host=host,
            port=port,
            lifespan="on",
            log_level="warning",
            access_log=False,
        )
        server = uvicorn.Server(config)
        thread = threading.Thread(
            target=server.run,
            kwargs={"sockets": [listener]},
            name="audiodoc-test-uvicorn",
            daemon=True,
        )

        try:
            thread.start()
            deadline = time.monotonic() + 10
            while not server.started:
                if not thread.is_alive():
                    raise RuntimeError(_SERVER_EXITED_BEFORE_START)
                if time.monotonic() >= deadline:
                    raise TimeoutError(_SERVER_START_TIMEOUT)
                time.sleep(0.01)

            yield LiveServer(
                base_url=f"http://{host}:{port}",
                whisper_api_key=whisper_api_key,
                document_api_key=document_api_key,
                temp_dir=tmp_path,
            )
        finally:
            server.should_exit = True
            if thread.ident is not None:
                thread.join(timeout=10)
            if thread.is_alive():
                raise RuntimeError(_SERVER_SHUTDOWN_TIMEOUT)
