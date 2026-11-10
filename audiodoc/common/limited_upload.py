# Copyright (c) 2026 Nikolai Zelensky
"""Bounded reads and writes for uploaded files."""

from pathlib import Path

from fastapi import HTTPException, UploadFile

from audiodoc.errors.messages import ERROR_MESSAGES

CHUNK_SIZE = 1024 * 1024


def _too_large(limit: int) -> HTTPException:
    return HTTPException(
        status_code=413,
        detail=ERROR_MESSAGES["upload_too_large"].format(limit=limit // (1024 * 1024)),
    )


async def read_upload_limited(file: UploadFile, limit: int) -> bytes:
    """Read an upload in chunks and never retain more than ``limit`` bytes."""
    data = bytearray()
    while chunk := await file.read(CHUNK_SIZE):
        if len(data) + len(chunk) > limit:
            raise _too_large(limit)
        data.extend(chunk)
    return bytes(data)


async def save_upload_limited(file: UploadFile, destination: Path, limit: int) -> int:
    """Save an upload in chunks and never write more than ``limit`` bytes."""
    total = 0
    with destination.open("wb") as output:
        while chunk := await file.read(CHUNK_SIZE):
            if total + len(chunk) > limit:
                raise _too_large(limit)
            output.write(chunk)
            total += len(chunk)
    return total
