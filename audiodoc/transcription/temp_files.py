# Copyright (c) 2026 Nikolai Zelensky
"""Private temporary storage for uploaded audio."""

import os
import re
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from audiodoc.config import settings
from audiodoc.env_readers import get_home_dir, resolve_home_path


def temp_dir() -> Path:
    """Return the private temporary audio directory from the current settings."""
    home = get_home_dir()
    configured = (settings.TEMP_DIR or "").strip()
    return resolve_home_path(configured, home) if configured else home / "tmp"


STALE_AFTER_SECONDS = 3600


def ensure_temp_dir() -> Path:
    """Create the private audio temporary directory and enforce mode 0700.

    Returns:
        The configured private temporary directory.

    """
    directory = temp_dir()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Tighten permissions if the directory already existed with broader access.
    directory.chmod(0o700)
    return directory


def _remove_if_stale(item: Path, now: float) -> None:
    """Remove a managed audio file that is older than the staleness limit."""
    # Only remove files created by temp_audio_file (UUID names). The
    # configured directory may contain unrelated operator-managed files.
    is_managed = bool(re.fullmatch(r"[0-9a-f]{32}", item.stem))
    if (
        not item.is_symlink()
        and item.is_file()
        and is_managed
        and now - item.stat().st_mtime > STALE_AFTER_SECONDS
    ):
        item.unlink(missing_ok=True)


def cleanup_stale_files() -> None:
    """Remove audio files left behind by a prior abnormal process exit."""
    now = time.time()
    for item in ensure_temp_dir().iterdir():
        try:
            _remove_if_stale(item, now)
        except OSError:
            # A concurrent cleanup or filesystem race should not prevent startup.
            continue


@contextmanager
def temp_audio_file(original_name: str) -> Iterator[Path]:
    """Yield a random private path and always remove it on context exit."""
    suffix = Path(str(original_name or "audio")).suffix[:10]
    if not suffix.isascii() or any(char in suffix for char in ("/", "\\", "\x00")):
        suffix = ""
    path = ensure_temp_dir() / f"{uuid.uuid4().hex}{suffix}"
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)
