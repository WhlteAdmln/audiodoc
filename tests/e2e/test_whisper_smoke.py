# Copyright (c) 2026 Nikolai Zelensky
"""Slow end-to-end smoke test using the real Whisper model."""

import asyncio
import re
import shutil
from difflib import SequenceMatcher
from pathlib import Path

import pytest

from backend.common.work_queue import WorkQueue
from backend.config import settings
from backend.transcription.model import ModelHolder
from backend.transcription.service import transcribe_file


async def _generate_speech(executable: str, audio_path: Path) -> None:
    """Generate a short speech sample with eSpeak NG."""
    process = await asyncio.create_subprocess_exec(
        executable,
        "-v",
        "en-us",
        "-s",
        "135",
        "-w",
        str(audio_path),
        "Hello, this is an audio transcription test.",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise

    if process.returncode != 0:
        error_output = (stderr or b"").decode("utf-8", errors="replace")
        message = f"espeak-ng failed with status {process.returncode}: {error_output}"
        raise RuntimeError(message)


@pytest.mark.timeout(900)
def test_real_tiny_whisper_transcribes_generated_speech(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recognize a known word using the cached tiny model on CPU."""
    espeak_ng = shutil.which("espeak-ng")
    assert espeak_ng is not None, "Install the espeak-ng package to run this test."

    audio_path = tmp_path / "whisper-smoke.wav"
    asyncio.run(_generate_speech(espeak_ng, audio_path))

    monkeypatch.setattr(settings, "WHISPER_MODEL_SIZE", "tiny")
    monkeypatch.setattr(settings, "WHISPER_MODEL_PATH", "")
    monkeypatch.setattr(settings, "WHISPER_LANGUAGE", "en")
    monkeypatch.setattr(settings, "WHISPER_DEVICE", "cpu")
    monkeypatch.setattr(settings, "WHISPER_COMPUTE_TYPE", "int8")
    monkeypatch.setattr(settings, "WHISPER_CPU_THREADS", 2)
    monkeypatch.setattr(settings, "WHISPER_OFFLINE", True)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")

    configured_model_holder = ModelHolder(settings)
    configured_model_holder.load()
    transcription = asyncio.run(
        transcribe_file(
            audio_path,
            queue=WorkQueue(
                settings.MAX_CONCURRENT_TRANSCRIPTIONS,
                settings.MAX_WAITING_TRANSCRIPTIONS,
            ),
            configured_model_holder=configured_model_holder,
        )
    )
    recognized_words = re.findall(r"[a-z]+", transcription["text"].casefold())

    assert any(
        SequenceMatcher(None, "hello", word).ratio() >= 0.8 for word in recognized_words
    ), f"Expected to recognize 'hello', got: {transcription['text']!r}"
