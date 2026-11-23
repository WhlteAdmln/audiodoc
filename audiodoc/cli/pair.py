# Copyright (c) 2026 Nikolai Zelensky
"""The pair command: print the bot configuration settings."""

import argparse
import sys

from dotenv import dotenv_values

from audiodoc.cli.run import ALL_INTERFACES_HOST
from audiodoc.env_readers import get_home_dir
from audiodoc.system_diagnostics import IPV6_HOST_MARKER


def handle_pair_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Handle the pair command."""
    try:
        snippet = _build_pair_configuration(args.url)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    sys.stdout.write(snippet)
    return 0


def _build_pair_configuration(url: str | None) -> str:
    """Build the exact shared settings required by bot-obormot."""
    env_path = get_home_dir() / ".env"
    if not env_path.is_file():
        message = (
            f"Configuration file not found: {env_path}. Run 'audiodoc init' first."
        )
        raise FileNotFoundError(message)

    values = dotenv_values(env_path)
    audio_key = values.get("AUDIODOC_AUDIO_KEY")
    document_key = values.get("AUDIODOC_DOCUMENT_KEY")
    if not audio_key or not document_key:
        message = "Both API keys must be set in the audiodoc .env file."
        raise ValueError(message)

    base_url = url
    if base_url is None:
        host = values.get("AUDIODOC_HOST") or "127.0.0.1"
        port = values.get("AUDIODOC_PORT") or "8000"
        if host in {ALL_INTERFACES_HOST, "::"}:
            host = "127.0.0.1"
        elif IPV6_HOST_MARKER in host and not host.startswith("["):
            host = f"[{host}]"
        base_url = f"http://{host}:{port}"

    return (
        f"AUDIODOC_URL={base_url}\n"
        f"AUDIODOC_AUDIO_KEY={audio_key}\n"
        f"AUDIODOC_DOCUMENT_KEY={document_key}\n"
    )
