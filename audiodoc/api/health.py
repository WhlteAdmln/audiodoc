# Copyright (c) 2026 Nikolai Zelensky
"""Unauthenticated liveness endpoint that reports Whisper model state."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from audiodoc.api.dependencies import get_model_holder
from audiodoc.config import settings
from audiodoc.transcription.model import ModelHolder

router = APIRouter()


@router.get("/health")
async def health(
    request: Request,
    configured_model_holder: Annotated[ModelHolder, Depends(get_model_holder)],
) -> dict[str, object]:
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
        "loaded": configured_model_holder.is_loaded,
    }
