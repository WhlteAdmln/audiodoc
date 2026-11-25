# Copyright (c) 2026 Nikolai Zelensky

"""Tests for api error handlers."""

import logging
from collections.abc import Awaitable, Callable
from importlib import import_module
from types import SimpleNamespace
from typing import Never

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from audiodoc.api.error_handlers import register_error_handlers
from audiodoc.common.work_queue import WorkQueue
from audiodoc.errors.base import AppError, ServerBusyError
from audiodoc.errors.documents import (
    DependencyMissingError,
    DocumentRejectedError,
    PayloadTooLargeError,
    ProcessingTimeoutError,
    UnsupportedFormatError,
)
from audiodoc.errors.transcription import (
    AudioTooLongError,
    InvalidAudioError,
    ModelNotReadyError,
    TranscriptionTimeoutError,
)


class _UnexpectedServerError(RuntimeError):
    """Raised to exercise the sanitized unexpected-error handler."""

    def __init__(self) -> None:
        """Initialize the test exception with its private detail."""
        super().__init__("private /srv/audiodoc/secret.txt")


def _document_result() -> object:
    return {
        "format": "txt",
        "text": "plain text",
        "characters": 10,
        "truncated": False,
    }


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

    actual = (
        response.status_code,
        response.json(),
        response.headers.get("retry-after"),
    )
    expected = (
        status_code,
        {"detail": detail, "code": code},
        headers.get("Retry-After"),
    )
    assert actual == expected, "the typed error was mapped to the wrong response"


@pytest.fixture(name="unexpected_error_call")
def fixture_unexpected_error_call(caplog: pytest.LogCaptureFixture) -> SimpleNamespace:
    """Call a route that raises an unexpected exception; return response and log."""
    app = FastAPI()
    register_error_handlers(app)
    router = APIRouter()

    @router.get("/explode")
    async def explode() -> None:
        raise _UnexpectedServerError

    app.include_router(router)
    caplog.set_level(logging.ERROR)
    response = TestClient(app, raise_server_exceptions=False).get("/explode")
    return SimpleNamespace(response=response, log=caplog.text)


def test_unexpected_exception_returns_generic_message_without_details(
    unexpected_error_call: SimpleNamespace,
) -> None:
    response = unexpected_error_call.response
    actual = (response.status_code, response.json())
    expected = (500, {"detail": "Internal server error", "code": "internal_error"})
    assert actual == expected, "the unexpected error response is not generic"


def test_unexpected_exception_hides_private_file_name_from_response(
    unexpected_error_call: SimpleNamespace,
) -> None:
    private_file_name = "secret.txt"
    assert private_file_name not in unexpected_error_call.response.text, (
        "the response leaked a private file name"
    )


def test_unexpected_exception_logs_private_error_detail(
    unexpected_error_call: SimpleNamespace,
) -> None:
    private_error_detail = "private /srv/audiodoc/secret.txt"
    assert private_error_detail in unexpected_error_call.log, (
        "the error detail was not logged"
    )


def _upload_document(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    process_document: Callable[..., Awaitable[object]],
    filename: str,
) -> SimpleNamespace:
    documents = import_module("audiodoc.api.documents")
    monkeypatch.setattr(documents, "process_document", process_document)
    app = FastAPI()
    app.state.document_queue = WorkQueue(1, 4, error_factory=ServerBusyError)
    register_error_handlers(app)
    app.include_router(documents.router)
    response = TestClient(app).post(
        "/process-document",
        files={"file": (filename, b"plain text", "text/plain")},
    )
    return SimpleNamespace(response=response, log=caplog.text)


def _log_lines_starting_with(log: str, prefix: str) -> list[str]:
    return [line for line in log.splitlines() if line.startswith(prefix)]


@pytest.fixture(name="accepted_upload")
def fixture_accepted_upload(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> SimpleNamespace:
    """Upload a document whose name has a newline; return response and log."""

    async def fake_process_document(*_args: object, **_kwargs: object) -> object:
        return _document_result()

    caplog.set_level(logging.INFO)
    return _upload_document(
        caplog, monkeypatch, fake_process_document, "note\nINJECTED.log.txt"
    )


def test_document_with_newline_in_filename_is_accepted(
    accepted_upload: SimpleNamespace,
) -> None:
    expected_status_code = 200
    assert accepted_upload.response.status_code == expected_status_code, (
        "the document was not accepted"
    )


def test_document_filename_is_sanitized_before_logging(
    accepted_upload: SimpleNamespace,
) -> None:
    escaped_filename = "filename=note%0AINJECTED.log.txt"
    assert escaped_filename in accepted_upload.log, (
        "the file name was not escaped in the log"
    )


def test_document_filename_does_not_start_a_forged_log_line(
    accepted_upload: SimpleNamespace,
) -> None:
    forged_lines = _log_lines_starting_with(accepted_upload.log, "INJECTED.log.txt")
    expected_empty: list[str] = []
    assert forged_lines == expected_empty, "the file name forged a log line"


@pytest.fixture(name="rejected_upload")
def fixture_rejected_upload(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> SimpleNamespace:
    """Upload a rejected document whose name has a newline; return response, log."""

    async def reject_document(*_args: object, **_kwargs: object) -> Never:
        raise DocumentRejectedError

    caplog.set_level(logging.WARNING)
    return _upload_document(caplog, monkeypatch, reject_document, "bad\nFORGED.log.txt")


def test_typed_document_rejection_returns_rejection_response(
    rejected_upload: SimpleNamespace,
) -> None:
    response = rejected_upload.response
    actual = (response.status_code, response.json())
    expected = (
        400,
        {"detail": "Документ не может быть обработан", "code": "document_rejected"},
    )
    assert actual == expected, "the rejection was mapped to the wrong response"


def test_typed_document_rejection_is_logged(rejected_upload: SimpleNamespace) -> None:
    rejection_message = "Document rejected"
    assert rejection_message in rejected_upload.log, "the rejection was not logged"


def test_typed_document_rejection_is_logged_without_raw_filename(
    rejected_upload: SimpleNamespace,
) -> None:
    escaped_filename = "filename=bad%0AFORGED.log.txt"
    assert escaped_filename in rejected_upload.log, (
        "the file name was not escaped in the log"
    )


def test_typed_document_rejection_does_not_start_a_forged_log_line(
    rejected_upload: SimpleNamespace,
) -> None:
    forged_lines = _log_lines_starting_with(rejected_upload.log, "FORGED.log.txt")
    expected_empty: list[str] = []
    assert forged_lines == expected_empty, "the file name forged a log line"
