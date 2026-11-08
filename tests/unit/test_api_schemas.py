# Copyright (c) 2026 Nikolai Zelensky
from backend.api.schemas import DocumentResponse, TranscribeResponse


def test_response_schemas_keep_the_bot_contract_field_names():
    document = DocumentResponse(
        format="txt",
        text="hello",
        characters=5,
    )
    transcription = TranscribeResponse(
        text="hello",
        language="en",
        duration=1.25,
    )

    assert document.model_dump() == {
        "format": "txt",
        "text": "hello",
        "characters": 5,
        "truncated": False,
    }
    assert transcription.model_dump() == {
        "text": "hello",
        "language": "en",
        "duration": 1.25,
    }
