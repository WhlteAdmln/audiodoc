# Copyright (c) 2026 Nikolai Zelensky
"""Argument parser of the audiodoc command-line interface."""

import argparse
from pathlib import Path

from audiodoc.service import SYSTEM_MODE, USER_MODE

MAX_PORT = 65_535
LINE_FEED = "\n"
CARRIAGE_RETURN = "\r"
SUPPORTED_MODEL_NAMES = (
    "tiny",
    "tiny.en",
    "base",
    "base.en",
    "small",
    "small.en",
    "medium",
    "medium.en",
    "large",
    "large-v1",
    "large-v2",
    "large-v3",
    "large-v3-turbo",
    "turbo",
    "distil-small.en",
    "distil-medium.en",
    "distil-large-v2",
    "distil-large-v3",
)


def parse_port(value: str) -> int:
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


def _parse_host(value: str) -> str:
    """Validate a hostname or IP address used for server binding."""
    if not value.strip() or any(character.isspace() for character in value):
        message = "Host must be a non-empty hostname or IP address."
        raise argparse.ArgumentTypeError(message)
    return value


def _parse_compute_type(value: str) -> str:
    """Reject empty compute types and line breaks."""
    if not value or LINE_FEED in value or CARRIAGE_RETURN in value:
        message = "Compute type must be a non-empty single-line value."
        raise argparse.ArgumentTypeError(message)
    return value


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(prog="audiodoc")
    commands = parser.add_subparsers(dest="command", required=True)

    run_parser = commands.add_parser("run", help="Run the API server.")
    run_parser.add_argument("--host", type=_parse_host)
    run_parser.add_argument("--port", type=parse_port)
    run_parser.add_argument("--env-file", type=Path)

    commands.add_parser("version", help="Show the installed version.")
    doctor_parser = commands.add_parser(
        "doctor", help="Check the audiodoc installation."
    )
    doctor_parser.add_argument(
        "--offline",
        action="store_true",
        help="Require the model to be available locally.",
    )

    init_parser = commands.add_parser("init", help="Create a protected .env file.")
    init_parser.add_argument("--model", choices=SUPPORTED_MODEL_NAMES, default="small")
    init_parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    init_parser.add_argument("--compute-type", type=_parse_compute_type)
    init_parser.add_argument("--host", type=_parse_host, default="127.0.0.1")
    init_parser.add_argument("--port", type=parse_port, default=8000)
    init_parser.add_argument("--force", action="store_true")

    pair_parser = commands.add_parser(
        "pair", help="Print the bot configuration settings."
    )
    pair_parser.add_argument("--url")

    model_parser = commands.add_parser("model", help="Manage Whisper models.")
    model_commands = model_parser.add_subparsers(dest="model_command", required=True)
    download_parser = model_commands.add_parser(
        "download", help="Download a Whisper model."
    )
    download_parser.add_argument(
        "--name", choices=SUPPORTED_MODEL_NAMES, default="small"
    )
    download_parser.add_argument("--dir", dest="directory", type=Path)

    config_parser = commands.add_parser(
        "config", help="Inspect application configuration."
    )
    config_commands = config_parser.add_subparsers(dest="config_command", required=True)
    config_commands.add_parser("check", help="Validate configuration.")

    service_parser = commands.add_parser("service", help="Manage the systemd service.")
    service_commands = service_parser.add_subparsers(
        dest="service_command", required=True
    )
    install_parser = service_commands.add_parser(
        "install", help="Render or install a systemd unit."
    )
    mode_group = install_parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--user", dest="service_mode", action="store_const", const=USER_MODE
    )
    mode_group.add_argument(
        "--system", dest="service_mode", action="store_const", const=SYSTEM_MODE
    )
    install_parser.set_defaults(service_mode=USER_MODE)
    install_parser.add_argument("--print", dest="print_unit", action="store_true")
    install_parser.add_argument("--force", action="store_true")

    return parser
