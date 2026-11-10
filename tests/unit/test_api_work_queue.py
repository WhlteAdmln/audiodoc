# Copyright (c) 2026 Nikolai Zelensky
"""HTTP behavior for overloaded document and transcription queues."""

import asyncio
from importlib import import_module

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from audiodoc.api.error_handlers import register_error_handlers
from audiodoc.common.work_queue import WorkQueue
from audiodoc.errors.base import ServerBusyError
from audiodoc.transcription.model import ModelHolder


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


def _app_with_router(
    router: APIRouter,
    *,
    model_holder: ModelHolder | None = None,
    document_queue: WorkQueue | None = None,
    transcription_queue: WorkQueue | None = None,
) -> FastAPI:
    app = FastAPI()
    if model_holder is not None:
        app.state.model_holder = model_holder
    if document_queue is not None:
        app.state.document_queue = document_queue
    if transcription_queue is not None:
        app.state.transcription_queue = transcription_queue
    register_error_handlers(app)
    app.include_router(router)
    return app


def _closed_queue() -> WorkQueue:
    queue = WorkQueue(workers=1, max_waiting=0, error_factory=ServerBusyError)
    asyncio.run(queue.shutdown())
    return queue


def test_server_busy_error_returns_retry_after_header():
    router = APIRouter()

    @router.get("/busy")
    async def busy():
        raise ServerBusyError

    response = TestClient(_app_with_router(router)).get("/busy")
    assert response.status_code == 503
    assert response.json() == {
        "detail": "Сервис занят. Повторите запрос позже",
        "code": "server_busy",
    }
    assert response.headers["Retry-After"] == "30"


def test_document_queue_rejects_before_upload_is_copied(monkeypatch):
    documents = import_module("audiodoc.api.documents")
    queue = _closed_queue()

    def unexpected_read(*_args, **_kwargs):
        raise _UnexpectedUploadReadError

    monkeypatch.setattr(documents, "read_upload_limited", unexpected_read)

    response = TestClient(
        _app_with_router(documents.router, document_queue=queue)
    ).post(
        "/process-document",
        files={"file": ("note.txt", b"document", "text/plain")},
    )
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "30"


def test_transcription_queue_rejects_before_temp_file_write(monkeypatch):
    transcribe = import_module("audiodoc.api.transcribe")
    queue = _closed_queue()

    def unexpected_write(*_args, **_kwargs):
        raise _UnexpectedAudioWriteError

    configured_model_holder = ModelHolder()
    monkeypatch.setattr(configured_model_holder, "_model", object())
    monkeypatch.setattr(transcribe, "save_upload_limited", unexpected_write)

    response = TestClient(
        _app_with_router(
            transcribe.router,
            model_holder=configured_model_holder,
            transcription_queue=queue,
        )
    ).post(
        "/transcribe",
        files={"file": ("voice.ogg", b"audio", "audio/ogg")},
    )
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "30"
