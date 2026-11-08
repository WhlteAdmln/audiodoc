# Copyright (c) 2026 Nikolai Zelensky
"""Stable JSON response schemas shared with the Telegram bot."""

from pydantic import BaseModel


class TranscribeResponse(BaseModel):
    """Successful speech transcription response."""

    text: str
    language: str
    duration: float


class DocumentResponse(BaseModel):
    """Successful document extraction response."""

    format: str
    text: str
    characters: int
    truncated: bool = False
