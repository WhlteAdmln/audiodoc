# Copyright (c) 2026 Nikolai Zelensky
"""Command-line interface for the audiodoc server."""

import argparse
import importlib
import logging
import os
import secrets
import sys
import tempfile
import warnings
from collections.abc import Callable, Mapping, Sequence
from importlib.metadata import version as package_version
from ipaddress import IPv4Address
from pathlib import Path

import uvicorn
from dotenv import dotenv_values

from audiodoc.api.auth import check_security_settings
from audiodoc.config import ConfigError, Settings, load_env_file, load_settings
from audiodoc.doctor import collect_doctor_checks
from audiodoc.env_readers import get_bool, get_home_dir, get_log_level
from audiodoc.logging_setup import configure_logging
from audiodoc.service import install_service_unit, render_service_unit
from audiodoc.system_diagnostics import DiagnosticCheck

logger = logging.getLogger(__name__)
MAX_PORT = 65_535
ALL_INTERFACES_HOST = str(IPv4Address(0))
CommandHandler = Callable[[argparse.Namespace, argparse.ArgumentParser], int]
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


def _parse_host(value: str) -> str:
    """Validate a hostname or IP address used for server binding."""
    if not value.strip() or any(character.isspace() for character in value):
        message = "Host must be a non-empty hostname or IP address."
        raise argparse.ArgumentTypeError(message)
    return value


def _parse_compute_type(value: str) -> str:
    """Reject empty compute types and line breaks."""
    if not value or "\n" in value or "\r" in value:
        message = "Compute type must be a non-empty single-line value."
        raise argparse.ArgumentTypeError(message)
    return value


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(prog="audiodoc")
    commands = parser.add_subparsers(dest="command", required=True)

    run_parser = commands.add_parser("run", help="Run the API server.")
    run_parser.add_argument("--host", type=_parse_host)
    run_parser.add_argument("--port", type=_parse_port)
    run_parser.add_argument("--env-file", type=Path)

    commands.add_parser("version", help="Show the installed version.")
    doctor_parser = commands.add_parser("doctor", help="Check the audiodoc installation.")
    doctor_parser.add_argument(
        "--offline", action="store_true", help="Require the model to be available locally."
    )

    init_parser = commands.add_parser("init", help="Create a protected .env file.")
    init_parser.add_argument("--model", choices=SUPPORTED_MODEL_NAMES, default="small")
    init_parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    init_parser.add_argument("--compute-type", type=_parse_compute_type)
    init_parser.add_argument("--host", type=_parse_host, default="127.0.0.1")
    init_parser.add_argument("--port", type=_parse_port, default=8000)
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
        "--user", dest="service_mode", action="store_const", const="user"
    )
    mode_group.add_argument(
        "--system", dest="service_mode", action="store_const", const="system"
    )
    install_parser.set_defaults(service_mode="user")
    install_parser.add_argument("--print", dest="print_unit", action="store_true")
    install_parser.add_argument("--force", action="store_true")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the audiodoc command-line interface."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    handlers: dict[str, CommandHandler] = {
        "run": _handle_run_command,
        "version": _handle_version_command,
        "doctor": _handle_doctor_command,
        "init": _handle_init_command,
        "pair": _handle_pair_command,
        "model": _handle_model_command,
        "config": _handle_config_command,
        "service": _handle_service_command,
    }
    handler = handlers.get(args.command)
    if handler is None:
        parser.print_usage(sys.stderr)
        sys.stderr.write(f"{parser.prog}: error: Unsupported command.\n")
        return 2
    return handler(args, parser)


