# Copyright (c) 2026 Nikolai Zelensky
"""HTTP response contract shared with the Telegram bot."""

import json
from pathlib import Path

from fastapi.testclient import TestClient
from jsonschema import validate

from app import app
from backend.common.work_queue import WorkQueue
from backend.transcription.model import ModelHolder
from scripts.export_openapi import render_openapi

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "audiodoc_responses.json"
CONTRACT = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
OPENAPI_PATH = ROOT / "contract" / "openapi.json"
OPENAPI = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
app.state.model_holder = ModelHolder()
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
    monkeypatch.setattr(app.state.model_holder, "_model", object())

    async def fake_transcribe_file(
        _path: Path,
        *,
        _slot_acquired: bool = False,
        configured_model_holder: object | None = None,
        queue: WorkQueue,
    ) -> dict[str, object]:
        assert _slot_acquired is True
        assert configured_model_holder is app.state.model_holder
        assert queue is app.state.transcription_queue
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


def test_openapi_snapshot_matches_application() -> None:
    """Keep the checked-in OpenAPI snapshot synchronized with the app."""
    assert OPENAPI_PATH.read_text(encoding="utf-8") == render_openapi(), (
        "OpenAPI snapshot is out of date; run `make contract`"
    )


def test_bot_examples_validate_against_openapi_schemas() -> None:
    """Validate every shared bot response example against its response schema."""
    examples = {
        "transcribe": "/transcribe",
        "process_document": "/process-document",
    }
    for example_name, path in examples.items():
        response_schema = OPENAPI["paths"][path]["post"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        schema_name = response_schema["$ref"].rsplit("/", maxsplit=1)[-1]
        validate(
            instance=CONTRACT[example_name],
            schema=OPENAPI["components"]["schemas"][schema_name],
        )


def test_every_openapi_path_is_mentioned_in_api_docs() -> None:
    """Require the API documentation to mention every OpenAPI path."""
    documentation = (ROOT / "docs" / "api.md").read_text(encoding="utf-8")
    for path in OPENAPI["paths"]:
        assert path in documentation, f"OpenAPI path {path} is missing from docs/api.md"
