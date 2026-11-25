# Copyright (c) 2026 Nikolai Zelensky
"""System configuration diagnostics for the audiodoc installation."""

import errno
import ipaddress
import json
import os
import socket
import stat
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from http import HTTPStatus
from http.client import HTTPConnection, HTTPException
from pathlib import Path
from typing import Literal

from audiodoc.env_readers import get_bool, get_home_dir, resolve_home_path

MAX_PORT = 65_535
HEALTH_PROBE_TIMEOUT_SECONDS = 2.0
HEALTHY_STATUS = "ok"
HEALTH_LOADED_FIELD = "loaded"

CheckStatus = Literal["OK", "WARN", "FAIL"]
FAIL_STATUS: CheckStatus = "FAIL"
IPV6_HOST_MARKER = ":"


@dataclass(frozen=True, slots=True)
class DiagnosticCheck:
    """Describe the result of one system diagnostic check."""

    name: str
    status: CheckStatus
    message: str


def check_python_version() -> DiagnosticCheck:
    """Check that the running Python version is supported."""
    major, minor, micro = sys.version_info[:3]
    if (major, minor, micro) < (3, 11, 5):
        return DiagnosticCheck(
            "Python",
            "FAIL",
            f"Python 3.11.5 or newer is required; found {major}.{minor}.{micro}.",
        )
    return DiagnosticCheck(
        "Python",
        "OK",
        f"Python {major}.{minor}.{micro} is supported.",
    )


def check_env_file(environ: Mapping[str, str]) -> DiagnosticCheck:
    """Check that the application .env file exists and has private permissions."""
    env_path = get_home_dir(environ) / ".env"
    try:
        metadata = env_path.lstat()
    except FileNotFoundError:
        return DiagnosticCheck("Environment file", "FAIL", f"Not found: {env_path}.")
    except OSError as error:
        return DiagnosticCheck(
            "Environment file",
            "FAIL",
            f"Cannot inspect {env_path}: {error}.",
        )

    if not stat.S_ISREG(metadata.st_mode):
        return DiagnosticCheck(
            "Environment file",
            "FAIL",
            f"Not a regular file: {env_path}.",
        )

    permissions = stat.S_IMODE(metadata.st_mode)
    if permissions & 0o077 or permissions & stat.S_IRUSR == 0:
        return DiagnosticCheck(
            "Environment file",
            "FAIL",
            f"Permissions must be private and owner-readable: {env_path}.",
        )

    return DiagnosticCheck(
        "Environment file",
        "OK",
        f"Found with private permissions: {env_path}.",
    )


def _key_values(environ: Mapping[str, str], name: str) -> set[str]:
    """Read comma-separated API keys from one environment variable."""
    value = environ.get(name, "")
    return {item.strip() for item in value.split(",") if item.strip()}


def check_api_keys(environ: Mapping[str, str]) -> DiagnosticCheck:
    """Check that both API keys exist and do not share values."""
    audio_keys = _key_values(environ, "AUDIODOC_AUDIO_KEY")
    document_keys = _key_values(environ, "AUDIODOC_DOCUMENT_KEY")
    missing = [
        name
        for name, keys in (
            ("AUDIODOC_AUDIO_KEY", audio_keys),
            ("AUDIODOC_DOCUMENT_KEY", document_keys),
        )
        if not keys
    ]
    if missing:
        return DiagnosticCheck(
            "API keys",
            "FAIL",
            "Missing API keys: " + ", ".join(missing) + ".",
        )
    if audio_keys & document_keys:
        return DiagnosticCheck(
            "API keys",
            "FAIL",
            "The audio and document API keys share at least one value.",
        )
    return DiagnosticCheck("API keys", "OK", "Both API keys are present and distinct.")


def check_unauthenticated_setting(environ: Mapping[str, str]) -> DiagnosticCheck:
    """Warn when unauthenticated API access is enabled."""
    try:
        enabled = get_bool("ALLOW_UNAUTHENTICATED", environ=environ)
    except ValueError:
        return DiagnosticCheck(
            "Unauthenticated access",
            "FAIL",
            "ALLOW_UNAUTHENTICATED must be a valid boolean.",
        )
    if enabled:
        return DiagnosticCheck(
            "Unauthenticated access",
            "WARN",
            "ALLOW_UNAUTHENTICATED=true disables API authentication.",
        )
    return DiagnosticCheck(
        "Unauthenticated access",
        "OK",
        "ALLOW_UNAUTHENTICATED is disabled.",
    )


