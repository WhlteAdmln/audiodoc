# Copyright (c) 2026 Nikolai Zelensky
"""Small aiohttp client matching the Telegram bot upload contract."""

from pathlib import Path
from typing import cast

import aiohttp


async def upload_file(
    url: str,
    file_path: Path,
    api_key: str,
    *,
    max_characters: int | None = None,
) -> tuple[int, dict[str, object]]:
    """Upload a file using multipart field ``file`` and Bearer authentication.

    Args:
        url: Full endpoint URL, including its path.
        file_path: Local file to upload.
        api_key: API key for the target endpoint.
        max_characters: Optional document extraction limit.

    Returns:
        The HTTP status code and decoded JSON response object.
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    with file_path.open("rb") as file_handle:
        form = aiohttp.FormData()
        form.add_field("file", file_handle, filename=file_path.name)
        if max_characters is not None:
            form.add_field("max_characters", str(max_characters))

        async with (
            aiohttp.ClientSession() as session,
            session.post(url, data=form, headers=headers) as response,
        ):
            payload = await response.json()
            if not isinstance(payload, dict):
                raise TypeError
            return response.status, cast("dict[str, object]", payload)
