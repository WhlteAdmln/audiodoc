# Copyright (c) 2026 Nikolai Zelensky
"""HTTP behavior for overloaded document and transcription queues."""

from contextlib import asynccontextmanager
from importlib import import_module

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from backend.api.error_handlers import register_error_handlers
from backend.errors.base import ServerBusyError


class _UnexpectedUploadReadError(AssertionError):
    """Raised when a test unexpectedly reads an upload."""

    def __init__(self) -> None:
        """Initialize the test assertion error."""
        super().__init__("upload must not be read when the queue is full")


class _UnexpectedAudioWriteError(AssertionError):
    """Raised when a test unexpectedly writes an audio file."""

    def __init__(self) -> None:
        """Initialize the test assertion error."""
        super().__init__("audio must not be copied when the queue is full")


def _app_with_router(router):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    return app


def test_server_busy_error_returns_retry_after_header():
    router = APIRouter()

    @router.get("/busy")
    async def busy():
        raise ServerBusyError

    response = TestClient(_app_with_router(router)).get("/busy")
    assert response.status_code == 503
    assert response.json() == {"detail": "Сервис занят. Повторите запрос позже"}
    assert response.headers["Retry-After"] == "30"


def test_document_queue_rejects_before_upload_is_copied(monkeypatch):
    documents = import_module("backend.api.documents")

    @asynccontextmanager
    async def reject_slot():
        raise ServerBusyError
        yield

    def unexpected_read(*_args, **_kwargs):
        raise _UnexpectedUploadReadError

    monkeypatch.setattr(documents.document_queue, "slot", reject_slot)
    monkeypatch.setattr(documents, "read_upload_limited", unexpected_read)

    response = TestClient(_app_with_router(documents.router)).post(
        "/process-document",
        files={"file": ("note.txt", b"document", "text/plain")},
    )
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "30"


def test_transcription_queue_rejects_before_temp_file_write(monkeypatch):
    transcribe = import_module("backend.api.transcribe")

    @asynccontextmanager
    async def reject_slot():
        raise ServerBusyError
        yield

    def unexpected_write(*_args, **_kwargs):
        raise _UnexpectedAudioWriteError

    monkeypatch.setattr(transcribe.model_holder, "_model", object())
    monkeypatch.setattr(transcribe.transcription_queue, "slot", reject_slot)
    monkeypatch.setattr(transcribe, "save_upload_limited", unexpected_write)

    response = TestClient(_app_with_router(transcribe.router)).post(
        "/transcribe",
        files={"file": ("voice.ogg", b"audio", "audio/ogg")},
    )
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "30"
