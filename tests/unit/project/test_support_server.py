# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the live Uvicorn support fixture."""

import aiohttp
import pytest

from tests.support.server import LiveServer, fixture_live_server

__all__ = ["fixture_live_server"]


@pytest.mark.asyncio
async def test_live_server_starts_real_app_with_fake_model(
    live_server: LiveServer,
) -> None:
    async with (
        aiohttp.ClientSession() as session,
        session.get(f"{live_server.base_url}/health") as response,
    ):
        payload = await response.json()

    expected_status = 200
    assert response.status == expected_status
    assert payload["loaded"] is True
    assert live_server.temp_dir.is_dir()
