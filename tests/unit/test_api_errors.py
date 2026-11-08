"""Tests for safe HTTP error responses and sanitized request logging."""

import logging

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from backend.api.error_handlers import register_error_handlers


def test_unexpected_exception_returns_generic_message_without_details(caplog):
    app = FastAPI()
    register_error_handlers(app)
    router = APIRouter()

    @router.get("/explode")
    async def explode():
        raise RuntimeError("private /srv/backend/secret.txt")

    app.include_router(router)
    caplog.set_level(logging.ERROR)
    response = TestClient(app, raise_server_exceptions=False).get("/explode")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "secret.txt" not in response.text
    assert "private /srv/backend/secret.txt" in caplog.text


def test_document_filename_is_sanitized_before_logging(caplog, monkeypatch):
    from backend.api import documents
    from backend.api.error_handlers import register_error_handlers

    async def fake_process_document(*_args, **_kwargs):
        return _document_result()

    monkeypatch.setattr(documents, "process_document", fake_process_document)

    app = FastAPI()
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
    from backend.api import documents
    from backend.errors.documents import DocumentRejectedError

    async def reject_document(*_args, **_kwargs):
        raise DocumentRejectedError("Документ не может быть обработан")

    monkeypatch.setattr(documents, "process_document", reject_document)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(documents.router)
    caplog.set_level(logging.WARNING)

    response = TestClient(app).post(
        "/process-document",
        files={"file": ("bad\nFORGED.log.txt", b"plain text", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Документ не может быть обработан"}
    assert "Document rejected" in caplog.text
    assert "filename=bad%0AFORGED.log.txt" in caplog.text
    assert not any(
        line.startswith("FORGED.log.txt") for line in caplog.text.splitlines()
    )
