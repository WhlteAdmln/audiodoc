"""Unauthenticated liveness endpoint that reports Whisper model state."""

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
    return {
        "status": "ok",
        "model": settings.WHISPER_MODEL_SIZE,
        "loaded": model_holder.is_loaded,
    }
