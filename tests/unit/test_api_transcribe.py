# Copyright (c) 2026 Nikolai Zelensky
"""Unit test for the Whisper HTTP response with a fake model.

The real model is not loaded: TestClient is used without starting lifespan,
and the model object is replaced directly in the test.
"""

import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.api import ready as ready_module
from backend.config import Settings, settings
from backend.main import create_app
from backend.transcription import model as model_module
from backend.transcription import service as service_module
from backend.transcription import temp_files
from backend.transcription.model import ModelHolder
from tests.support.builders import create_wav

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
    def transcribe(self, audio, **kwargs):
        assert audio.size > 0
        segments = [SimpleNamespace(text=" recognized speech ")]
        info = SimpleNamespace(language="ru", duration=1.5)
        return iter(segments), info


def test_transcribe_response_shape_with_fake_model(monkeypatch, tmp_path):
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


class TooLongWhisperModel:
    def transcribe(self, audio, **kwargs):
        def segments():
            raise _UnexpectedSegmentIterationError
            yield None

        info = SimpleNamespace(language="ru", duration=9999)
        return segments(), info


def test_transcribe_rejects_audio_over_configured_duration(monkeypatch, tmp_path):
    monkeypatch.setattr(app.state.model_holder, "_model", TooLongWhisperModel())
    monkeypatch.setattr(temp_files, "TEMP_DIR", tmp_path)

    response = client.post(
        "/transcribe",
        files={"file": ("long.wav", create_wav(), "audio/wav")},
    )

    assert response.status_code == 400
    assert "слишком длинное" in response.json()["detail"].lower()
    assert list(tmp_path.iterdir()) == []


def test_transcribe_rejects_corrupt_audio_and_removes_temp_file(monkeypatch, tmp_path):
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


def test_transcribe_returns_gateway_timeout_for_slow_model(monkeypatch, tmp_path):
    class SlowWhisperModel:
        def transcribe(self, audio, **kwargs):
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


def test_ready_reports_unloaded_model_after_model_load_failure(monkeypatch):
    def fail_build(_configured_settings: Settings) -> None:
        raise _ModelBuildError

    monkeypatch.setattr(app.state.model_holder, "_model", None)
    monkeypatch.setattr(model_module, "_build_model", fail_build)

    with pytest.raises(_ModelBuildError):
        app.state.model_holder.load()

    monkeypatch.setattr(settings, "DOCUMENT_API_KEY", "")
    monkeypatch.setattr(settings, "ALLOW_UNAUTHENTICATED", True)
    monkeypatch.setattr(
        ready_module,
        "_available_tesseract_languages",
        lambda: (False, []),
    )
    monkeypatch.setattr(ready_module.shutil, "which", lambda _name: None)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["model_loaded"] is False
