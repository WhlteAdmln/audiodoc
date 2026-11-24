# Copyright (c) 2026 Nikolai Zelensky

"""Tests for API key authentication."""

import asyncio
from collections.abc import Awaitable, Callable
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from audiodoc.api.auth import check_security_settings, require_key
from audiodoc.config import Settings, settings
from audiodoc.main import create_app


def _run_dependency(
    dependency: Callable[..., Awaitable[None]],
    authorization: str | None = None,
) -> None:
    application = FastAPI()
    application.state.settings = Settings(AUDIODOC_AUDIO_KEY="expected-secret")
    request = Request({"type": "http", "app": application})
    return asyncio.run(dependency(request, authorization))


def test_require_key_rejects_missing_and_invalid_tokens() -> None:
    dependency = require_key(lambda configured: configured.AUDIODOC_AUDIO_KEY)
    with pytest.raises(HTTPException) as missing:
        _run_dependency(dependency)
    expected_status_code = 401
    assert missing.value.status_code == expected_status_code
    expected_www_authenticate = "Bearer"
    assert missing.value.headers["WWW-Authenticate"] == expected_www_authenticate

    with pytest.raises(HTTPException) as invalid:
        _run_dependency(dependency, "Bearer wrong-secret")
    expected_status_code = 401
    assert invalid.value.status_code == expected_status_code


def test_require_key_accepts_valid_token_case_insensitive_scheme() -> None:
    dependency = require_key(lambda configured: configured.AUDIODOC_AUDIO_KEY)
    assert _run_dependency(dependency, "bearer expected-secret") is None


def test_require_key_supports_two_comma_separated_rotation_keys() -> None:
    dependency = require_key(lambda configured: configured.AUDIODOC_AUDIO_KEY)
    configured_settings = Settings(AUDIODOC_AUDIO_KEY="new-secret, old-secret")
    application = FastAPI()
    application.state.settings = configured_settings
    request = Request({"type": "http", "app": application})
    assert asyncio.run(dependency(request, "Bearer old-secret")) is None


def test_require_key_uses_process_settings_without_app_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "AUDIODOC_AUDIO_KEY", "expected-secret")
    dependency = require_key(lambda configured: configured.AUDIODOC_AUDIO_KEY)
    application = FastAPI()
    request = Request({"type": "http", "app": application})

    assert asyncio.run(dependency(request, "Bearer expected-secret")) is None


def test_missing_keys_fail_closed_by_default() -> None:
    configured_settings = SimpleNamespace(
        AUDIODOC_AUDIO_KEY="",
        AUDIODOC_DOCUMENT_KEY="document-secret",
        ALLOW_UNAUTHENTICATED=False,
    )
    with pytest.raises(
        RuntimeError,
        match=r"^Missing API keys: AUDIODOC_AUDIO_KEY\.",
    ):
        check_security_settings(configured_settings)


def test_missing_keys_are_allowed_only_when_explicitly_enabled() -> None:
    configured_settings = SimpleNamespace(
        AUDIODOC_AUDIO_KEY="",
        AUDIODOC_DOCUMENT_KEY="",
        ALLOW_UNAUTHENTICATED=True,
    )
    check_security_settings(configured_settings)


def test_comma_only_key_value_is_treated_as_missing() -> None:
    configured_settings = SimpleNamespace(
        AUDIODOC_AUDIO_KEY=", ,",
        AUDIODOC_DOCUMENT_KEY="document-secret",
        ALLOW_UNAUTHENTICATED=False,
    )
    with pytest.raises(
        RuntimeError,
        match=r"^Missing API keys: AUDIODOC_AUDIO_KEY\.",
    ):
        check_security_settings(configured_settings)


@pytest.mark.parametrize(
    ("whisper_key", "document_key"),
    [
        ("shared-secret", "shared-secret"),
        ("new-secret, shared-secret", "shared-secret, old-secret"),
    ],
)
def test_shared_api_keys_fail_closed(
    whisper_key: str,
    document_key: str,
) -> None:
    configured_settings = SimpleNamespace(
        AUDIODOC_AUDIO_KEY=whisper_key,
        AUDIODOC_DOCUMENT_KEY=document_key,
        ALLOW_UNAUTHENTICATED=False,
    )

    with pytest.raises(
        RuntimeError,
        match="must not share any key values",
    ):
        check_security_settings(configured_settings)


def test_document_route_requires_its_own_key() -> None:
    app = create_app(
        Settings(
            AUDIODOC_DOCUMENT_KEY="document-test-key",
            AUDIODOC_AUDIO_KEY="whisper-test-key",
        )
    )

    client = TestClient(app)
    files = {"file": ("note.txt", b"short test", "text/plain")}

    expected_missing_key_status = 401
    assert (
        client.post("/process-document", files=files).status_code
        == expected_missing_key_status
    )
    expected_wrong_key_status = 401
    assert (
        client.post(
            "/transcribe",
            files={"file": ("voice.ogg", b"fake audio", "audio/ogg")},
        ).status_code
        == expected_wrong_key_status
    )
    expected_audio_key_status = 401
    assert (
        client.post(
            "/process-document",
            files=files,
            headers={"Authorization": "Bearer wrong"},
        ).status_code
        == expected_audio_key_status
    )
    response = client.post(
        "/process-document",
        files=files,
        headers={"Authorization": "Bearer document-test-key"},
    )
    expected_document_key_status = 200
    assert response.status_code == expected_document_key_status


def test_api_keys_are_scoped_to_each_application_settings() -> None:
    first_app = create_app(
        Settings(
            AUDIODOC_DOCUMENT_KEY="document-one",
            AUDIODOC_AUDIO_KEY="whisper-one",
        )
    )
    second_app = create_app(
        Settings(
            AUDIODOC_DOCUMENT_KEY="document-two",
            AUDIODOC_AUDIO_KEY="whisper-two",
        )
    )

    attempts = (
        (first_app, "/process-document", "document-two", "note.txt", "text/plain"),
        (second_app, "/process-document", "document-one", "note.txt", "text/plain"),
        (first_app, "/transcribe", "whisper-two", "voice.ogg", "audio/ogg"),
        (second_app, "/transcribe", "whisper-one", "voice.ogg", "audio/ogg"),
    )

    for application, path, token, filename, content_type in attempts:
        response = TestClient(application).post(
            path,
            files={"file": (filename, b"test upload", content_type)},
            headers={"Authorization": f"Bearer {token}"},
        )
        expected_status_code = 401
        assert response.status_code == expected_status_code
