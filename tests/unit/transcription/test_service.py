# Copyright (c) 2026 Nikolai Zelensky

"""Tests for transcription service."""

import asyncio
import threading
import wave
from contextlib import closing
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

import audiodoc.transcription.service as transcription_service
from audiodoc.common import deadline as deadline_module
from audiodoc.common.work_queue import WorkQueue
from audiodoc.errors.transcription import (
    AudioTooLongError,
    InvalidAudioError,
    ModelNotReadyError,
    TranscriptionTimeoutError,
)
from audiodoc.transcription.model import ModelHolder
from tests.support.builders import create_ocr_image, create_ogg_opus, create_wav
from tests.support.clock import FakeMonotonicClock
from tests.support.whisper import FakeWhisperModel, loaded_model_holder


def _test_queue(max_waiting: int = 4) -> WorkQueue:
    return WorkQueue(workers=1, max_waiting=max_waiting)


def _empty_wav() -> bytes:
    output = BytesIO()
    with closing(wave.Wave_write(output)) as audio:
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


def test_transcribe_file_runs_model_in_worker_thread(tmp_path: Path) -> None:
    path = tmp_path / "audio.ogg"
    path.write_bytes(create_wav())
    model = FakeWhisperModel()
    configured_model_holder = loaded_model_holder(model)
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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "audio.ogg"
    path.write_bytes(create_wav())

    def transcribe(_path: object, **_kwargs: object) -> object:
        def segments() -> object:
            raise _UnexpectedSegmentIterationError
            yield None

        return segments(), SimpleNamespace(language="ru", duration=9999)

    too_long_model = SimpleNamespace(transcribe=transcribe)

    configured_model_holder = loaded_model_holder(too_long_model)
    monkeypatch.setattr(transcription_service.settings, "MAX_AUDIO_DURATION", 600)

    with pytest.raises(AudioTooLongError) as error:
        asyncio.run(
            transcription_service.transcribe_file(
                path,
                configured_model_holder=configured_model_holder,
                queue=_test_queue(),
            )
        )

    expected_public_message = (
        "Аудио слишком длинное. Максимальная длительность: 600 \u0441."
    )
    assert error.value.public_message == expected_public_message


def test_transcribe_file_reports_model_not_ready(tmp_path: Path) -> None:
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


def test_transcribe_file_requires_model_holder(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="configured_model_holder"):
        # pylint: disable-next=missing-kwoa  # the call omits it on purpose
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
    builder: object,
    language: object,
    beam_size: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "audio.data"
    path.write_bytes(builder())
    captured = {}

    def transcribe(audio: object, **kwargs: object) -> object:
        captured["audio"] = audio
        captured["kwargs"] = kwargs
        return iter([SimpleNamespace(text=" decoded audio ")]), SimpleNamespace(
            language=language,
            duration=0.25,
        )

    recording_model = SimpleNamespace(transcribe=transcribe)

    configured_model_holder = loaded_model_holder(recording_model)
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
    expected_dtype = "float32"
    assert str(captured["audio"].dtype) == expected_dtype
    assert captured["kwargs"] == {
        "language": language,
        "beam_size": beam_size,
        "vad_filter": True,
    }
    expected_text = "decoded audio"
    assert result["text"] == expected_text
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
def test_transcribe_file_rejects_invalid_audio(
    audio_data: object, tmp_path: Path
) -> None:
    path = tmp_path / "invalid.audio"
    path.write_bytes(audio_data)
    configured_model_holder = loaded_model_holder(FakeWhisperModel())

    with pytest.raises(InvalidAudioError):
        asyncio.run(
            transcription_service.transcribe_file(
                path,
                configured_model_holder=configured_model_holder,
                queue=_test_queue(),
            )
        )


def test_transcribe_file_rejects_audio_over_decoded_duration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "long.wav"
    path.write_bytes(create_wav())
    configured_model_holder = loaded_model_holder(FakeWhisperModel())
    monkeypatch.setattr(transcription_service.settings, "MAX_AUDIO_DURATION", 0.1)

    with pytest.raises(AudioTooLongError) as error:
        asyncio.run(
            transcription_service.transcribe_file(
                path,
                configured_model_holder=configured_model_holder,
                queue=_test_queue(),
            )
        )

    expected_public_message = (
        "Аудио слишком длинное. Максимальная длительность: 0.1 \u0441."
    )
    assert error.value.public_message == expected_public_message


def test_transcribe_file_reports_deadline_exceeded_for_slow_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "slow.wav"
    path.write_bytes(create_wav())
    called = threading.Event()
    clock = FakeMonotonicClock()

    def transcribe(_audio: object, **_kwargs: object) -> object:
        called.set()
        clock.advance(0.2)
        return iter([]), SimpleNamespace(language="ru", duration=0.25)

    slow_model = SimpleNamespace(transcribe=transcribe)

    configured_model_holder = loaded_model_holder(slow_model)
    monkeypatch.setattr(transcription_service.settings, "WHISPER_TIMEOUT", 0.1)
    monkeypatch.setattr(deadline_module, "time", clock)

    with pytest.raises(TranscriptionTimeoutError):
        asyncio.run(
            transcription_service.transcribe_file(
                path,
                configured_model_holder=configured_model_holder,
                queue=_test_queue(),
            )
        )

    assert called.is_set()


def test_transcriptions_respect_the_concurrency_semaphore(tmp_path: Path) -> None:
    queue = _test_queue(max_waiting=1)
    started = threading.Event()
    release = threading.Event()
    calls: list[str] = []

    def transcribe(_path: object, **_kwargs: object) -> object:
        calls.append("started")
        started.set()
        release.wait(timeout=5)
        return iter([]), SimpleNamespace(language="ru", duration=1)

    blocking_model = SimpleNamespace(transcribe=transcribe)

    configured_model_holder = loaded_model_holder(blocking_model)
    paths = [tmp_path / "one.ogg", tmp_path / "two.ogg"]
    for path in paths:
        path.write_bytes(create_wav())

    async def run_both() -> int:
        tasks = [
            asyncio.create_task(
                transcription_service.transcribe_file(
                    path,
                    configured_model_holder=configured_model_holder,
                    queue=queue,
                )
            )
            for path in paths
        ]
        await asyncio.to_thread(started.wait, 5)
        for _ in tasks:
            await asyncio.sleep(0)
        waiting_while_first_runs = queue.waiting
        release.set()
        await asyncio.gather(*tasks)
        return waiting_while_first_runs

    waiting_while_first_runs = asyncio.run(run_both())
    expected_waiting = 1
    assert waiting_while_first_runs == expected_waiting, (
        "the second transcription must wait for the first one's slot"
    )


def test_cancelled_transcription_waits_for_worker_even_when_cancelled_twice(
    tmp_path: Path,
) -> None:
    path = tmp_path / "audio.wav"
    path.write_bytes(create_wav())
    started = threading.Event()
    release = threading.Event()

    def transcribe(_audio: object, **_kwargs: object) -> object:
        started.set()
        release.wait(timeout=5)
        return [], SimpleNamespace(language="ru", duration=0.25)

    slow_model = SimpleNamespace(transcribe=transcribe)

    configured_model_holder = loaded_model_holder(slow_model)

    async def cancel_transcription() -> object:
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
