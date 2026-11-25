# Copyright (c) 2026 Nikolai Zelensky

"""Tests for API response schemas."""

from audiodoc.api.schemas import DocumentResponse, TranscribeResponse


def test_response_schemas_keep_the_bot_contract_field_names() -> None:
    document_text = "Ёжик в тумане №7"
    spoken_text = "Bonjour, ça va?"
    document = DocumentResponse(
        format="txt",
        text=document_text,
        characters=16,
    )
    transcription = TranscribeResponse(
        text=spoken_text,
        language="en",
        duration=1.25,
    )

    assert document.model_dump() == {
        "format": "txt",
        "text": document_text,
        "characters": 16,
        "truncated": False,
    }
    assert transcription.model_dump() == {
        "text": spoken_text,
        "language": "en",
        "duration": 1.25,
    }
