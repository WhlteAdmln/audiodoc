# Copyright (c) 2026 Nikolai Zelensky

"""Tests for api transcribe."""

from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import Never

import httpx2
import pytest
from fastapi.testclient import TestClient

from audiodoc.common import deadline as deadline_module
from audiodoc.config import settings
from audiodoc.main import create_app
from audiodoc.transcription.model import ModelHolder
from tests.support.api_app import app_with_router, closed_queue
from tests.support.builders import create_wav
from tests.support.clock import FakeMonotonicClock
from tests.support.whisper import loaded_model_holder, overlong_model, speech_model

UNREADABLE_AUDIO = "Не удалось прочитать аудиофайл"
TIMEOUT_DETAIL = "Превышено время обработки аудио"


class _UnexpectedAudioWriteError(AssertionError):
    """Raised when a test unexpectedly writes an audio file."""

    def __init__(self) -> None:
        """Initialize the test assertion error."""
        super().__init__("audio must not be copied when the queue is full")


@pytest.fixture(name="audio_dir")
def fixture_audio_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Keep the temporary audio files of one test in its own directory."""
    directory = tmp_path / "audio"
    directory.mkdir()
    monkeypatch.setattr(settings, "TEMP_DIR", str(directory))
    return directory


def _post(
    model: object, filename: str, data: bytes, content_type: str = "audio/wav"
) -> httpx2.Response:
    application = create_app(settings)
    application.state.model_holder = loaded_model_holder(model)
    return TestClient(application).post(
        "/transcribe", files={"file": (filename, data, content_type)}
    )


def _slow_model(clock: FakeMonotonicClock) -> SimpleNamespace:
    def transcribe(_audio: object, **_kwargs: object) -> object:
        clock.advance(0.2)
        return iter([]), SimpleNamespace(language="ru", duration=0.25)

    return SimpleNamespace(transcribe=transcribe)


@pytest.fixture(name="slow_response")
def fixture_slow_response(
    monkeypatch: pytest.MonkeyPatch, audio_dir: Path
) -> httpx2.Response:
    """Post audio to a model that outlives the configured timeout."""
    clock = FakeMonotonicClock()
    monkeypatch.setattr(deadline_module, "time", clock)
    monkeypatch.setattr(settings, "WHISPER_TIMEOUT", 0.1)
    return _post(_slow_model(clock), f"{audio_dir.name}-slow.wav", create_wav())


@pytest.fixture(name="busy_response")
def fixture_busy_response(monkeypatch: pytest.MonkeyPatch) -> httpx2.Response:
    """Post audio to a router whose queue is closed and fail if it is copied."""
    transcribe = import_module("audiodoc.api.transcribe")

    def unexpected_write(*_args: object, **_kwargs: object) -> Never:
        raise _UnexpectedAudioWriteError

    monkeypatch.setattr(transcribe, "save_upload_limited", unexpected_write)
    application = app_with_router(
        transcribe.router,
        model_holder=loaded_model_holder(speech_model()),
        transcription_queue=closed_queue(),
    )
    return TestClient(application).post(
        "/transcribe", files={"file": ("voice.ogg", b"audio", "audio/ogg")}
    )


def _leftovers(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir())


@pytest.mark.usefixtures("audio_dir")
def test_returns_text_language_and_duration() -> None:
    response = _post(speech_model(), "voice.wav", create_wav())

    expected_body = {"text": "recognized speech", "language": "ru", "duration": 1.5}
    assert response.json() == expected_body, "wrong transcription response"


@pytest.mark.parametrize(
    "filename",
    [
        "voice.wav",
        "../../../escape.wav",
        "/etc/cron.d/job.wav",
        "голос.wav",
        "name\x00.wav",
        "a.wav;rm -rf ~",
        "",
    ],
    ids=["plain", "dot-dot", "absolute", "cyrillic", "nul", "shell", "empty"],
)
def test_removes_the_temporary_file_after_success(
    audio_dir: Path, filename: str
) -> None:
    _post(speech_model(), filename, create_wav())

    expected_empty: list[str] = []
    assert _leftovers(audio_dir) == expected_empty, "audio stayed on disk"


@pytest.mark.parametrize(
    "filename",
    ["../escape.wav", "../../escape.wav", "/../escape.wav", "..\\escape.wav"],
)
def test_never_writes_outside_the_temporary_directory(
    tmp_path: Path, audio_dir: Path, filename: str
) -> None:
    _post(speech_model(), filename, create_wav())

    outside = sorted(path.name for path in tmp_path.iterdir() if path != audio_dir)

    expected_empty: list[str] = []
    assert outside == expected_empty, "an upload escaped its directory"


@pytest.mark.usefixtures("audio_dir")
def test_rejects_audio_over_configured_duration() -> None:
    response = _post(overlong_model(), "long.wav", create_wav())

    expected_status = 400
    assert response.status_code == expected_status, "overlong audio was accepted"


@pytest.mark.usefixtures("audio_dir")
def test_explains_the_duration_limit() -> None:
    response = _post(overlong_model(), "long.wav", create_wav())

    duration_message = "слишком длинное"
    assert duration_message in response.json()["detail"].lower(), "wrong detail"


def test_removes_the_temporary_file_after_overlong_audio(audio_dir: Path) -> None:
    _post(overlong_model(), "long.wav", create_wav())

    expected_empty: list[str] = []
    assert _leftovers(audio_dir) == expected_empty, "overlong audio stayed on disk"


@pytest.mark.parametrize(
    ("filename", "data"),
    [
        ("corrupt.ogg", b"not an audio stream"),
        ("empty.wav", b""),
        ("fake.wav", b"RIFF\xff\xff\xff\xffWAVEfmt "),
        ("zip.ogg", b"PK\x03\x04" + b"\x00" * 64),
    ],
    ids=["text", "empty", "truncated-header", "zip"],
)
@pytest.mark.usefixtures("audio_dir")
def test_rejects_unreadable_audio(filename: str, data: bytes) -> None:
    response = _post(speech_model(), filename, data, "audio/ogg")

    expected_body = {"detail": UNREADABLE_AUDIO, "code": "invalid_audio"}
    assert response.json() == expected_body, "unreadable audio was not rejected"


def test_removes_the_temporary_file_after_unreadable_audio(audio_dir: Path) -> None:
    _post(speech_model(), "corrupt.ogg", b"not an audio stream", "audio/ogg")

    expected_empty: list[str] = []
    assert _leftovers(audio_dir) == expected_empty, "corrupt audio stayed on disk"


def test_rejects_audio_over_size_limit(
    audio_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "MAX_AUDIO_SIZE", 16)

    response = _post(speech_model(), f"{audio_dir.name}.wav", create_wav())

    expected_status = 413
    assert response.status_code == expected_status, "oversized audio was accepted"


def test_removes_the_partial_file_after_size_rejection(
    audio_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "MAX_AUDIO_SIZE", 16)
    _post(speech_model(), "big.wav", create_wav())

    expected_empty: list[str] = []
    assert _leftovers(audio_dir) == expected_empty, "a partial upload stayed on disk"


def test_answers_gateway_timeout_for_slow_model(slow_response: httpx2.Response) -> None:
    expected_body = {"detail": TIMEOUT_DETAIL, "code": "transcription_timeout"}
    assert slow_response.json() == expected_body, "a slow model was not cut off"


@pytest.mark.usefixtures("slow_response")
def test_removes_the_temporary_file_after_timeout(audio_dir: Path) -> None:
    expected_empty: list[str] = []
    assert _leftovers(audio_dir) == expected_empty, "timed-out audio stayed on disk"


def test_answers_service_unavailable_without_loaded_model() -> None:
    application = create_app(settings)
    application.state.model_holder = ModelHolder(settings)

    response = TestClient(application).post(
        "/transcribe", files={"file": ("voice.wav", create_wav(), "audio/wav")}
    )

    expected_status = 503
    assert response.status_code == expected_status, "an unloaded model answered"


def test_busy_queue_answers_service_unavailable(busy_response: httpx2.Response) -> None:
    expected_status = 503
    assert busy_response.status_code == expected_status, "a full queue copied audio"


def test_busy_queue_asks_client_to_retry_later(busy_response: httpx2.Response) -> None:
    expected_retry_after = "30"
    assert busy_response.headers.get("Retry-After") == expected_retry_after, (
        "no Retry-After on a busy queue"
    )
