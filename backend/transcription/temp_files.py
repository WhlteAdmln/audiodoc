"""Private temporary storage for uploaded audio."""

import os
import re
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from backend.config import settings
from backend.config.paths import PROJECT_ROOT

DEFAULT_TEMP_DIR = PROJECT_ROOT / "tmp"


def _resolve_temp_dir(value: str | None) -> Path:
    configured = (value or "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_TEMP_DIR


TEMP_DIR = _resolve_temp_dir(settings.TEMP_DIR)
STALE_AFTER_SECONDS = 3600


def ensure_temp_dir() -> Path:
    """Create the private audio temporary directory and enforce mode 0700.

    Returns:
        The configured private temporary directory.
    """
    TEMP_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Tighten permissions if the directory already existed with broader access.
    os.chmod(TEMP_DIR, 0o700)
    return TEMP_DIR


def cleanup_stale_files() -> None:
    """Remove audio files left behind by a prior abnormal process exit."""
    now = time.time()
    for item in ensure_temp_dir().iterdir():
        try:
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
