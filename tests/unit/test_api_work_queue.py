"""HTTP behavior for overloaded document and transcription queues."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.error_handlers import register_error_handlers
from backend.errors.base import ServerBusyError


def _app_with_router(router):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    return app


def test_server_busy_error_returns_retry_after_header():
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/busy")
    async def busy():
        raise ServerBusyError()

    response = TestClient(_app_with_router(router)).get("/busy")
    assert response.status_code == 503
    assert response.json() == {"detail": "Сервис занят. Повторите запрос позже"}
    assert response.headers["Retry-After"] == "30"


def test_document_queue_rejects_before_upload_is_copied(monkeypatch):
    import backend.api.documents as documents

    @asynccontextmanager
    async def reject_slot():
        raise ServerBusyError()
        yield

    def unexpected_read(*_args, **_kwargs):
        raise AssertionError("upload must not be read when the queue is full")

    monkeypatch.setattr(documents.document_queue, "slot", reject_slot)
    monkeypatch.setattr(documents, "read_upload_limited", unexpected_read)

    response = TestClient(_app_with_router(documents.router)).post(
        "/process-document",
        files={"file": ("note.txt", b"document", "text/plain")},
    )
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "30"


def test_transcription_queue_rejects_before_temp_file_write(monkeypatch):
    import backend.api.transcribe as transcribe

    @asynccontextmanager
    async def reject_slot():
        raise ServerBusyError()
        yield

    def unexpected_write(*_args, **_kwargs):
        raise AssertionError("audio must not be copied when the queue is full")

    monkeypatch.setattr(transcribe.model_holder, "_model", object())
    monkeypatch.setattr(transcribe.transcription_queue, "slot", reject_slot)
    monkeypatch.setattr(transcribe, "save_upload_limited", unexpected_write)

    response = TestClient(_app_with_router(transcribe.router)).post(
        "/transcribe",
        files={"file": ("voice.ogg", b"audio", "audio/ogg")},
    )
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "30"
