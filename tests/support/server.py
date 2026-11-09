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

from backend.config import settings
from backend.main import create_app
from backend.transcription import model as model_module
from backend.transcription import temp_files

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

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


@pytest.fixture
def live_server(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[LiveServer]:
    """Run the real FastAPI application on an isolated loopback port."""
    whisper_api_key = "test-whisper-key"
    document_api_key = "test-document-key"
    monkeypatch.setattr(settings, "WHISPER_API_KEY", whisper_api_key)
    monkeypatch.setattr(settings, "DOCUMENT_API_KEY", document_api_key)
    monkeypatch.setattr(settings, "ALLOW_UNAUTHENTICATED", False)
    monkeypatch.setattr(settings, "TEMP_DIR", str(tmp_path))
    monkeypatch.setattr(temp_files, "TEMP_DIR", tmp_path)
    monkeypatch.setattr(model_module, "_build_model", _FakeWhisperModel)
    monkeypatch.setattr(model_module.model_holder, "_model", None)

    host = "127.0.0.1"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((host, 0))
        listener.listen()
        listener.setblocking(False)
        port = listener.getsockname()[1]

        config = uvicorn.Config(
            app=create_app(),
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
