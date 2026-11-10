# Copyright (c) 2026 Nikolai Zelensky
"""Heuristic for identifying text files from their leading bytes."""


def looks_like_text(data: bytes) -> bool:
    """Return True if the first 4096 bytes look like UTF-8 text."""
    sample = data[:4096]

    if b"\x00" in sample:
        return False

    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True
