# Copyright (c) 2026 Nikolai Zelensky

"""Tests for api transcribe."""

import time
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import Never

import pytest
from fastapi.testclient import TestClient

from audiodoc.api import ready as ready_module
from audiodoc.config import Settings, settings
from audiodoc.main import create_app
from audiodoc.transcription import model as model_module
from audiodoc.transcription import service as service_module
from audiodoc.transcription import temp_files
from audiodoc.transcription.model import ModelHolder
from tests.support.api_app import app_with_router, closed_queue
from tests.support.builders import create_wav


class _UnexpectedAudioWriteError(AssertionError):
    """Raised when a test unexpectedly writes an audio file."""

    def __init__(self) -> None:
        """Initialize the test assertion error."""
        super().__init__("audio must not be copied when the queue is full")


app = create_app(settings)


app.state.model_holder = ModelHolder(settings)


client = TestClient(app)


class _ModelBuildError(RuntimeError):
    """Raised when the fake model factory fails."""


class _UnexpectedSegmentIterationError(AssertionError):
    """Raised when the test consumes segments for overlong audio."""

    def __init__(self) -> None:
        """Initialize the test assertion error."""
        super().__init__("segments should not be consumed for overlong audio")


class FakeWhisperModel:
    def transcribe(self, audio: object, **_kwargs: object) -> object:
        assert audio.size > 0
        segments = [SimpleNamespace(text=" recognized speech ")]
        info = SimpleNamespace(language="ru", duration=1.5)
        return iter(segments), info


class TooLongWhisperModel:
    def transcribe(self, _audio: object, **_kwargs: object) -> object:
        def segments() -> object:
            raise _UnexpectedSegmentIterationError
            yield None

        info = SimpleNamespace(language="ru", duration=9999)
        return segments(), info


def test_transcription_queue_rejects_before_temp_file_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transcribe = import_module("audiodoc.api.transcribe")
    queue = closed_queue()

    def unexpected_write(*_args: object, **_kwargs: object) -> Never:
        raise _UnexpectedAudioWriteError

    configured_model_holder = ModelHolder()
    monkeypatch.setattr(configured_model_holder, "_model", object())
    monkeypatch.setattr(transcribe, "save_upload_limited", unexpected_write)

    response = TestClient(
        app_with_router(
            transcribe.router,
            model_holder=configured_model_holder,
            transcription_queue=queue,
        )
    ).post(
        "/transcribe",
        files={"file": ("voice.ogg", b"audio", "audio/ogg")},
    )
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "30"


def test_transcribe_response_shape_with_fake_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(app.state.model_holder, "_model", FakeWhisperModel())
    monkeypatch.setattr(temp_files, "TEMP_DIR", tmp_path)

    response = client.post(
        "/transcribe",
        files={"file": ("voice.wav", create_wav(), "audio/wav")},
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["text"], str)
    assert isinstance(body["language"], str)
    assert isinstance(body["duration"], (int, float))
    assert body["text"] == "recognized speech"
    assert list(tmp_path.iterdir()) == []


def test_transcribe_rejects_audio_over_configured_duration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(app.state.model_holder, "_model", TooLongWhisperModel())
    monkeypatch.setattr(temp_files, "TEMP_DIR", tmp_path)

    response = client.post(
        "/transcribe",
        files={"file": ("long.wav", create_wav(), "audio/wav")},
    )

    assert response.status_code == 400
    assert "слишком длинное" in response.json()["detail"].lower()
    assert list(tmp_path.iterdir()) == []


def test_transcribe_rejects_corrupt_audio_and_removes_temp_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(app.state.model_holder, "_model", FakeWhisperModel())
    monkeypatch.setattr(temp_files, "TEMP_DIR", tmp_path)

    response = client.post(
        "/transcribe",
        files={"file": ("corrupt.ogg", b"not an audio stream", "audio/ogg")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c "
        "\u043f\u0440\u043e\u0447\u0438\u0442\u0430\u0442\u044c "
        "\u0430\u0443\u0434\u0438\u043e\u0444\u0430\u0439\u043b"
    )
    assert list(tmp_path.iterdir()) == []


def test_transcribe_returns_gateway_timeout_for_slow_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class SlowWhisperModel:
        def transcribe(self, _audio: object, **_kwargs: object) -> object:
            time.sleep(0.2)
            return iter([]), SimpleNamespace(language="ru", duration=0.25)

    monkeypatch.setattr(app.state.model_holder, "_model", SlowWhisperModel())
    monkeypatch.setattr(service_module.settings, "WHISPER_TIMEOUT", 0.1)
    monkeypatch.setattr(temp_files, "TEMP_DIR", tmp_path)

    response = client.post(
        "/transcribe",
        files={"file": ("slow.wav", create_wav(), "audio/wav")},
    )

    assert response.status_code == 504
    assert response.json()["detail"] == "Превышено время обработки аудио"
    assert list(tmp_path.iterdir()) == []


def test_ready_reports_unloaded_model_after_model_load_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_build(_configured_settings: Settings) -> None:
        raise _ModelBuildError

    monkeypatch.setattr(app.state.model_holder, "_model", None)
    monkeypatch.setattr(model_module, "_build_model", fail_build)

    with pytest.raises(_ModelBuildError):
        app.state.model_holder.load()

    monkeypatch.setattr(settings, "AUDIODOC_DOCUMENT_KEY", "")
    monkeypatch.setattr(settings, "ALLOW_UNAUTHENTICATED", True)
    monkeypatch.setattr(
        ready_module,
        "check_native_tools",
        lambda: SimpleNamespace(
            tesseract=None,
            languages=(),
            djvulibre=False,
        ),
    )

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["model_loaded"] is False
