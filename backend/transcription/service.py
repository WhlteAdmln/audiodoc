# Copyright (c) 2026 Nikolai Zelensky
"""Threaded Whisper execution with bounded admission and active concurrency."""

import asyncio
from pathlib import Path
from typing import Any, cast

import av
import numpy as np
from numpy.typing import NDArray

from backend.common.deadline import Deadline, DeadlineExceededError
from backend.common.work_queue import WorkQueue
from backend.config import settings
from backend.errors.messages import ERROR_MESSAGES
from backend.errors.transcription import (
    AudioTooLongError,
    InvalidAudioError,
    ModelNotReadyError,
    TranscriptionTimeoutError,
)
from backend.transcription.model import ModelHolder

SAMPLE_RATE = 16_000


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


def _decode_audio(path: Path, deadline: Deadline) -> NDArray[np.float32]:
    """Decode audio into mono float32 samples at 16 kHz."""
    deadline.check()
    chunks: list[NDArray[np.float32]] = []
    sample_count = 0
    maximum_samples = settings.MAX_AUDIO_DURATION * SAMPLE_RATE
    audio_stream = None

    try:
        with av.open(str(path), mode="r") as container:
            audio_stream = next(
                (stream for stream in container.streams if stream.type == "audio"),
                None,
            )

            if audio_stream is not None:
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

                sample_count = _collect_audio_frames(
                    resampler.resample(None),
                    chunks,
                    sample_count,
                    maximum_samples,
                    deadline,
                )
    except (av.error.FFmpegError, OSError, ValueError) as error:
        raise InvalidAudioError from error

    if audio_stream is None or not chunks:
        raise InvalidAudioError

    deadline.check()
    return cast("NDArray[np.float32]", np.concatenate(chunks))


def _transcribe_sync(
    path: Path,
    deadline: Deadline,
    configured_model_holder: ModelHolder,
) -> dict[str, Any]:
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
) -> dict[str, Any]:
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
        return await asyncio.shield(worker)
    except DeadlineExceededError as error:
        raise TranscriptionTimeoutError from error
    except asyncio.CancelledError:
        cleanup = asyncio.gather(worker, return_exceptions=True)
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                continue
        raise


async def transcribe_file(
    path: Path,
    *,
    configured_model_holder: ModelHolder,
    queue: WorkQueue,
    _slot_acquired: bool = False,
) -> dict[str, Any]:
    """Recognize audio outside the event loop using the bounded work queue.

    ``_slot_acquired`` is reserved for the HTTP layer, which admits the request
    before copying the uploaded file to private temporary storage.
    ``queue`` is owned by the application or direct caller.
    """
    if _slot_acquired:
        return await _run_transcription(path, configured_model_holder)

    async with queue.slot():
        return await _run_transcription(path, configured_model_holder)
