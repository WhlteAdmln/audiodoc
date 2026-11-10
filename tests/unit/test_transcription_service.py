# Copyright (c) 2026 Nikolai Zelensky
import asyncio
import threading
import time
import wave
from io import BytesIO
from types import SimpleNamespace
from typing import Any

import pytest

import backend.transcription.service as transcription_service
from backend.common.work_queue import WorkQueue
from backend.errors.transcription import (
    AudioTooLongError,
    InvalidAudioError,
    ModelNotReadyError,
    TranscriptionTimeoutError,
)
from backend.transcription.model import ModelHolder
from tests.support.builders import create_ocr_image, create_ogg_opus, create_wav


def _test_queue(max_waiting: int = 4) -> WorkQueue:
    return WorkQueue(workers=1, max_waiting=max_waiting)


def _loaded_model_holder(model: Any) -> ModelHolder:
    holder = ModelHolder()
    holder._model = model
    return holder


def _empty_wav() -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16_000)
    return output.getvalue()


def _wrong_codec_wav() -> bytes:
    payload = bytearray(create_wav())
    payload[20:22] = b"\xff\xff"
    return bytes(payload)


class _UnexpectedSegmentIterationError(AssertionError):
    """Raised when the test consumes segments for overlong audio."""

    def __init__(self) -> None:
        """Initialize the test assertion error."""
        super().__init__("segments must not be consumed")


class FakeModel:
    def __init__(self, duration=1.5):
        self.duration = duration
        self.thread_id = None

    def transcribe(self, path, **kwargs):
        self.thread_id = threading.get_ident()
        segments = [SimpleNamespace(text=" recognized text ")]
        return iter(segments), SimpleNamespace(language="ru", duration=self.duration)


def test_transcribe_file_runs_model_in_worker_thread(tmp_path):
    path = tmp_path / "audio.ogg"
    path.write_bytes(create_wav())
    model = FakeModel()
    configured_model_holder = _loaded_model_holder(model)
    main_thread_id = threading.get_ident()

    result = asyncio.run(
        transcription_service.transcribe_file(
            path,
            configured_model_holder=configured_model_holder,
            queue=_test_queue(),
        )
    )

    assert model.thread_id != main_thread_id
    assert result == {"text": "recognized text", "language": "ru", "duration": 1.5}


def test_transcribe_file_rejects_audio_over_duration_before_iterating_segments(
    tmp_path, monkeypatch
):
    path = tmp_path / "audio.ogg"
    path.write_bytes(create_wav())

    class TooLongModel:
        def transcribe(self, path, **kwargs):
            def segments():
                raise _UnexpectedSegmentIterationError
                yield None

            return segments(), SimpleNamespace(language="ru", duration=9999)

    configured_model_holder = _loaded_model_holder(TooLongModel())
    monkeypatch.setattr(transcription_service.settings, "MAX_AUDIO_DURATION", 600)

    with pytest.raises(AudioTooLongError) as error:
        asyncio.run(
            transcription_service.transcribe_file(
                path,
                configured_model_holder=configured_model_holder,
                queue=_test_queue(),
            )
        )

    assert error.value.public_message == (
        "Аудио слишком длинное. Максимальная длительность: 600 \u0441."
    )


def test_transcribe_file_reports_model_not_ready(tmp_path):
    path = tmp_path / "audio.ogg"
    path.write_bytes(b"audio")
    configured_model_holder = ModelHolder()

    with pytest.raises(ModelNotReadyError):
        asyncio.run(
            transcription_service.transcribe_file(
                path,
                configured_model_holder=configured_model_holder,
                queue=_test_queue(),
            )
        )


def test_transcribe_file_requires_model_holder(tmp_path):
    with pytest.raises(TypeError, match="configured_model_holder"):
        transcription_service.transcribe_file(
            tmp_path / "audio.ogg",
            queue=_test_queue(),
        )


@pytest.mark.parametrize(
    ("builder", "language", "beam_size"),
    [
        (create_wav, "en", 3),
        (create_ogg_opus, "ru", 7),
    ],
)
def test_transcribe_file_decodes_real_audio_and_passes_whisper_settings(
    builder, language, beam_size, tmp_path, monkeypatch
):
    path = tmp_path / "audio.data"
    path.write_bytes(builder())
    captured = {}

    class RecordingModel:
        def transcribe(self, audio, **kwargs):
            captured["audio"] = audio
            captured["kwargs"] = kwargs
            return iter([SimpleNamespace(text=" decoded audio ")]), SimpleNamespace(
                language=language,
                duration=0.25,
            )

    configured_model_holder = _loaded_model_holder(RecordingModel())
    monkeypatch.setattr(transcription_service.settings, "WHISPER_LANGUAGE", language)
    monkeypatch.setattr(
        transcription_service.settings,
        "WHISPER_BEAM_SIZE",
        beam_size,
    )

    result = asyncio.run(
        transcription_service.transcribe_file(
            path,
            configured_model_holder=configured_model_holder,
            queue=_test_queue(),
        )
    )

    assert captured["audio"].size > 0
    assert captured["audio"].ndim == 1
    assert str(captured["audio"].dtype) == "float32"
    assert captured["kwargs"] == {
        "language": language,
        "beam_size": beam_size,
        "vad_filter": True,
    }
    assert result["text"] == "decoded audio"
    assert result["language"] == language


