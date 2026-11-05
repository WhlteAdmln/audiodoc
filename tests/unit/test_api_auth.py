from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.api.auth import check_security_settings, require_key


def run_dependency(dependency, authorization=None):
    import asyncio

    return asyncio.run(dependency(authorization))


def test_require_key_rejects_missing_and_invalid_tokens():
    dependency = require_key(lambda: "expected-secret")
    with pytest.raises(HTTPException) as missing:
        run_dependency(dependency)
    assert missing.value.status_code == 401
    assert missing.value.headers["WWW-Authenticate"] == "Bearer"

    with pytest.raises(HTTPException) as invalid:
        run_dependency(dependency, "Bearer wrong-secret")
    assert invalid.value.status_code == 401


def test_require_key_accepts_valid_token_case_insensitive_scheme():
    dependency = require_key(lambda: "expected-secret")
    assert run_dependency(dependency, "bearer expected-secret") is None


def test_require_key_supports_two_comma_separated_rotation_keys():
    dependency = require_key(lambda: "new-secret, old-secret")
    assert run_dependency(dependency, "Bearer old-secret") is None


def test_missing_keys_fail_closed_by_default():
    settings = SimpleNamespace(
        WHISPER_API_KEY="",
        DOCUMENT_API_KEY="document-secret",
        ALLOW_UNAUTHENTICATED=False,
    )
    with pytest.raises(RuntimeError, match="WHISPER_API_KEY"):
        check_security_settings(settings)


def test_missing_keys_allowed_only_when_explicitly_enabled():
    settings = SimpleNamespace(
        WHISPER_API_KEY="",
        DOCUMENT_API_KEY="",
        ALLOW_UNAUTHENTICATED=True,
    )
    check_security_settings(settings)


def test_comma_only_key_value_is_treated_as_missing():
    settings = SimpleNamespace(
        WHISPER_API_KEY=", ,",
        DOCUMENT_API_KEY="document-secret",
        ALLOW_UNAUTHENTICATED=False,
    )
    with pytest.raises(RuntimeError, match="WHISPER_API_KEY"):
        check_security_settings(settings)


def test_document_route_requires_its_own_key(monkeypatch):
    pytest.importorskip("ebooklib")
    pytest.importorskip("striprtf")

    from fastapi.testclient import TestClient
    from backend.config import settings
    from backend.main import app

    monkeypatch.setattr(settings, "DOCUMENT_API_KEY", "document-test-key")
    monkeypatch.setattr(settings, "WHISPER_API_KEY", "whisper-test-key")
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
