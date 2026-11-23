# Copyright (c) 2026 Nikolai Zelensky
"""Threaded Whisper execution with bounded admission and active concurrency."""

import asyncio
from functools import partial
from pathlib import Path
from typing import TypedDict, cast

import av
import numpy as np
from numpy.typing import NDArray

from audiodoc.common.deadline import Deadline, DeadlineExceededError
from audiodoc.common.work_queue import WorkQueue, await_worker, run_in_slot
from audiodoc.config import settings
from audiodoc.errors.messages import ERROR_MESSAGES
from audiodoc.errors.transcription import (
    AudioTooLongError,
    InvalidAudioError,
    ModelNotReadyError,
    TranscriptionTimeoutError,
)
from audiodoc.transcription.model import ModelHolder

SAMPLE_RATE = 16_000
AUDIO_STREAM_TYPE = "audio"


class TranscriptionResult(TypedDict):
    """Recognized text, detected language and audio duration in seconds."""

    text: str
    language: str | None
    duration: float


def _collect_audio_frames(
    frames: list[av.AudioFrame],
    chunks: list[NDArray[np.float32]],
    sample_count: int,
    maximum_samples: int,
    deadline: Deadline,
) -> int:
    """Collect resampled frames while enforcing the duration limit."""
    for frame in frames:
        deadline.check()
        sample_count += frame.samples
        if sample_count > maximum_samples:
            message = ERROR_MESSAGES["audio_too_long_with_limit"].format(
                limit=settings.MAX_AUDIO_DURATION
            )
            raise AudioTooLongError(message)
        samples = np.asarray(
            frame.to_ndarray(),
            dtype=np.float32,
        ).reshape(-1)
        chunks.append(cast("NDArray[np.float32]", samples))
    return sample_count


def _decode_stream(
    path: Path, deadline: Deadline, chunks: list[NDArray[np.float32]]
) -> bool:
    """Decode the first audio stream into chunks; return whether one exists."""
    sample_count = 0
    maximum_samples = settings.MAX_AUDIO_DURATION * SAMPLE_RATE

    with av.open(str(path), mode="r") as container:
        audio_stream = next(
            (
                stream
                for stream in container.streams
                if stream.type == AUDIO_STREAM_TYPE
            ),
            None,
        )

        if audio_stream is None:
            return False

        resampler = av.AudioResampler(
            format="fltp",
            layout="mono",
            rate=SAMPLE_RATE,
        )

        for frame in container.decode(audio=audio_stream.index):
            deadline.check()
            sample_count = _collect_audio_frames(
                resampler.resample(frame),
                chunks,
                sample_count,
                maximum_samples,
                deadline,
            )

        _collect_audio_frames(
            resampler.resample(None),
            chunks,
            sample_count,
            maximum_samples,
            deadline,
        )
    return True


def _decode_audio(path: Path, deadline: Deadline) -> NDArray[np.float32]:
    """Decode audio into mono float32 samples at 16 kHz."""
    deadline.check()
    chunks: list[NDArray[np.float32]] = []

    try:
        has_audio_stream = _decode_stream(path, deadline, chunks)
    except (av.error.FFmpegError, OSError, ValueError) as error:
        raise InvalidAudioError from error

    if not has_audio_stream or not chunks:
        raise InvalidAudioError

    deadline.check()
    return cast("NDArray[np.float32]", np.concatenate(chunks))


def _transcribe_sync(
    path: Path,
    deadline: Deadline,
    configured_model_holder: ModelHolder,
) -> TranscriptionResult:
    try:
        model = configured_model_holder.get()
    except RuntimeError as error:
        raise ModelNotReadyError from error

    audio = _decode_audio(path, deadline)
    segments, info = model.transcribe(
        audio,
        language=settings.WHISPER_LANGUAGE,
        beam_size=settings.WHISPER_BEAM_SIZE,
        vad_filter=True,
    )

    deadline.check()
    duration = float(info.duration)
    if duration > settings.MAX_AUDIO_DURATION:
        message = ERROR_MESSAGES["audio_too_long_with_limit"].format(
            limit=settings.MAX_AUDIO_DURATION
        )
        raise AudioTooLongError(message)

    text_parts = []
    for segment in segments:
        deadline.check()
        text_parts.append(segment.text.strip())
    deadline.check()

    text = " ".join(text_parts).strip()
    return {"text": text, "language": info.language, "duration": duration}


async def _run_transcription(
    path: Path,
    configured_model_holder: ModelHolder,
) -> TranscriptionResult:
    """Run the non-cancellable model thread while retaining its worker slot."""
    deadline = Deadline(settings.WHISPER_TIMEOUT)
    worker = asyncio.create_task(
        asyncio.to_thread(
            _transcribe_sync,
            path,
            deadline,
            configured_model_holder,
        )
    )
    try:
        return await await_worker(worker)
    except DeadlineExceededError as error:
        raise TranscriptionTimeoutError from error


async def transcribe_file(
    path: Path,
    *,
    configured_model_holder: ModelHolder,
    queue: WorkQueue,
    _slot_acquired: bool = False,
) -> TranscriptionResult:
    """Recognize audio outside the event loop using the bounded work queue.

    ``_slot_acquired`` is reserved for the HTTP layer, which admits the request
    before copying the uploaded file to private temporary storage.
    ``queue`` is owned by the application or direct caller.
    """
    return await run_in_slot(
        queue,
        partial(_run_transcription, path, configured_model_holder),
        slot_acquired=_slot_acquired,
    )
