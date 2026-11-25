# Copyright (c) 2026 Nikolai Zelensky

"""Tests for API response schemas."""

from audiodoc.api.schemas import DocumentResponse, TranscribeResponse


def test_document_response_keeps_the_bot_contract_field_names() -> None:
    document_text = "Ёжик в тумане №7"
    document = DocumentResponse(
        format="txt",
        text=document_text,
        characters=16,
    )
    expected_fields = {
        "format": "txt",
        "text": document_text,
        "characters": 16,
        "truncated": False,
    }

    assert document.model_dump() == expected_fields, "document fields changed"


def test_transcribe_response_keeps_the_bot_contract_field_names() -> None:
    spoken_text = "Bonjour, ça va?"
    transcription = TranscribeResponse(
        text=spoken_text,
        language="en",
        duration=1.25,
    )
    expected_fields = {
        "text": spoken_text,
        "language": "en",
        "duration": 1.25,
    }

    assert transcription.model_dump() == expected_fields, "transcription fields changed"
