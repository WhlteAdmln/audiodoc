# Copyright (c) 2026 Nikolai Zelensky
"""HTTP tests for optional max_characters and the truncation response flag."""

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_document_endpoint_accepts_optional_character_budget():
    response = client.post(
        "/process-document",
        files={"file": ("note.txt", b"0123456789", "text/plain")},
        data={"max_characters": "5"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "format": "txt",
        "text": "01234",
        "characters": 5,
        "truncated": True,
    }


def test_document_endpoint_keeps_legacy_request_without_budget():
    response = client.post(
        "/process-document",
        files={"file": ("note.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 200
    assert response.json()["text"] == "hello"
    assert response.json()["truncated"] is False


def test_document_endpoint_validates_character_budget_range():
    response = client.post(
        "/process-document",
        files={"file": ("note.txt", b"hello", "text/plain")},
        data={"max_characters": "0"},
    )
    assert response.status_code == 422
