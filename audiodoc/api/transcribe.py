# Copyright (c) 2026 Nikolai Zelensky
"""Whisper transcription endpoint."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from audiodoc.api.auth import require_key
from audiodoc.api.dependencies import get_model_holder, get_transcription_queue
from audiodoc.api.schemas import ErrorResponse, TranscribeResponse
from audiodoc.common.limited_upload import save_upload_limited
from audiodoc.common.work_queue import WorkQueue
from audiodoc.config import settings
from audiodoc.errors.base import BackendError
from audiodoc.transcription.model import ModelHolder
from audiodoc.transcription.service import transcribe_file
from audiodoc.transcription.temp_files import temp_audio_file

logger = logging.getLogger(__name__)

router = APIRouter(
    dependencies=[
        Depends(
            require_key(
                lambda configured_settings: configured_settings.AUDIODOC_AUDIO_KEY
            )
        )
    ]
)


@router.post(
    "/transcribe",
    response_model=TranscribeResponse,
    description=(
        "Save an audio upload and return its Whisper transcription.\n\n"
        "Args:\n"
        "    file: Multipart audio file from the client.\n\n"
        "Returns:\n"
        "    The recognized text, detected language, and audio duration.\n\n"
        "Raises:\n"
        "    HTTPException: For missing model, invalid duration, oversized audio, or\n"
        "        an internal transcription failure."
    ),
    responses={
        400: {
            "model": ErrorResponse,
            "description": (
                "Audio is unreadable (invalid_audio) or exceeds the duration "
                "limit (audio_too_long)."
            ),
        },
        500: {
            "model": ErrorResponse,
            "description": "Unexpected internal failure (internal_error).",
        },
        503: {
            "model": ErrorResponse,
            "description": (
                "The model is not ready (model_not_ready), or the work queue "
                "is full (server_busy)."
            ),
            "headers": {
                "Retry-After": {
                    "description": "Seconds to wait before retrying.",
                    "schema": {"type": "string"},
                }
            },
        },
        504: {
            "model": ErrorResponse,
            "description": "Transcription timed out (transcription_timeout).",
        },
    },
)
async def transcribe(
    file: Annotated[UploadFile, File()],
    configured_model_holder: Annotated[ModelHolder, Depends(get_model_holder)],
    queue: Annotated[WorkQueue, Depends(get_transcription_queue)],
) -> dict[str, object]:
    """Save an audio upload and return its Whisper transcription.

    Args:
        file: Multipart audio file from the client.
        configured_model_holder: Application-owned Whisper model holder.
        queue: Application-owned transcription work queue.

    Returns:
        The recognized text, detected language, and audio duration.

    Raises:
        HTTPException: For missing model, invalid duration, oversized audio, or
            an internal transcription failure.

    """
    if not configured_model_holder.is_loaded:
        raise HTTPException(status_code=503, detail="Whisper model is not loaded")

    try:
        # Admission happens before the upload is copied to private storage.
        async with queue.slot():
            with temp_audio_file(file.filename or "audio") as file_path:
                await save_upload_limited(file, file_path, settings.MAX_AUDIO_SIZE)
                return await transcribe_file(
                    file_path,
                    queue=queue,
                    _slot_acquired=True,
                    configured_model_holder=configured_model_holder,
                )

    except BackendError:
        raise
    except HTTPException:
        raise
    except Exception:
        logger.exception("Audio transcription failed")
        raise HTTPException(status_code=500, detail="Transcription failed") from None
    finally:
        await file.close()
