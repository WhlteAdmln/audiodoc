# Copyright (c) 2026 Nikolai Zelensky
"""Command-line interface for the audiodoc server."""

import argparse
import logging
import os
import sys
import warnings
from collections.abc import Mapping, Sequence
from importlib.metadata import version as package_version
from ipaddress import IPv4Address
from pathlib import Path

import uvicorn

from audiodoc.api.auth import check_security_settings
from audiodoc.config import ConfigError, Settings, load_env_file, load_settings
from audiodoc.env_readers import get_bool, get_log_level
from audiodoc.logging_setup import configure_logging

logger = logging.getLogger(__name__)
MAX_PORT = 65_535
ALL_INTERFACES_HOST = str(IPv4Address(0))


def _parse_port(value: str) -> int:
    """Parse a TCP port number."""
    try:
        port = int(value)
    except ValueError as error:
        message = "Port must be an integer."
        raise argparse.ArgumentTypeError(message) from error

    if not 1 <= port <= MAX_PORT:
        message = f"Port must be between 1 and {MAX_PORT}."
        raise argparse.ArgumentTypeError(message)

    return port


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(prog="audiodoc")
    commands = parser.add_subparsers(dest="command", required=True)

    run_parser = commands.add_parser("run", help="Run the API server.")
    run_parser.add_argument("--host", default="127.0.0.1")
    run_parser.add_argument("--port", type=_parse_port, default=8000)
    run_parser.add_argument("--env-file", type=Path)

    commands.add_parser("version", help="Show the installed version.")

    config_parser = commands.add_parser(
        "config", help="Inspect application configuration."
    )
    config_commands = config_parser.add_subparsers(dest="config_command", required=True)
    config_commands.add_parser("check", help="Validate configuration.")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the audiodoc command-line interface."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        _run_server(args.host, args.port, args.env_file)
        return 0

    if args.command == "version":
        sys.stdout.write(f"audiodoc {package_version('audiodoc')}\n")
        return 0

    if args.command == "config" and args.config_command == "check":
        load_env_file()
        problems = _configuration_problems(os.environ)
        if problems:
            sys.stdout.write("Configuration has problems:\n")
            for problem in problems:
                sys.stdout.write(f"- {problem}\n")
            return 1

        sys.stdout.write("Configuration is valid.\n")
        return 0

    parser.print_usage(sys.stderr)
    sys.stderr.write(f"{parser.prog}: error: Unsupported command.\n")
    return 2


def _run_server(host: str, port: int, env_file: Path | None) -> None:
    """Load configuration, configure logging, and start Uvicorn."""
    load_env_file(env_file)
    configured_settings = load_settings(os.environ)
    secrets = tuple(
        part.strip()
        for value in (
            configured_settings.AUDIODOC_AUDIO_KEY,
            configured_settings.AUDIODOC_DOCUMENT_KEY,
        )
        for part in value.split(",")
        if part.strip()
    )
    configure_logging(configured_settings.LOG_LEVEL, secrets)

    if host == ALL_INTERFACES_HOST:
        logger.warning(
            "SECURITY WARNING: Binding to 0.0.0.0 exposes audiodoc on all "
            "network interfaces. Ensure API keys and firewall rules are configured."
        )

    uvicorn.run(
        "audiodoc.main:create_app",
        factory=True,
        host=host,
        port=port,
        server_header=False,
    )


def _configuration_problems(environ: Mapping[str, str]) -> list[str]:
    """Collect configuration and security problems without exposing secrets."""
    problems: list[str] = []
    try:
        configured_settings = load_settings(environ)
    except ConfigError as error:
        problems.extend(message.partition(" Got:")[0] for message in error.errors)
        configured_settings = _settings_for_security_check(environ)

    try:
        check_security_settings(configured_settings)
    except RuntimeError as error:
        problems.append(str(error))

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always", RuntimeWarning)
        get_log_level(environ=environ)

    if captured:
        problems.append("Invalid LOG_LEVEL; falling back to INFO.")

    return problems


def _settings_for_security_check(environ: Mapping[str, str]) -> Settings:
    """Build the authentication settings even when other settings are invalid."""
    audio_key = environ.get("AUDIODOC_AUDIO_KEY", "").strip()
    if not audio_key:
        audio_key = environ.get("WHISPER_API_KEY", "").strip()

    document_key = environ.get("AUDIODOC_DOCUMENT_KEY", "").strip()
    if not document_key:
        document_key = environ.get("DOCUMENT_API_KEY", "").strip()

    try:
        allow_unauthenticated = get_bool("ALLOW_UNAUTHENTICATED", environ=environ)
    except ValueError:
        allow_unauthenticated = False

    return Settings(
        AUDIODOC_AUDIO_KEY=audio_key,
        AUDIODOC_DOCUMENT_KEY=document_key,
        ALLOW_UNAUTHENTICATED=allow_unauthenticated,
    )
