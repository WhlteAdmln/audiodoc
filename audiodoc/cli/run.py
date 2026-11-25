# Copyright (c) 2026 Nikolai Zelensky
"""The run command: start the API server."""

import argparse
import logging
import os
from pathlib import Path

import uvicorn

from audiodoc.cli.parser import parse_port
from audiodoc.config import ConfigError, load_env_file, load_settings
from audiodoc.logging_setup import configure_logging, split_secrets
from audiodoc.system_diagnostics import binds_all_interfaces

# The package name keeps the logger name the command had before the split.
logger = logging.getLogger(__package__)


def handle_run_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Handle the run command."""
    try:
        _run_server(args.host, args.port, args.env_file)
    except ConfigError as error:
        parser.error(str(error))
    return 0


def _run_server(host: str | None, port: int | None, env_file: Path | None) -> None:
    """Load configuration, configure logging, and start Uvicorn."""
    load_env_file(env_file)
    configured_settings = load_settings(os.environ)
    resolved_host = (
        host or os.environ.get("AUDIODOC_HOST", "127.0.0.1").strip()
    ) or "127.0.0.1"
    if port is None:
        try:
            resolved_port = parse_port(os.environ.get("AUDIODOC_PORT", "8000"))
        except argparse.ArgumentTypeError as error:
            raise ConfigError([f"Invalid AUDIODOC_PORT: {error}"]) from error
    else:
        resolved_port = port

    configured_secrets = split_secrets(
        configured_settings.AUDIODOC_AUDIO_KEY,
        configured_settings.AUDIODOC_DOCUMENT_KEY,
    )
    configure_logging(configured_settings.LOG_LEVEL, configured_secrets)

    if binds_all_interfaces(resolved_host):
        logger.warning(
            "SECURITY WARNING: Binding to %s exposes audiodoc on all "
            "network interfaces. Ensure API keys and firewall rules are configured.",
            resolved_host,
        )

    uvicorn.run(
        "audiodoc.main:create_app",
        factory=True,
        host=resolved_host,
        port=resolved_port,
        server_header=False,
    )
