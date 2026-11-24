# Copyright (c) 2026 Nikolai Zelensky

"""Tests for api documents."""

from importlib import import_module
from typing import Never

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


def test_document_endpoint_accepts_optional_character_budget(
    client: TestClient,
) -> None:
    response = client.post(
        "/process-document",
        files={"file": ("note.txt", b"0123456789", "text/plain")},
        data={"max_characters": "5"},
    )
    expected_status_code = 200
    assert response.status_code == expected_status_code
    assert response.json() == {
        "format": "txt",
        "text": "01234",
        "characters": 5,
        "truncated": True,
    }


def test_document_endpoint_keeps_legacy_request_without_budget(
    client: TestClient,
) -> None:
    response = client.post(
        "/process-document",
        files={"file": ("note.txt", b"hello", "text/plain")},
    )
    expected_status_code = 200
    assert response.status_code == expected_status_code
    expected_text = "hello"
    assert response.json()["text"] == expected_text
    assert response.json()["truncated"] is False


def test_document_endpoint_validates_character_budget_range(client: TestClient) -> None:
    response = client.post(
        "/process-document",
        files={"file": ("note.txt", b"hello", "text/plain")},
        data={"max_characters": "0"},
    )
    expected_status_code = 422
    assert response.status_code == expected_status_code


def test_document_queue_rejects_before_upload_is_copied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    documents = import_module("audiodoc.api.documents")
    queue = closed_queue()

    def unexpected_read(*_args: object, **_kwargs: object) -> Never:
        raise _UnexpectedUploadReadError

    monkeypatch.setattr(documents, "read_upload_limited", unexpected_read)

    response = TestClient(app_with_router(documents.router, document_queue=queue)).post(
        "/process-document",
        files={"file": ("note.txt", b"document", "text/plain")},
    )
    expected_status_code = 503
    assert response.status_code == expected_status_code
    expected_retry_after = "30"
    assert response.headers["Retry-After"] == expected_retry_after
