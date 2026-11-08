# Copyright (c) 2026 Nikolai Zelensky
"""HTTP response contract shared with the Telegram bot."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import app
from backend.transcription.model import model_holder

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "audiodoc_responses.json"
CONTRACT = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
client = TestClient(app)


def _assert_transcribe_shape(payload: dict) -> None:
    assert set(payload) == set(CONTRACT["transcribe"])
    assert isinstance(payload["text"], str)
    assert isinstance(payload["language"], str)
    assert isinstance(payload["duration"], (int, float))


def _assert_document_shape(payload: dict) -> None:
    assert set(payload) == set(CONTRACT["process_document"])
    assert isinstance(payload["format"], str)
    assert isinstance(payload["text"], str)
    assert isinstance(payload["characters"], int)
    assert isinstance(payload["truncated"], bool)
    assert payload["characters"] == len(payload["text"])


def test_transcribe_response_matches_shared_bot_contract(monkeypatch):
    monkeypatch.setattr(model_holder, "_model", object())

    async def fake_transcribe_file(_path, *, _slot_acquired=False):
        assert _slot_acquired is True
        return dict(CONTRACT["transcribe"])

    monkeypatch.setattr("backend.api.transcribe.transcribe_file", fake_transcribe_file)

    response = client.post(
        "/transcribe",
        files={"file": ("voice.ogg", b"fake audio", "audio/ogg")},
    )

    assert response.status_code == 200
    _assert_transcribe_shape(response.json())


def test_process_document_response_matches_shared_bot_contract():
    sample = CONTRACT["process_document"]["text"]
    response = client.post(
        "/process-document",
        files={"file": ("note.txt", sample.encode("utf-8"), "text/plain")},
    )

    assert response.status_code == 200
    payload = response.json()
    _assert_document_shape(payload)
    assert payload == CONTRACT["process_document"]


def test_unsupported_file_is_not_a_success():
    response = client.post(
        "/process-document",
        files={"file": ("x.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )

    assert response.status_code != 200