@pytest.mark.parametrize(
    "audio_data",
    [
        pytest.param(b"", id="zero-length-file"),
        pytest.param(_empty_wav(), id="empty-wav"),
        pytest.param(b"not an audio container", id="corrupt-file"),
        pytest.param(_wrong_codec_wav(), id="wrong-codec"),
        pytest.param(create_ocr_image(), id="image-without-audio"),
    ],
)
def test_transcribe_file_rejects_invalid_audio(audio_data, tmp_path):
    path = tmp_path / "invalid.audio"
    path.write_bytes(audio_data)
    configured_model_holder = _loaded_model_holder(FakeModel())

    with pytest.raises(InvalidAudioError):
        asyncio.run(
            transcription_service.transcribe_file(
                path,
                configured_model_holder=configured_model_holder,
                queue=_test_queue(),
            )
        )


def test_transcribe_file_rejects_audio_over_decoded_duration(tmp_path, monkeypatch):
    path = tmp_path / "long.wav"
    path.write_bytes(create_wav())
    configured_model_holder = _loaded_model_holder(FakeModel())
    monkeypatch.setattr(transcription_service.settings, "MAX_AUDIO_DURATION", 0.1)

    with pytest.raises(AudioTooLongError) as error:
        asyncio.run(
            transcription_service.transcribe_file(
                path,
                configured_model_holder=configured_model_holder,
                queue=_test_queue(),
            )
        )

    assert error.value.public_message == (
        "Аудио слишком длинное. Максимальная длительность: 0.1 \u0441."
    )


def test_transcribe_file_reports_deadline_exceeded_for_slow_model(
    tmp_path, monkeypatch
):
    path = tmp_path / "slow.wav"
    path.write_bytes(create_wav())
    called = threading.Event()

    class SlowModel:
        def transcribe(self, audio, **kwargs):
            called.set()
            time.sleep(0.2)
            return iter([]), SimpleNamespace(language="ru", duration=0.25)

    configured_model_holder = _loaded_model_holder(SlowModel())
    monkeypatch.setattr(transcription_service.settings, "WHISPER_TIMEOUT", 0.1)

    with pytest.raises(TranscriptionTimeoutError):
        asyncio.run(
            transcription_service.transcribe_file(
                path,
                configured_model_holder=configured_model_holder,
                queue=_test_queue(),
            )
        )

    assert called.is_set()


def test_transcriptions_respect_the_concurrency_semaphore(tmp_path):
    queue = _test_queue(max_waiting=1)
    lock = threading.Lock()
    active = 0
    maximum_active = 0

    class CountingModel:
        def transcribe(self, path, **kwargs):
            nonlocal active, maximum_active
            with lock:
                active += 1
                maximum_active = max(maximum_active, active)
            time.sleep(0.04)
            with lock:
                active -= 1
            return iter([]), SimpleNamespace(language="ru", duration=1)

    configured_model_holder = _loaded_model_holder(CountingModel())
    paths = [tmp_path / "one.ogg", tmp_path / "two.ogg"]
    for path in paths:
        path.write_bytes(create_wav())

    async def run_both():
        await asyncio.gather(
            transcription_service.transcribe_file(
                paths[0],
                configured_model_holder=configured_model_holder,
                queue=queue,
            ),
            transcription_service.transcribe_file(
                paths[1],
                configured_model_holder=configured_model_holder,
                queue=queue,
            ),
        )

    asyncio.run(run_both())
    assert maximum_active == 1


def test_cancelled_transcription_waits_for_worker_even_when_cancelled_twice(
    tmp_path, monkeypatch
):
    path = tmp_path / "audio.wav"
    path.write_bytes(create_wav())
    started = threading.Event()
    release = threading.Event()

    class SlowModel:
        def transcribe(self, audio, **kwargs):
            started.set()
            release.wait(timeout=5)
            return [], SimpleNamespace(language="ru", duration=0.25)

    configured_model_holder = _loaded_model_holder(SlowModel())

    async def cancel_transcription():
        task = asyncio.create_task(
            transcription_service.transcribe_file(
                path,
                configured_model_holder=configured_model_holder,
                queue=_test_queue(),
            )
        )
        started_in_time = await asyncio.to_thread(started.wait, 2)
        task.cancel()
        await asyncio.sleep(0)
        waiting_after_cancel = not task.done()
        task.cancel()
        await asyncio.sleep(0)
        waiting_after_second_cancel = not task.done()
        release.set()

        with pytest.raises(asyncio.CancelledError):
            await task

        return (
            started_in_time,
            waiting_after_cancel,
            waiting_after_second_cancel,
        )

    assert asyncio.run(cancel_transcription()) == (True, True, True)
