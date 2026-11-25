# Copyright (c) 2026 Nikolai Zelensky

"""Tests for API key authentication."""

import asyncio
import re

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from audiodoc.api.auth import check_security_settings, require_key
from audiodoc.config import Settings, settings
from audiodoc.main import create_app

AUDIO_KEY = "audio-K3y_~-2026"
DOCUMENT_KEY = "doc-9f!Q-key=="
NOTE = {"file": ("note.txt", b"short test", "text/plain")}
VOICE = {"file": ("voice.ogg", b"fake audio", "audio/ogg")}


def _check(
    authorization: str | None, expected_keys: str = "expected-secret"
) -> int | None:
    dependency = require_key(lambda configured: configured.AUDIODOC_AUDIO_KEY)
    application = FastAPI()
    application.state.settings = Settings(AUDIODOC_AUDIO_KEY=expected_keys)
    request = Request({"type": "http", "app": application})
    try:
        asyncio.run(dependency(request, authorization))
    except HTTPException as error:
        return error.status_code
    return None


def _security_error(audio: str, document: str, *, allow: bool = False) -> str:
    configured = Settings(
        AUDIODOC_AUDIO_KEY=audio,
        AUDIODOC_DOCUMENT_KEY=document,
        ALLOW_UNAUTHENTICATED=allow,
    )
    try:
        check_security_settings(configured)
    except RuntimeError as error:
        return str(error)
    return ""


@pytest.fixture(name="client")
def fixture_client() -> TestClient:
    """Create a client for an application with separate audio and document keys."""
    return TestClient(
        create_app(
            Settings(AUDIODOC_DOCUMENT_KEY=DOCUMENT_KEY, AUDIODOC_AUDIO_KEY=AUDIO_KEY)
        )
    )


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "",
        "Bearer",
        "Bearer ",
        "Bearer wrong-secret",
        "Basic expected-secret",
        "expected-secret",
        "Bearerexpected-secret",
        "Bearer expected-secre",
        "Bearer expected-secret-and-more",
        "Bearer EXPECTED-SECRET",
        "Bearer expected-secret\x00",
        "Bearer expected\N{HYPHEN}secret",
        "Bearer секрет",
        "Bearer expected-secret, other",
        "Bearer " + "x" * 100_000,
    ],
    ids=[
        "missing",
        "empty",
        "scheme-only",
        "empty-token",
        "wrong",
        "basic",
        "no-scheme",
        "no-space",
        "prefix",
        "suffix",
        "upper-case",
        "nul",
        "unicode-hyphen",
        "cyrillic",
        "list",
        "huge",
    ],
)
def test_rejects_missing_or_wrong_credentials(authorization: str | None) -> None:
    status = _check(authorization)

    expected_status = 401
    assert status == expected_status, "a bad credential was accepted"


def test_asks_for_bearer_credentials_on_rejection() -> None:
    dependency = require_key(lambda configured: configured.AUDIODOC_AUDIO_KEY)
    application = FastAPI()
    application.state.settings = Settings(AUDIODOC_AUDIO_KEY="expected-secret")
    request = Request({"type": "http", "app": application})

    with pytest.raises(HTTPException) as caught:
        asyncio.run(dependency(request, "Bearer nope"))

    expected_headers = {"WWW-Authenticate": "Bearer"}
    assert caught.value.headers == expected_headers, "no Bearer challenge was sent"


@pytest.mark.parametrize(
    "authorization",
    ["Bearer expected-secret", "bearer expected-secret", "BEARER  expected-secret "],
)
def test_accepts_the_key_with_any_scheme_case(authorization: str) -> None:
    status = _check(authorization)

    assert status is None, "a valid credential was rejected"


@pytest.mark.parametrize("token", ["new-secret", "old-secret"])
def test_accepts_every_rotation_key(token: str) -> None:
    status = _check(f"Bearer {token}", " new-secret , old-secret ,")

    assert status is None, "a rotation key was rejected"


def test_skips_the_check_when_no_key_is_configured() -> None:
    status = _check(None, "")

    assert status is None, "an unconfigured key blocked the request"


def test_reads_process_settings_without_app_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "AUDIODOC_AUDIO_KEY", "process-wide-secret")
    dependency = require_key(lambda configured: configured.AUDIODOC_AUDIO_KEY)
    request = Request({"type": "http", "app": FastAPI()})

    with pytest.raises(HTTPException) as caught:
        asyncio.run(dependency(request, "Bearer anything-else"))

    expected_status = 401
    assert caught.value.status_code == expected_status, "process settings ignored"


@pytest.mark.parametrize(
    ("audio", "document", "missing"),
    [
        ("", "document-secret", "AUDIODOC_AUDIO_KEY"),
        ("audio-secret", "   ", "AUDIODOC_DOCUMENT_KEY"),
        (", ,", "document-secret", "AUDIODOC_AUDIO_KEY"),
        ("", ",", "AUDIODOC_AUDIO_KEY, AUDIODOC_DOCUMENT_KEY"),
    ],
    ids=["audio-empty", "document-blank", "commas-only", "both"],
)
def test_fails_closed_when_keys_are_missing(
    audio: str, document: str, missing: str
) -> None:
    message = _security_error(audio, document)

    assert message.startswith(f"Missing API keys: {missing}."), "missing keys passed"


