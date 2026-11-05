import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

import backend.transcription.service as transcription_service
from backend.common.work_queue import WorkQueue
from backend.errors.transcription import AudioTooLongError, ModelNotReadyError
from backend.transcription.model import model_holder


class FakeModel:
    def __init__(self, duration=1.5):
        self.duration = duration
        self.thread_id = None

    def transcribe(self, path, **kwargs):
        self.thread_id = threading.get_ident()
        segments = [SimpleNamespace(text=" recognized text ")]
        return iter(segments), SimpleNamespace(language="ru", duration=self.duration)


def test_transcribe_file_runs_model_in_worker_thread(tmp_path, monkeypatch):
    path = tmp_path / "audio.ogg"
    path.write_bytes(b"audio")
    model = FakeModel()
    monkeypatch.setattr(model_holder, "_model", model)
    main_thread_id = threading.get_ident()

    result = asyncio.run(transcription_service.transcribe_file(path))

    assert model.thread_id != main_thread_id
    assert result == {"text": "recognized text", "language": "ru", "duration": 1.5}


def test_transcribe_file_rejects_audio_over_duration_before_iterating_segments(
    tmp_path, monkeypatch
):
    path = tmp_path / "audio.ogg"
    path.write_bytes(b"audio")

    class TooLongModel:
        def transcribe(self, path, **kwargs):
            def segments():
                raise AssertionError("segments must not be consumed")
                yield None

            return segments(), SimpleNamespace(language="ru", duration=9999)

    monkeypatch.setattr(model_holder, "_model", TooLongModel())
    monkeypatch.setattr(transcription_service.settings, "MAX_AUDIO_DURATION", 600)

    with pytest.raises(AudioTooLongError):
        asyncio.run(transcription_service.transcribe_file(path))


def test_transcribe_file_reports_model_not_ready(tmp_path, monkeypatch):
    path = tmp_path / "audio.ogg"
    path.write_bytes(b"audio")
    monkeypatch.setattr(model_holder, "_model", None)

    with pytest.raises(ModelNotReadyError):
        asyncio.run(transcription_service.transcribe_file(path))


def test_transcriptions_respect_the_concurrency_semaphore(monkeypatch, tmp_path):
    import time

    monkeypatch.setattr(
        transcription_service,
        "transcription_queue",
        WorkQueue(1, 1),
    )
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

    monkeypatch.setattr(model_holder, "_model", CountingModel())
    paths = [tmp_path / "one.ogg", tmp_path / "two.ogg"]
    for path in paths:
        path.write_bytes(b"audio")

    async def run_both():
        await asyncio.gather(
            transcription_service.transcribe_file(paths[0]),
            transcription_service.transcribe_file(paths[1]),
        )

    asyncio.run(run_both())
    assert maximum_active == 1
