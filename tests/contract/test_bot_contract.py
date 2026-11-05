"""HTTP-контракт Document Engine с Telegram-ботом.

TestClient создаётся без context manager намеренно: контрактный тест документа
не требует запуска lifespan и загрузки модели Whisper.
"""

import pytest

pytest.importorskip("ebooklib")
pytest.importorskip("striprtf")

from fastapi.testclient import TestClient

from app import app


client = TestClient(app)


def test_document_response_matches_what_the_bot_validates():
    response = client.post(
        "/process-document",
        files={
            "file": (
                "note.txt",
                "Привет, мир! Это тест.".encode("utf-8"),
                "text/plain",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["format"], str)
    assert isinstance(body["text"], str)
    assert isinstance(body["characters"], int)
    assert "Привет" in body["text"]


def test_unsupported_file_is_not_a_success():
    response = client.post(
        "/process-document",
        files={"file": ("x.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )

    assert response.status_code != 200
