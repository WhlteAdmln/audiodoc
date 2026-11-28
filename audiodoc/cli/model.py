# Copyright (c) 2026 Nikolai Zelensky
"""The model command: manage Whisper models."""

import argparse
import importlib
import sys
from pathlib import Path

from audiodoc.env_readers import get_home_dir
from audiodoc.transcription.model_revisions import (
    MODEL_REVISIONS,
    InstalledModel,
    remove_revision_marker,
    write_revision_marker,
)


def handle_model_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Handle model management commands."""
    model_directory = args.directory or (get_home_dir() / "models" / args.name)
    try:
        model_path = _download_model(args.name, model_directory)
    except ImportError as error:
        parser.error(f"Could not import faster-whisper: {error}")
    sys.stdout.write(f"Model downloaded to: {model_path}\n")
    return 0


def _download_model(name: str, directory: Path) -> Path:
    """Download a supported Whisper model at its pinned revision."""
    directory.mkdir(parents=True, exist_ok=True)
    remove_revision_marker(directory)
    download_model = importlib.import_module("faster_whisper.utils").download_model
    revision = MODEL_REVISIONS[name]
    downloaded_path = download_model(name, output_dir=str(directory), revision=revision)
    write_revision_marker(directory, InstalledModel(name, revision))
    return Path(downloaded_path)
