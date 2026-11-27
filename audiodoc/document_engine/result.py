# Copyright (c) 2026 Nikolai Zelensky
"""Build stable document responses and retain the extraction truncation flag."""

from dataclasses import dataclass
from typing import TypedDict

from audiodoc.common.text_budget import StopReason
from audiodoc.document_engine.limits import MAX_EXTRACTED_TEXT_LENGTH


@dataclass(frozen=True)
class ExtractionOutcome:
    """Text extracted from one document and the limit that stopped it."""

    format: str
    text: str
    stop_reason: StopReason


class DocumentResult(TypedDict):
    """Public document extraction response."""

    format: str
    text: str
    characters: int
    truncated: bool


def limit_text(text: str) -> str:
    """Keep a legacy final safety cap for text created outside TextBudget."""
    if len(text) > MAX_EXTRACTED_TEXT_LENGTH:
        return text[:MAX_EXTRACTED_TEXT_LENGTH]
    return text


def build_result(outcome: ExtractionOutcome) -> DocumentResult:
    """Create the public document result, including whether extraction was cut."""
    text = limit_text(outcome.text.strip())
    return {
        "format": outcome.format,
        "text": text,
        "characters": len(text),
        "truncated": outcome.stop_reason is not StopReason.NONE,
    }
