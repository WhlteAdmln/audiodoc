# Copyright (c) 2026 Nikolai Zelensky
"""Tests for safe HTTP error responses and sanitized request logging."""

import logging
from importlib import import_module

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from backend.api.error_handlers import register_error_handlers
from backend.common.work_queue import WorkQueue
from backend.errors.base import AppError, BackendError, ServerBusyError
from backend.errors.documents import (
    DependencyMissingError,
    DocumentRejectedError,
    PayloadTooLargeError,
    ProcessingTimeoutError,
    UnsupportedFormatError,
)
from backend.errors.transcription import (
    AudioTooLongError,
    InvalidAudioError,
    ModelNotReadyError,
    TranscriptionTimeoutError,
)


class _UnexpectedServerError(RuntimeError):
    """Raised to exercise the sanitized unexpected-error handler."""

    def __init__(self) -> None:
        """Initialize the test exception with its private detail."""
        super().__init__("private /srv/backend/secret.txt")


@pytest.mark.parametrize(
    ("error_type", "status_code", "code", "detail", "headers"),
    [
        (AppError, 500, "internal_error", "Внутренняя ошибка сервиса", {}),
        (
            ServerBusyError,
            503,
            "server_busy",
            "Сервис занят. Повторите запрос позже",
            {"Retry-After": "30"},
        ),
        (
            DocumentRejectedError,
            400,
            "document_rejected",
            "Документ не может быть обработан",
            {},
        ),
        (
            UnsupportedFormatError,
            400,
            "unsupported_format",
            "Формат не поддерживается Document Engine",
            {},
        ),
        (PayloadTooLargeError, 413, "payload_too_large", "Файл слишком большой", {}),
        (
            ProcessingTimeoutError,
            504,
            "processing_timeout",
            "Превышено время обработки",
            {},
        ),
        (
            DependencyMissingError,
            503,
            "dependency_missing",
            "\u041d\u0430 сервере не установлена нужная программа",
            {},
        ),
        (
            InvalidAudioError,
            400,
            "invalid_audio",
            "\u041d\u0435 удалось прочитать аудиофайл",
            {},
        ),
        (AudioTooLongError, 400, "audio_too_long", "Аудио слишком длинное", {}),
        (
            ModelNotReadyError,
            503,
            "model_not_ready",
            "Модель Whisper ещё не загружена",
            {},
        ),
        (
            TranscriptionTimeoutError,
            504,
            "transcription_timeout",
            "Превышено время обработки аудио",
            {},
        ),
    ],
)
def test_typed_errors_return_status_code_detail_and_headers(
    error_type: type[AppError],
    status_code: int,
    code: str,
    detail: str,
    headers: dict[str, str],
) -> None:
    app = FastAPI()
    register_error_handlers(app)
    router = APIRouter()

    @router.get("/error")
    async def raise_typed_error() -> None:
        raise error_type()

    app.include_router(router)
    response = TestClient(app).get("/error")

    assert response.status_code == status_code
    assert response.json() == {"detail": detail, "code": code}
    assert response.headers.get("retry-after") == headers.get("Retry-After")


def test_backend_error_remains_an_alias_for_app_error() -> None:
    assert BackendError is AppError


def test_unexpected_exception_returns_generic_message_without_details(caplog):
    app = FastAPI()
    register_error_handlers(app)
    router = APIRouter()

    @router.get("/explode")
    async def explode():
        raise _UnexpectedServerError

    app.include_router(router)
    caplog.set_level(logging.ERROR)
    response = TestClient(app, raise_server_exceptions=False).get("/explode")

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Internal server error",
        "code": "internal_error",
    }
    assert "secret.txt" not in response.text
    assert "private /srv/backend/secret.txt" in caplog.text


def test_document_filename_is_sanitized_before_logging(caplog, monkeypatch):
    documents = import_module("backend.api.documents")

    async def fake_process_document(*_args, **_kwargs):
        return _document_result()

    monkeypatch.setattr(documents, "process_document", fake_process_document)

    app = FastAPI()
    app.state.document_queue = WorkQueue(1, 4, error_factory=ServerBusyError)
    register_error_handlers(app)
    app.include_router(documents.router)
    caplog.set_level(logging.INFO)

    response = TestClient(app).post(
        "/process-document",
        files={"file": ("note\nINJECTED.log.txt", b"plain text", "text/plain")},
    )

    assert response.status_code == 200
    assert "filename=note%0AINJECTED.log.txt" in caplog.text
    assert not any(
        line.startswith("INJECTED.log.txt") for line in caplog.text.splitlines()
    )


def _document_result():
    return {
        "format": "txt",
        "text": "plain text",
        "characters": 10,
        "truncated": False,
    }


def test_typed_document_rejection_is_logged_without_raw_filename(caplog, monkeypatch):
    documents = import_module("backend.api.documents")

    async def reject_document(*_args, **_kwargs):
        raise DocumentRejectedError

    monkeypatch.setattr(documents, "process_document", reject_document)
    app = FastAPI()
    app.state.document_queue = WorkQueue(1, 4, error_factory=ServerBusyError)
    register_error_handlers(app)
    app.include_router(documents.router)
    caplog.set_level(logging.WARNING)

    response = TestClient(app).post(
        "/process-document",
        files={"file": ("bad\nFORGED.log.txt", b"plain text", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Документ не может быть обработан",
        "code": "document_rejected",
    }
    assert "Document rejected" in caplog.text
    assert "filename=bad%0AFORGED.log.txt" in caplog.text
    assert not any(
        line.startswith("FORGED.log.txt") for line in caplog.text.splitlines()
    )