def binds_all_interfaces(host: str) -> bool:
    """Return whether a numeric host spells the unspecified (all-interfaces) address."""
    try:
        addresses = socket.getaddrinfo(host, None, flags=socket.AI_NUMERICHOST)
    except (socket.gaierror, UnicodeError):
        return False
    return any(
        ipaddress.ip_address(sockaddr[0]).is_unspecified
        for _family, _type, _proto, _canonname, sockaddr in addresses
    )


def check_bind_address(environ: Mapping[str, str]) -> DiagnosticCheck:
    """Warn when the server is configured to bind on every network interface."""
    host = (environ.get("AUDIODOC_HOST", "127.0.0.1").strip()) or "127.0.0.1"
    if binds_all_interfaces(host):
        return DiagnosticCheck(
            "Bind address",
            "WARN",
            f"Binding to {host} exposes the server on all network interfaces.",
        )
    return DiagnosticCheck("Bind address", "OK", f"Server binds to {host}.")


def _probe_writable(directory: Path) -> None:
    """Create the directory and open a temporary file in it."""
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryFile(dir=directory):
        pass


def check_temp_directory(environ: Mapping[str, str]) -> DiagnosticCheck:
    """Check that the configured temporary directory can accept writes."""
    home = get_home_dir(environ)
    configured_path = environ.get("BACKEND_TEMP_DIR", "").strip()
    directory = (
        resolve_home_path(configured_path, home) if configured_path else home / "tmp"
    )
    try:
        _probe_writable(directory)
    except OSError as error:
        return DiagnosticCheck(
            "Temporary directory",
            "FAIL",
            f"Cannot write to {directory}: {error}.",
        )
    return DiagnosticCheck(
        "Temporary directory",
        "OK",
        f"Writable: {directory}.",
    )


def _probe_bind(family: int, host: str, port: int) -> None:
    """Bind a TCP socket to the address to prove that the port is free."""
    with socket.socket(family, socket.SOCK_STREAM) as listener:
        listener.bind((host, port))


def _request_health(connection: HTTPConnection) -> tuple[int, bytes]:
    """Send GET /health and return the response status and body."""
    connection.request("GET", "/health")
    response = connection.getresponse()
    return response.status, response.read()


def _serves_audiodoc_health(host: str, port: int) -> bool:
    """Return whether an audiodoc service answers /health on the address."""
    connection = HTTPConnection(host, port, timeout=HEALTH_PROBE_TIMEOUT_SECONDS)
    try:
        status, body = _request_health(connection)
    except (OSError, HTTPException):
        return False
    finally:
        connection.close()
    if status != HTTPStatus.OK:
        return False
    try:
        payload = json.loads(body)
    except ValueError:
        return False
    return (
        isinstance(payload, dict)
        and payload.get("status") == HEALTHY_STATUS
        and HEALTH_LOADED_FIELD in payload
    )


def check_port(environ: Mapping[str, str]) -> DiagnosticCheck:
    """Check that the configured server TCP port is available."""
    host = (environ.get("AUDIODOC_HOST", "127.0.0.1").strip()) or "127.0.0.1"
    raw_port = environ.get("AUDIODOC_PORT", "8000").strip()
    try:
        port = int(raw_port)
    except ValueError:
        return DiagnosticCheck(
            "API port",
            "FAIL",
            "AUDIODOC_PORT must be an integer.",
        )
    if not 1 <= port <= MAX_PORT:
        return DiagnosticCheck(
            "API port",
            "FAIL",
            "AUDIODOC_PORT must be between 1 and 65535.",
        )

    family = socket.AF_INET6 if IPV6_HOST_MARKER in host else socket.AF_INET
    try:
        _probe_bind(family, host, port)
    except OSError as error:
        if error.errno == errno.EADDRINUSE and _serves_audiodoc_health(host, port):
            return DiagnosticCheck(
                "API port",
                "OK",
                f"Port {port} on {host} is used by the running audiodoc service.",
            )
        return DiagnosticCheck(
            "API port",
            "FAIL",
            f"Port {port} on {host} is unavailable: {error}.",
        )
    return DiagnosticCheck("API port", "OK", f"Port {port} on {host} is available.")


def collect_system_checks(
    environ: Mapping[str, str] | None = None,
) -> tuple[DiagnosticCheck, ...]:
    """Collect all system configuration checks."""
    source = os.environ if environ is None else environ
    return (
        check_python_version(),
        check_env_file(source),
        check_api_keys(source),
        check_unauthenticated_setting(source),
        check_bind_address(source),
        check_temp_directory(source),
        check_port(source),
    )
