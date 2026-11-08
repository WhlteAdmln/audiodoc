# Copyright (c) 2026 Nikolai Zelensky
"""Unauthenticated liveness endpoint that reports Whisper model state."""

from pathlib import Path

from fastapi import APIRouter

from backend.config import settings
from backend.transcription.model import model_holder

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, object]:
    """Return service liveness, configured model name, and load state.

    Returns:
        A JSON-compatible status object. This endpoint requires no API key.

    """
    configured_path = settings.WHISPER_MODEL_PATH
    model_name = (
        Path(configured_path).name if configured_path else settings.WHISPER_MODEL_SIZE
    )
    return {
        "status": "ok",
        "model": model_name,
        "loaded": model_holder.is_loaded,
    }
