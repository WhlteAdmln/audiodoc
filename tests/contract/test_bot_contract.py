# Copyright (c) 2026 Nikolai Zelensky
"""HTTP response contract shared with the Telegram bot."""

import json
from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jsonschema import validate

from audiodoc.common.work_queue import WorkQueue
from audiodoc.main import create_app
from audiodoc.transcription.model import ModelHolder
from scripts.export_openapi import render_openapi
from tests.support.whisper import FakeWhisperModel, loaded_model_holder

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "audiodoc_responses.json"
CONTRACT = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
OPENAPI_PATH = ROOT / "contract" / "openapi.json"
OPENAPI = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))


@pytest.fixture(name="app")
def fixture_app() -> FastAPI:
    """Create an application with an unloaded model holder for one test."""
    application = create_app()
    application.state.model_holder = ModelHolder()
    return application


@pytest.fixture(name="client")
def fixture_client(app: FastAPI) -> TestClient:
    """Create a test client for the application of one test."""
    return TestClient(app)


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


def test_transcribe_response_matches_shared_bot_contract(
    monkeypatch: pytest.MonkeyPatch,
    app: FastAPI,
    client: TestClient,
) -> None:
    app.state.model_holder = loaded_model_holder(FakeWhisperModel())

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

    monkeypatch.setattr("audiodoc.api.transcribe.transcribe_file", fake_transcribe_file)

    response = client.post(
        "/transcribe",
        files={"file": ("voice.ogg", b"fake audio", "audio/ogg")},
    )

    assert response.status_code == HTTPStatus.OK
    _assert_transcribe_shape(response.json())


def test_process_document_response_matches_shared_bot_contract(
    client: TestClient,
) -> None:
    sample = CONTRACT["process_document"]["text"]
    response = client.post(
        "/process-document",
        files={"file": ("note.txt", sample.encode("utf-8"), "text/plain")},
    )

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    _assert_document_shape(payload)
    assert payload == CONTRACT["process_document"]


def test_unsupported_file_is_not_a_success(client: TestClient) -> None:
    response = client.post(
        "/process-document",
        files={"file": ("x.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )

    assert response.status_code != HTTPStatus.OK


def test_openapi_snapshot_matches_application() -> None:
    assert OPENAPI_PATH.read_text(encoding="utf-8") == render_openapi(), (
        "OpenAPI snapshot is out of date; run `make contract`"
    )


def test_bot_examples_validate_against_openapi_schemas() -> None:
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


def test_error_responses_publish_machine_readable_codes() -> None:
    expected_codes = {
        "/transcribe": {
            "400": ("invalid_audio", "audio_too_long"),
            "500": ("internal_error",),
            "503": ("model_not_ready", "server_busy"),
            "504": ("transcription_timeout",),
        },
        "/process-document": {
            "400": ("document_rejected", "unsupported_format"),
            "413": ("payload_too_large",),
            "500": ("internal_error",),
            "503": ("dependency_missing", "server_busy"),
            "504": ("processing_timeout",),
        },
    }
    error_schema = OPENAPI["components"]["schemas"]["ErrorResponse"]
    assert set(error_schema["required"]) == {"detail", "code"}
    assert set(error_schema["properties"]["code"]["enum"]) == {
        "internal_error",
        "server_busy",
        "document_rejected",
        "unsupported_format",
        "payload_too_large",
        "processing_timeout",
        "dependency_missing",
        "invalid_audio",
        "audio_too_long",
        "model_not_ready",
        "transcription_timeout",
    }

    for path, path_errors in expected_codes.items():
        operation = OPENAPI["paths"][path]["post"]
        for status_code, codes in path_errors.items():
            response = operation["responses"][status_code]
            assert response["content"]["application/json"]["schema"] == {
                "$ref": "#/components/schemas/ErrorResponse"
            }
            assert all(code in response["description"] for code in codes)

        assert "Retry-After" in operation["responses"]["503"]["headers"]


def test_every_openapi_path_is_mentioned_in_api_docs() -> None:
    documentation = (ROOT / "docs" / "api.md").read_text(encoding="utf-8")
    for path in OPENAPI["paths"]:
        assert path in documentation, f"OpenAPI path {path} is missing from docs/api.md"
