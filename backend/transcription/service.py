"""Threaded Whisper execution with bounded admission and active concurrency."""

import asyncio
from pathlib import Path

from backend.common.work_queue import WorkQueue
from backend.config import settings
from backend.errors.base import ServerBusyError
from backend.errors.transcription import AudioTooLongError, ModelNotReadyError
from backend.transcription.model import model_holder

transcription_queue = WorkQueue(
    settings.MAX_CONCURRENT_TRANSCRIPTIONS,
    settings.MAX_WAITING_TRANSCRIPTIONS,
    error_factory=ServerBusyError,
)


def _transcribe_sync(path: Path) -> dict:
    try:
        model = model_holder.get()
    except RuntimeError as error:
        raise ModelNotReadyError() from error

    segments, info = model.transcribe(
        str(path),
        language=settings.WHISPER_LANGUAGE,
        beam_size=settings.WHISPER_BEAM_SIZE,
        vad_filter=True,
    )

    duration = float(info.duration)
    if duration > settings.MAX_AUDIO_DURATION:
        raise AudioTooLongError(
            f"Аудио слишком длинное. Максимальная длительность: {settings.MAX_AUDIO_DURATION} с."
        )

    text = " ".join(segment.text.strip() for segment in segments).strip()
    return {"text": text, "language": info.language, "duration": duration}


async def _run_transcription(path: Path) -> dict:
    """Run the non-cancellable model thread while retaining its worker slot."""
    worker = asyncio.create_task(asyncio.to_thread(_transcribe_sync, path))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        while not worker.done():
            try:
                await asyncio.shield(worker)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        raise


async def transcribe_file(
    path: Path,
    *,
    _slot_acquired: bool = False,
) -> dict:
    """Recognize audio outside the event loop using the bounded work queue.

    ``_slot_acquired`` is reserved for the HTTP layer, which admits the request
    before copying the uploaded file to private temporary storage.
    """
    if _slot_acquired:
        return await _run_transcription(path)

    async with transcription_queue.slot():
        return await _run_transcription(path)