def test_allows_missing_keys_only_when_explicitly_enabled() -> None:
    message = _security_error("", "", allow=True)

    expected_message = ""
    assert message == expected_message, "the explicit opt-out was ignored"


@pytest.mark.parametrize(
    ("audio", "document", "allow"),
    [
        ("shared-secret", "shared-secret", False),
        ("new-secret, shared-secret", "shared-secret, old-secret", False),
        ("  padded-secret ", "padded-secret", False),
        ("shared-secret", "shared-secret", True),
    ],
    ids=["same", "rotation-overlap", "whitespace", "opt-out"],
)
def test_fails_closed_when_apis_share_a_key(
    audio: str, document: str, *, allow: bool
) -> None:
    message = _security_error(audio, document, allow=allow)

    expected_message = (
        "AUDIODOC_AUDIO_KEY and AUDIODOC_DOCUMENT_KEY must not share any key values."
    )
    assert message == expected_message, "a shared key was accepted"


@pytest.mark.parametrize(
    ("audio", "document", "names"),
    [
        ("ключ-42", "document-7Hq", "AUDIODOC_AUDIO_KEY"),
        ("audio-x9Z", "old-ascii-1, café-new", "AUDIODOC_DOCUMENT_KEY"),
        ("Schlüssel", "鍵-2026", "AUDIODOC_AUDIO_KEY, AUDIODOC_DOCUMENT_KEY"),
    ],
    ids=["audio", "document-rotation", "both"],
)
def test_rejects_keys_with_non_ascii_characters(
    audio: str, document: str, names: str
) -> None:
    message = _security_error(audio, document)

    expected_message = (
        f"API keys must contain only ASCII characters: {names}. "
        "Replace them with keys made of ASCII characters only."
    )
    assert message == expected_message, "a non-ASCII key passed startup"


def test_does_not_reveal_non_ascii_keys_in_the_error() -> None:
    message = _security_error("pässword-81", "document-Wq4")

    assert re.search("pässword-81", message) is None, "a key leaked into the error"


def test_does_not_reveal_keys_in_the_error() -> None:
    message = _security_error("", "shared-ab12, shared-ab12")

    assert re.search("shared-ab12", message) is None, "a key leaked into the error"


@pytest.mark.parametrize(
    ("path", "files", "token"),
    [
        ("/process-document", NOTE, None),
        ("/process-document", NOTE, "wrong"),
        ("/process-document", NOTE, AUDIO_KEY),
        ("/transcribe", VOICE, None),
        ("/transcribe", VOICE, DOCUMENT_KEY),
        ("/transcribe", VOICE, f"{AUDIO_KEY},{DOCUMENT_KEY}"),
    ],
    ids=[
        "document-missing",
        "document-wrong",
        "document-with-audio-key",
        "audio-missing",
        "audio-with-document-key",
        "audio-key-list",
    ],
)
def test_route_rejects_a_key_of_another_api(
    client: TestClient,
    path: str,
    files: dict[str, tuple[str, bytes, str]],
    token: str | None,
) -> None:
    headers = {} if token is None else {"Authorization": f"Bearer {token}"}

    response = client.post(path, files=files, headers=headers)

    expected_status = 401
    assert response.status_code == expected_status, "a foreign key was accepted"


def test_document_route_accepts_its_own_key(client: TestClient) -> None:
    response = client.post(
        "/process-document",
        files=NOTE,
        headers={"Authorization": f"Bearer {DOCUMENT_KEY}"},
    )

    expected_status = 200
    assert response.status_code == expected_status, "the document key was rejected"


@pytest.mark.parametrize(
    ("index", "path", "token", "files"),
    [
        (0, "/process-document", "document-two", NOTE),
        (1, "/process-document", "document-one", NOTE),
        (0, "/transcribe", "whisper-two", VOICE),
        (1, "/transcribe", "whisper-one", VOICE),
    ],
)
def test_keys_are_scoped_to_their_own_application(
    index: int, path: str, token: str, files: dict[str, tuple[str, bytes, str]]
) -> None:
    applications = [
        create_app(
            Settings(
                AUDIODOC_DOCUMENT_KEY="document-one", AUDIODOC_AUDIO_KEY="whisper-one"
            )
        ),
        create_app(
            Settings(
                AUDIODOC_DOCUMENT_KEY="document-two", AUDIODOC_AUDIO_KEY="whisper-two"
            )
        ),
    ]

    response = TestClient(applications[index]).post(
        path, files=files, headers={"Authorization": f"Bearer {token}"}
    )

    expected_status = 401
    assert response.status_code == expected_status, "a key crossed applications"
