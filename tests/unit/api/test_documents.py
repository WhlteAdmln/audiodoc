# Copyright (c) 2026 Nikolai Zelensky

"""Tests for api documents."""

from importlib import import_module
from typing import Never

import httpx2
import pytest
from fastapi.testclient import TestClient

from audiodoc.main import create_app
from tests.support.api_app import app_with_router, closed_queue


@pytest.fixture(name="client")
def fixture_client() -> TestClient:
    """Create a test client for a fresh application."""
    return TestClient(create_app())


class _UnexpectedUploadReadError(AssertionError):
    """Raised when a test unexpectedly reads an upload."""

    def __init__(self) -> None:
        """Initialize the test assertion error."""
        super().__init__("upload must not be read when the queue is full")


@pytest.fixture(name="busy_response")
def fixture_busy_response(monkeypatch: pytest.MonkeyPatch) -> httpx2.Response:
    """Post a document to a router whose queue is closed and fail if it is read."""
    documents = import_module("audiodoc.api.documents")

    def unexpected_read(*_args: object, **_kwargs: object) -> Never:
        raise _UnexpectedUploadReadError

    monkeypatch.setattr(documents, "read_upload_limited", unexpected_read)
    client = TestClient(
        app_with_router(documents.router, document_queue=closed_queue())
    )
    return client.post(
        "/process-document",
        files={"file": ("note.txt", b"document", "text/plain")},
    )


def test_applies_character_budget(client: TestClient) -> None:
    response = client.post(
        "/process-document",
        files={"file": ("note.txt", b"0123456789", "text/plain")},
        data={"max_characters": "5"},
    )

    expected_body = {
        "format": "txt",
        "text": "01234",
        "characters": 5,
        "truncated": True,
    }
    assert response.json() == expected_body, "the budget was not applied"


def test_returns_whole_text_without_budget(client: TestClient) -> None:
    response = client.post(
        "/process-document",
        files={"file": ("заметка.txt", "привет, мир".encode(), "text/plain")},
    )

    expected_body = {
        "format": "txt",
        "text": "привет, мир",
        "characters": 11,
        "truncated": False,
    }
    assert response.json() == expected_body, "a request without budget changed"


@pytest.mark.parametrize(
    "max_characters", ["0", "-1", "2000001", "abc", "1.5", "1e3", " "], ids=repr
)
def test_rejects_invalid_character_budget(
    client: TestClient, max_characters: str
) -> None:
    response = client.post(
        "/process-document",
        files={"file": ("note.txt", "Отчёт за Q3".encode(), "text/plain")},
        data={"max_characters": max_characters},
    )

    expected_status = 422
    assert response.status_code == expected_status, "a bad budget was accepted"


@pytest.mark.parametrize(
    "filename",
    [
        "../../../etc/passwd.txt",
        "..\\..\\windows\\win.ini.txt",
        "/abs/path/note.txt",
        "line\r\nbreak.txt",
        "%2e%2e%2fnote.txt",
    ],
    ids=["dot-dot", "backslash", "absolute", "crlf", "encoded"],
)
def test_processes_upload_with_hostile_filename(
    client: TestClient, filename: str
) -> None:
    response = client.post(
        "/process-document",
        files={"file": (filename, b"plain body", "text/plain")},
    )

    expected_text = "plain body"
    assert response.json().get("text") == expected_text, "a hostile name broke it"


def test_rejects_request_without_file(client: TestClient) -> None:
    response = client.post("/process-document", data={"max_characters": "5"})

    expected_status = 422
    assert response.status_code == expected_status, "a request without file passed"


def test_rejects_unsupported_format(client: TestClient) -> None:
    response = client.post(
        "/process-document",
        files={"file": ("tool.exe", b"MZ\x90\x00\x03", "application/octet-stream")},
    )

    expected_status = 400
    assert response.status_code == expected_status, "an executable was accepted"


def test_reports_payload_too_large_code_for_oversized_document(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    documents = import_module("audiodoc.api.documents")
    monkeypatch.setattr(documents, "MAX_DOCUMENT_SIZE", 11)

    response = client.post(
        "/process-document",
        files={"file": ("отчёт.txt", "квартальный отчёт".encode(), "text/plain")},
    )

    expected_body = {
        "detail": "Файл слишком большой. Максимальный размер: 0 МБ.",
        "code": "payload_too_large",
    }
    assert response.json() == expected_body, "an oversized document gave no code"


def test_hides_unexpected_failure_behind_internal_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    documents = import_module("audiodoc.api.documents")

    def broken_processing(*_args: object, **_kwargs: object) -> Never:
        raise LookupError

    monkeypatch.setattr(documents, "process_document", broken_processing)

    response = client.post(
        "/process-document",
        files={"file": ("plan-2026.md", b"# Roadmap\n- ship", "text/markdown")},
    )

    expected_body = {"detail": "Document processing failed", "code": "internal_error"}
    assert response.json() == expected_body, "an unexpected failure gave no code"


def test_busy_queue_answers_service_unavailable(busy_response: httpx2.Response) -> None:
    expected_status = 503
    assert busy_response.status_code == expected_status, "a full queue read the upload"


def test_busy_queue_asks_client_to_retry_later(busy_response: httpx2.Response) -> None:
    expected_retry_after = "30"
    assert busy_response.headers.get("Retry-After") == expected_retry_after, (
        "no Retry-After on a busy queue"
    )
