# Copyright (c) 2026 Nikolai Zelensky
"""Readiness diagnostics for native OCR and DJVU dependencies."""

import asyncio
import logging
import shutil

from fastapi import APIRouter

from backend.document_engine.ocr.tesseract import _get_pytesseract
from backend.transcription.model import model_holder

logger = logging.getLogger(__name__)
router = APIRouter()


def _available_tesseract_languages() -> tuple[bool, list[str]]:
    """Return the Tesseract executable state and installed language codes."""
    if shutil.which("tesseract") is None:
        return False, []

    try:
        pytesseract = _get_pytesseract()
    except ImportError:
        logger.warning("Unable to query Tesseract language data")
        return True, []

    try:
        return True, sorted(set(pytesseract.get_languages(config="")))
    except (OSError, pytesseract.TesseractError):
        # Keep the diagnostic endpoint safe and useful even when tessdata is broken.
        logger.warning("Unable to query Tesseract language data")
        return True, []


@router.get("/ready")
async def ready() -> dict[str, object]:
    """Report whether optional document-processing dependencies are installed.

    Returns:
        Boolean Tesseract/DjVuLibre status, available Tesseract languages, and
        the current Whisper model state. This endpoint requires no API key.

    """
    tesseract, languages = await asyncio.to_thread(_available_tesseract_languages)
    djvulibre = all(
        shutil.which(name) is not None for name in ("djvutxt", "djvused", "ddjvu")
    )
    return {
        "tesseract": tesseract,
        "languages": languages,
        "djvulibre": djvulibre,
        "model_loaded": model_holder.is_loaded,
    }
