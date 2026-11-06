"""Интеграционная проверка HTTP-ответа Whisper с подставной моделью.

Настоящая модель не загружается: TestClient используется без запуска lifespan,
а объект модели подменяется непосредственно в тесте.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.integration

pytest.importorskip("ebooklib")
pytest.importorskip("striprtf")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend.transcription.model import model_holder  # noqa: E402

client = TestClient(app)


class FakeWhisperModel:
    def transcribe(self, file_path, **kwargs):
        assert Path(file_path).is_file()
        segments = [SimpleNamespace(text=" recognized speech ")]
        info = SimpleNamespace(language="ru", duration=1.5)
        return iter(segments), info


def test_transcribe_response_shape_with_fake_model(monkeypatch):
    monkeypatch.setattr(model_holder, "_model", FakeWhisperModel())

    response = client.post(
        "/transcribe",
        files={"file": ("voice.ogg", b"test audio bytes", "audio/ogg")},
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["text"], str)
    assert isinstance(body["language"], str)
    assert isinstance(body["duration"], (int, float))
    assert body["text"] == "recognized speech"


class TooLongWhisperModel:
    def transcribe(self, file_path, **kwargs):
        def segments():
            raise AssertionError("segments should not be consumed for overlong audio")
            yield None

        info = SimpleNamespace(language="ru", duration=9999)
        return segments(), info


def test_transcribe_rejects_audio_over_configured_duration(monkeypatch):
    monkeypatch.setattr(model_holder, "_model", TooLongWhisperModel())

    response = client.post(
        "/transcribe",
        files={"file": ("long.ogg", b"test audio bytes", "audio/ogg")},
    )

    assert response.status_code == 400
    assert "слишком длинное" in response.json()["detail"].lower()
