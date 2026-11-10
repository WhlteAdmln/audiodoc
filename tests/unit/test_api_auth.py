# Copyright (c) 2026 Nikolai Zelensky
import asyncio
from collections.abc import Awaitable, Callable
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from audiodoc.api.auth import check_security_settings, require_key
from audiodoc.config import Settings, settings
from audiodoc.main import create_app


def run_dependency(
    dependency: Callable[..., Awaitable[None]],
    authorization: str | None = None,
) -> None:
    application = FastAPI()
    application.state.settings = Settings(WHISPER_API_KEY="expected-secret")
    request = Request({"type": "http", "app": application})
    return asyncio.run(dependency(request, authorization))


def test_require_key_rejects_missing_and_invalid_tokens():
    dependency = require_key(lambda configured: configured.WHISPER_API_KEY)
    with pytest.raises(HTTPException) as missing:
        run_dependency(dependency)
    assert missing.value.status_code == 401
    assert missing.value.headers["WWW-Authenticate"] == "Bearer"

    with pytest.raises(HTTPException) as invalid:
        run_dependency(dependency, "Bearer wrong-secret")
    assert invalid.value.status_code == 401


def test_require_key_accepts_valid_token_case_insensitive_scheme():
    dependency = require_key(lambda configured: configured.WHISPER_API_KEY)
    assert run_dependency(dependency, "bearer expected-secret") is None


def test_require_key_supports_two_comma_separated_rotation_keys():
    dependency = require_key(lambda configured: configured.WHISPER_API_KEY)
    configured_settings = Settings(WHISPER_API_KEY="new-secret, old-secret")
    application = FastAPI()
    application.state.settings = configured_settings
    request = Request({"type": "http", "app": application})
    assert asyncio.run(dependency(request, "Bearer old-secret")) is None


def test_require_key_uses_legacy_settings_without_app_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "WHISPER_API_KEY", "expected-secret")
    dependency = require_key(lambda configured: configured.WHISPER_API_KEY)
    application = FastAPI()
    request = Request({"type": "http", "app": application})

    assert asyncio.run(dependency(request, "Bearer expected-secret")) is None


def test_missing_keys_fail_closed_by_default():
    configured_settings = SimpleNamespace(
        WHISPER_API_KEY="",
        DOCUMENT_API_KEY="document-secret",
        ALLOW_UNAUTHENTICATED=False,
    )
    with pytest.raises(
        RuntimeError,
        match=r"^Missing API keys: AUDIODOC_AUDIO_KEY \(legacy: WHISPER_API_KEY\)",
    ):
        check_security_settings(configured_settings)


def test_missing_keys_allowed_only_when_explicitly_enabled():
    configured_settings = SimpleNamespace(
        WHISPER_API_KEY="",
        DOCUMENT_API_KEY="",
        ALLOW_UNAUTHENTICATED=True,
    )
    check_security_settings(configured_settings)


def test_comma_only_key_value_is_treated_as_missing():
    configured_settings = SimpleNamespace(
        WHISPER_API_KEY=", ,",
        DOCUMENT_API_KEY="document-secret",
        ALLOW_UNAUTHENTICATED=False,
    )
    with pytest.raises(
        RuntimeError,
        match=r"^Missing API keys: AUDIODOC_AUDIO_KEY \(legacy: WHISPER_API_KEY\)",
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
        WHISPER_API_KEY=whisper_key,
        DOCUMENT_API_KEY=document_key,
        ALLOW_UNAUTHENTICATED=False,
    )

    with pytest.raises(
        RuntimeError,
        match="must not share any key values",
    ):
        check_security_settings(configured_settings)


def test_document_route_requires_its_own_key():
    app = create_app(
        Settings(
            DOCUMENT_API_KEY="document-test-key",
            WHISPER_API_KEY="whisper-test-key",
        )
    )

    client = TestClient(app)
    files = {"file": ("note.txt", b"short test", "text/plain")}

    assert client.post("/process-document", files=files).status_code == 401
    assert (
        client.post(
            "/transcribe",
            files={"file": ("voice.ogg", b"fake audio", "audio/ogg")},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/process-document",
            files=files,
            headers={"Authorization": "Bearer wrong"},
        ).status_code
        == 401
    )
    response = client.post(
        "/process-document",
        files=files,
        headers={"Authorization": "Bearer document-test-key"},
    )
    assert response.status_code == 200


def test_api_keys_are_scoped_to_each_application_settings() -> None:
    first_app = create_app(
        Settings(
            DOCUMENT_API_KEY="document-one",
            WHISPER_API_KEY="whisper-one",
        )
    )
    second_app = create_app(
        Settings(
            DOCUMENT_API_KEY="document-two",
            WHISPER_API_KEY="whisper-two",
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
        assert response.status_code == 401