def _handle_run_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Handle the run command."""
    try:
        _run_server(args.host, args.port, args.env_file)
    except ConfigError as error:
        parser.error(str(error))
    return 0


def _handle_version_command(
    _args: argparse.Namespace, _parser: argparse.ArgumentParser
) -> int:
    """Handle the version command."""
    sys.stdout.write(f"audiodoc {package_version('audiodoc')}\n")
    return 0


def _handle_doctor_command(
    _args: argparse.Namespace, _parser: argparse.ArgumentParser
) -> int:
    """Handle installation diagnostics."""
    load_env_file()
    if _args.offline:
        checks = collect_doctor_checks(os.environ, offline=True)
    else:
        checks = collect_doctor_checks(os.environ)
    for check in checks:
        sys.stdout.write(f"{check.status:4} {check.name}: {check.message}\n")

    install_commands = _native_install_commands(checks)
    if install_commands:
        sys.stdout.write("Install missing native tools with one of:\n")
        for distribution, command in install_commands:
            sys.stdout.write(f"  {distribution}: {command}\n")

    return 1 if any(check.status == "FAIL" for check in checks) else 0


def _native_install_commands(
    checks: Sequence[DiagnosticCheck],
) -> tuple[tuple[str, str], ...]:
    """Return OS-specific installation commands for missing native tools."""
    failed_names = {check.name for check in checks if check.status == "FAIL"}
    packages: dict[str, list[str]] = {
        "apt": [],
        "dnf": [],
        "pacman": [],
    }

    if "Tesseract" in failed_names:
        packages["apt"].extend(
            ("tesseract-ocr", "tesseract-ocr-rus", "tesseract-ocr-eng")
        )
        packages["dnf"].extend(
            ("tesseract", "tesseract-langpack-rus", "tesseract-langpack-eng")
        )
        packages["pacman"].extend(
            ("tesseract", "tesseract-data-rus", "tesseract-data-eng")
        )

    if "DjVuLibre" in failed_names:
        packages["apt"].append("djvulibre-bin")
        packages["dnf"].append("djvulibre")
        packages["pacman"].append("djvulibre")

    if not any(packages.values()):
        return ()

    return (
        ("Debian/Ubuntu", f"sudo apt install {' '.join(packages['apt'])}"),
        ("Fedora/RHEL", f"sudo dnf install {' '.join(packages['dnf'])}"),
        ("Arch Linux", f"sudo pacman -S {' '.join(packages['pacman'])}"),
    )


def _handle_init_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Handle the init command."""
    compute_type = args.compute_type or ("float16" if args.device == "cuda" else "int8")
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


def _handle_pair_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Handle the pair command."""
    try:
        snippet = _build_pair_configuration(args.url)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    sys.stdout.write(snippet)
    return 0


def _handle_model_command(
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


def _handle_config_command(
    args: argparse.Namespace, _parser: argparse.ArgumentParser
) -> int:
    """Handle configuration inspection commands."""
    if args.config_command == "check":
        load_env_file()
        problems = _configuration_problems(os.environ)
        if problems:
            sys.stdout.write("Configuration has problems:\n")
            for problem in problems:
                sys.stdout.write(f"- {problem}\n")
            return 1
        sys.stdout.write("Configuration is valid.\n")
        return 0
    return 2


def _handle_service_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    """Handle systemd service installation."""
    home = get_home_dir()
    try:
        if args.print_unit:
            sys.stdout.write(render_service_unit(home, mode=args.service_mode))
            return 0
        unit_path = install_service_unit(
            home,
            mode=args.service_mode,
            force=args.force,
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))

    sys.stdout.write(f"Installed {args.service_mode} systemd unit: {unit_path}\n")
    sys.stdout.write("The service was not enabled or started. When ready, run:\n")
    if args.service_mode == "user":
        commands = (
            "systemctl --user daemon-reload",
            "systemctl --user enable --now audiodoc.service",
            "systemctl --user status audiodoc.service",
        )
    else:
        commands = (
            "sudo systemctl daemon-reload",
            "sudo systemctl enable --now audiodoc.service",
            "sudo systemctl status audiodoc.service",
        )
    for command in commands:
        sys.stdout.write(f"  {command}\n")
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
            resolved_port = _parse_port(os.environ.get("AUDIODOC_PORT", "8000"))
        except argparse.ArgumentTypeError as error:
            raise ConfigError([f"Invalid AUDIODOC_PORT: {error}"]) from error
    else:
        resolved_port = port

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

    if resolved_host == ALL_INTERFACES_HOST:
        logger.warning(
            "SECURITY WARNING: Binding to 0.0.0.0 exposes audiodoc on all "
            "network interfaces. Ensure API keys and firewall rules are configured."
        )

    uvicorn.run(
        "audiodoc.main:create_app",
        factory=True,
        host=resolved_host,
        port=resolved_port,
        server_header=False,
    )


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
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
        temporary_path.chmod(0o600)
        if force:
            temporary_path.replace(env_path)
        else:
            os.link(temporary_path, env_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    return env_path


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
        elif ":" in host and not host.startswith("["):
            host = f"[{host}]"
        base_url = f"http://{host}:{port}"

    return (
        f"AUDIODOC_URL={base_url}\n"
        f"AUDIODOC_AUDIO_KEY={audio_key}\n"
        f"AUDIODOC_DOCUMENT_KEY={document_key}\n"
    )


def _download_model(name: str, directory: Path) -> Path:
    """Download a supported Whisper model into the selected directory."""
    directory.mkdir(parents=True, exist_ok=True)
    download_model = importlib.import_module("faster_whisper.utils").download_model
    downloaded_path = download_model(name, output_dir=str(directory))
    return Path(downloaded_path)


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
