# Copyright (c) 2026 Nikolai Zelensky
"""HTTP response contract shared with the Telegram bot."""

import json
from http import HTTPStatus
from pathlib import Path
from typing import Any

import httpx2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jsonschema.validators import validator_for

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


@pytest.fixture(name="transcription_calls")
def fixture_transcription_calls() -> list[dict[str, object]]:
    """Collect the arguments of fake transcription calls for one test."""
    return []


@pytest.fixture(name="transcribe_response")
def fixture_transcribe_response(
    monkeypatch: pytest.MonkeyPatch,
    app: FastAPI,
    client: TestClient,
    transcription_calls: list[dict[str, object]],
) -> httpx2.Response:
    """Post an audio file to a loaded application with a fake transcription."""
    app.state.model_holder = loaded_model_holder(FakeWhisperModel())

    async def fake_transcribe_file(
        _path: Path,
        *,
        _slot_acquired: bool = False,
        configured_model_holder: object | None = None,
        queue: WorkQueue,
    ) -> dict[str, object]:
        transcription_calls.append(
            {
                "slot_acquired": _slot_acquired,
                "model_holder": configured_model_holder,
                "queue": queue,
            }
        )
        return dict(CONTRACT["transcribe"])

    monkeypatch.setattr("audiodoc.api.transcribe.transcribe_file", fake_transcribe_file)

    return client.post(
        "/transcribe",
        files={"file": ("voice.ogg", b"fake audio", "audio/ogg")},
    )


@pytest.fixture(name="document_response")
def fixture_document_response(client: TestClient) -> httpx2.Response:
    """Post the contract sample text as a document."""
    sample = CONTRACT["process_document"]["text"]
    return client.post(
        "/process-document",
        files={"file": ("note.txt", sample.encode("utf-8"), "text/plain")},
    )


def _transcribe_shape(payload: dict[str, Any]) -> dict[str, object]:
    return {
        "fields": set(payload),
        "text_is_str": isinstance(payload["text"], str),
        "language_is_str": isinstance(payload["language"], str),
        "duration_is_number": isinstance(payload["duration"], (int, float)),
    }


def _document_shape(payload: dict[str, Any]) -> dict[str, object]:
    return {
        "fields": set(payload),
        "format_is_str": isinstance(payload["format"], str),
        "text_is_str": isinstance(payload["text"], str),
        "characters_is_int": isinstance(payload["characters"], int),
        "truncated_is_bool": isinstance(payload["truncated"], bool),
        "characters_count_text": payload["characters"] == len(payload["text"]),
    }


@pytest.mark.usefixtures("transcribe_response")
def test_transcribe_passes_slot_model_and_queue_to_transcription(
    app: FastAPI,
    transcription_calls: list[dict[str, object]],
) -> None:
    passed_arguments = [
        (
            call["slot_acquired"],
            call["model_holder"] is app.state.model_holder,
            call["queue"] is app.state.transcription_queue,
        )
        for call in transcription_calls
    ]

    expected_arguments = [(True, True, True)]
    assert passed_arguments == expected_arguments, (
        "transcription did not get the acquired slot, model holder and queue"
    )


def test_transcribe_succeeds_for_the_bot(transcribe_response: httpx2.Response) -> None:
    assert transcribe_response.status_code == HTTPStatus.OK, "transcription failed"


def test_transcribe_response_matches_shared_bot_contract(
    transcribe_response: httpx2.Response,
) -> None:
    expected_shape = {
        "fields": set(CONTRACT["transcribe"]),
        "text_is_str": True,
        "language_is_str": True,
        "duration_is_number": True,
    }
    assert _transcribe_shape(transcribe_response.json()) == expected_shape, (
        "the transcription response breaks the bot contract"
    )


def test_process_document_succeeds_for_the_bot(
    document_response: httpx2.Response,
) -> None:
    assert document_response.status_code == HTTPStatus.OK, "document processing failed"


def test_process_document_response_matches_shared_bot_contract(
    document_response: httpx2.Response,
) -> None:
    expected_shape = {
        "fields": set(CONTRACT["process_document"]),
        "format_is_str": True,
        "text_is_str": True,
        "characters_is_int": True,
        "truncated_is_bool": True,
        "characters_count_text": True,
    }
    assert _document_shape(document_response.json()) == expected_shape, (
        "the document response breaks the bot contract"
    )


