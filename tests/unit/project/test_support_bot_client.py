# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the bot-compatible aiohttp upload client."""

from pathlib import Path

import pytest

from tests.support.bot_client import upload_file
from tests.support.builders import create_wav
from tests.support.server import LiveServer, fixture_live_server

__all__ = ["fixture_live_server"]


@pytest.mark.asyncio
async def test_bot_client_uploads_document_with_document_key(
    live_server: LiveServer,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "note.txt"
    file_path.write_text("Bot-compatible document.\n", encoding="utf-8")

    status, payload = await upload_file(
        f"{live_server.base_url}/process-document",
        file_path,
        live_server.document_api_key,
        max_characters=11264,
    )

    expected_text = "Bot-compatible document."
    expected_response = (200, "txt", expected_text, len(expected_text), False)
    actual_response = (
        status,
        payload["format"],
        payload["text"],
        payload["characters"],
        payload["truncated"],
    )
    assert actual_response == expected_response, "the document upload failed"


@pytest.mark.asyncio
async def test_bot_client_uploads_audio_with_whisper_key(
    live_server: LiveServer,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "voice.wav"
    file_path.write_bytes(create_wav())

    status, payload = await upload_file(
        f"{live_server.base_url}/transcribe",
        file_path,
        live_server.whisper_api_key,
    )

    expected_response = (
        200,
        {"text": "Test transcription", "language": "ru", "duration": 1.0},
    )
    assert (status, payload) == expected_response, "the audio upload failed"
