from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import ready as ready_module
from backend.config import settings
from backend.transcription.model import model_holder


def create_ready_app():
    app = FastAPI()
    app.include_router(ready_module.router)
    return app


def test_ready_requires_document_key_and_reports_native_dependencies(monkeypatch):
    monkeypatch.setattr(settings, "DOCUMENT_API_KEY", "document-ready-test-key")
    monkeypatch.setattr(
        ready_module,
        "_available_tesseract_languages",
        lambda: (True, ["eng", "rus"]),
    )
    monkeypatch.setattr(
        ready_module.shutil,
        "which",
        lambda name: f"/usr/bin/{name}",
    )
    monkeypatch.setattr(model_holder, "_model", object())
    client = TestClient(create_ready_app())

    assert client.get("/ready").status_code == 401
    response = client.get(
        "/ready",
        headers={"Authorization": "Bearer document-ready-test-key"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "tesseract": True,
        "languages": ["eng", "rus"],
        "djvulibre": True,
        "model_loaded": True,
    }


def test_ready_reports_missing_programs_without_raising(monkeypatch):
    monkeypatch.setattr(settings, "DOCUMENT_API_KEY", "document-ready-test-key")
    monkeypatch.setattr(
        ready_module,
        "_available_tesseract_languages",
        lambda: (False, []),
    )
    monkeypatch.setattr(
        ready_module.shutil,
        "which",
        lambda name: {"djvused": "/usr/bin/djvused"}.get(name),
    )
    monkeypatch.setattr(model_holder, "_model", None)

    response = TestClient(create_ready_app()).get(
        "/ready",
        headers={"Authorization": "Bearer document-ready-test-key"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "tesseract": False,
        "languages": [],
        "djvulibre": False,
        "model_loaded": False,
    }