def test_process_document_response_equals_the_contract_example(
    document_response: httpx2.Response,
) -> None:
    expected_payload = CONTRACT["process_document"]
    assert document_response.json() == expected_payload, (
        "the document response differs from the contract example"
    )


def test_unsupported_file_is_not_a_success(client: TestClient) -> None:
    response = client.post(
        "/process-document",
        files={"file": ("x.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )

    assert response.status_code != HTTPStatus.OK, "an unsupported file succeeded"


def test_openapi_snapshot_matches_application() -> None:
    assert OPENAPI_PATH.read_text(encoding="utf-8") == render_openapi(), (
        "OpenAPI snapshot is out of date; run `make contract`"
    )


@pytest.mark.parametrize(
    ("example_name", "path"),
    [("transcribe", "/transcribe"), ("process_document", "/process-document")],
)
def test_bot_examples_validate_against_openapi_schemas(
    example_name: str,
    path: str,
) -> None:
    response_schema = OPENAPI["paths"][path]["post"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    schema_name = response_schema["$ref"].rsplit("/", maxsplit=1)[-1]
    schema = OPENAPI["components"]["schemas"][schema_name]
    validator_class = validator_for(schema)
    validator_class.check_schema(schema)
    errors = [
        error.message
        for error in validator_class(schema).iter_errors(CONTRACT[example_name])
    ]

    expected_empty: list[str] = []
    assert errors == expected_empty, f"the {example_name} example breaks its schema"


def test_error_schema_requires_detail_and_code() -> None:
    error_schema = OPENAPI["components"]["schemas"]["ErrorResponse"]

    expected_required = {"detail", "code"}
    assert set(error_schema["required"]) == expected_required, (
        "the error schema requires other fields"
    )


def test_error_schema_lists_every_error_code() -> None:
    error_schema = OPENAPI["components"]["schemas"]["ErrorResponse"]

    expected_codes = {
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
    assert set(error_schema["properties"]["code"]["enum"]) == expected_codes, (
        "the error schema lists other codes"
    )


@pytest.mark.parametrize(
    ("path", "status_code", "codes"),
    [
        ("/transcribe", "400", ("invalid_audio", "audio_too_long")),
        ("/transcribe", "413", ("payload_too_large",)),
        ("/transcribe", "500", ("internal_error",)),
        ("/transcribe", "503", ("model_not_ready", "server_busy")),
        ("/transcribe", "504", ("transcription_timeout",)),
        ("/process-document", "400", ("document_rejected", "unsupported_format")),
        ("/process-document", "413", ("payload_too_large",)),
        ("/process-document", "500", ("internal_error",)),
        ("/process-document", "503", ("dependency_missing", "server_busy")),
        ("/process-document", "504", ("processing_timeout",)),
    ],
)
def test_error_responses_publish_machine_readable_codes(
    path: str,
    status_code: str,
    codes: tuple[str, ...],
) -> None:
    response = OPENAPI["paths"][path]["post"]["responses"][status_code]
    schema = response["content"]["application/json"]["schema"]
    missing_codes = [code for code in codes if code not in response["description"]]

    expected_response: tuple[dict[str, str], list[str]] = (
        {"$ref": "#/components/schemas/ErrorResponse"},
        [],
    )
    assert (schema, missing_codes) == expected_response, (
        f"{path} {status_code} does not publish its error codes"
    )


@pytest.mark.parametrize("path", ["/transcribe", "/process-document"])
def test_busy_responses_publish_retry_after(path: str) -> None:
    headers = OPENAPI["paths"][path]["post"]["responses"]["503"]["headers"]

    retry_after_header = "Retry-After"
    assert retry_after_header in headers, f"{path} 503 lacks a Retry-After header"


def test_every_openapi_path_is_mentioned_in_api_docs() -> None:
    documentation = (ROOT / "docs" / "api.md").read_text(encoding="utf-8")
    missing_paths = [path for path in OPENAPI["paths"] if path not in documentation]

    expected_empty: list[str] = []
    assert missing_paths == expected_empty, "OpenAPI paths are missing from docs/api.md"
