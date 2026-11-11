# Copyright (c) 2026 Nikolai Zelensky
"""Readiness diagnostics for native OCR and DJVU dependencies."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends

from audiodoc.api.dependencies import get_model_holder
from audiodoc.document_engine.diagnostics import check_native_tools
from audiodoc.transcription.model import ModelHolder

router = APIRouter()


@router.get("/ready")
async def ready(
    configured_model_holder: Annotated[ModelHolder, Depends(get_model_holder)],
) -> dict[str, object]:
    """Report whether optional document-processing dependencies are installed.

    Returns:
        Boolean Tesseract/DjVuLibre status, available Tesseract languages, and
        the current Whisper model state. This endpoint requires no API key.

    """
    native_tools = await asyncio.to_thread(check_native_tools)
    return {
        "tesseract": native_tools.tesseract is not None,
        "languages": list(native_tools.languages),
        "djvulibre": native_tools.djvulibre,
        "model_loaded": configured_model_holder.is_loaded,
    }
