# Copyright (c) 2026 Nikolai Zelensky
"""The init command: create a protected .env file."""

import argparse
import os
import secrets
import sys
import tempfile
from pathlib import Path

from audiodoc.doctor import CUDA_DEVICE
from audiodoc.env_readers import get_home_dir


def handle_init_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Handle the init command."""
    compute_type = args.compute_type or (
        "float16" if args.device == CUDA_DEVICE else "int8"
    )
    try:
        env_path = _write_initial_env(
            model=args.model,
            device=args.device,
            compute_type=compute_type,
            host=args.host,
            port=args.port,
            force=args.force,
        )
    except FileExistsError:
        parser.error("Configuration already exists. Use --force to overwrite.")
    sys.stdout.write(f"Created configuration: {env_path}\n")
    return 0


def _publish_env_file(
    descriptor: int,
    content: str,
    temporary_path: Path,
    env_path: Path,
    *,
    force: bool,
) -> None:
    """Write the content to the temporary file and move it into place."""
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(content)
    temporary_path.chmod(0o600)
    if force:
        temporary_path.replace(env_path)
    else:
        os.link(temporary_path, env_path)


def _write_initial_env(
    *,
    model: str,
    device: str,
    compute_type: str,
    host: str,
    port: int,
    force: bool,
) -> Path:
    """Create a protected environment file with distinct API keys."""
    home = get_home_dir()
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    env_path = home / ".env"

    audio_key = secrets.token_urlsafe(32)
    document_key = secrets.token_urlsafe(32)
    while document_key == audio_key:
        document_key = secrets.token_urlsafe(32)

    content = (
        "\n".join(
            (
                "# audiodoc configuration",
                f"AUDIODOC_AUDIO_KEY={audio_key}",
                f"AUDIODOC_DOCUMENT_KEY={document_key}",
                "ALLOW_UNAUTHENTICATED=false",
                f"AUDIODOC_HOST={host}",
                f"AUDIODOC_PORT={port}",
                f"WHISPER_MODEL_SIZE={model}",
                f"WHISPER_DEVICE={device}",
                f"WHISPER_COMPUTE_TYPE={compute_type}",
                "WHISPER_OFFLINE=false",
            )
        )
        + "\n"
    )

    descriptor, temporary_name = tempfile.mkstemp(prefix=".env.", dir=home)
    temporary_path = Path(temporary_name)
    try:
        _publish_env_file(descriptor, content, temporary_path, env_path, force=force)
    finally:
        temporary_path.unlink(missing_ok=True)

    return env_path
