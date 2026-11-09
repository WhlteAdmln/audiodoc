# Copyright (c) 2026 Nikolai Zelensky
"""Unauthenticated liveness endpoint that reports Whisper model state."""

from pathlib import Path

from fastapi import APIRouter, Request

from backend.config import settings
from backend.transcription.model import ModelHolder, model_holder

router = APIRouter()


def _get_model_holder(request: Request) -> ModelHolder:
    """Return the loaded application model, falling back during migration."""
    configured_holder: ModelHolder | None = getattr(
        request.app.state, "model_holder", None
    )
    if configured_holder is not None:
        return configured_holder
    return model_holder


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    """Return service liveness, configured model name, and load state.

    Returns:
        A JSON-compatible status object. This endpoint requires no API key.

    """
    configured_settings = getattr(request.app.state, "settings", settings)
    configured_path = configured_settings.WHISPER_MODEL_PATH
    model_name = (
        Path(configured_path).name
        if configured_path
        else configured_settings.WHISPER_MODEL_SIZE
    )
    return {
        "status": "ok",
        "model": model_name,
        "loaded": _get_model_holder(request).is_loaded,
    }
