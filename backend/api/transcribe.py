"""Whisper transcription endpoint."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.api.auth import require_key
from backend.api.schemas import TranscribeResponse
from backend.common.limited_upload import save_upload_limited
from backend.config import settings
from backend.errors.base import BackendError
from backend.transcription.model import model_holder
from backend.transcription.service import transcribe_file, transcription_queue
from backend.transcription.temp_files import temp_audio_file

logger = logging.getLogger(__name__)

router = APIRouter(
    dependencies=[Depends(require_key(lambda: settings.WHISPER_API_KEY))]
)


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(file: Annotated[UploadFile, File()]) -> dict[str, object]:
    """Save an audio upload and return its Whisper transcription.

    Args:
        file: Multipart audio file from the client.

    Returns:
        The recognized text, detected language, and audio duration.

    Raises:
        HTTPException: For missing model, invalid duration, oversized audio, or
            an internal transcription failure.
    """
    if not model_holder.is_loaded:
        raise HTTPException(status_code=503, detail="Whisper model is not loaded")

    try:
        # Admission happens before the upload is copied to private storage.
        async with transcription_queue.slot():
            with temp_audio_file(file.filename or "audio") as file_path:
                await save_upload_limited(file, file_path, settings.MAX_AUDIO_SIZE)
                return await transcribe_file(file_path, _slot_acquired=True)

    except BackendError:
        raise
    except HTTPException:
        raise
    except Exception:
        logger.exception("Audio transcription failed")
        raise HTTPException(status_code=500, detail="Transcription failed") from None
    finally:
        await file.close()
