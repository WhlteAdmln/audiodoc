# Copyright (c) 2026 Nikolai Zelensky
"""Stable JSON response schemas shared with the Telegram bot."""

from typing import Literal

from pydantic import BaseModel

ErrorCode = Literal[
    "internal_error",
    "server_busy",
    "document_rejected",
    "unsupported_format",
    "payload_too_large",
    "processing_timeout",
    "dependency_missing",
    "invalid_audio",
    "audio_too_long",
    "model_not_ready",
    "transcription_timeout",
]


class ErrorResponse(BaseModel):
    """Machine-readable HTTP error response."""

    detail: str
    code: ErrorCode


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
