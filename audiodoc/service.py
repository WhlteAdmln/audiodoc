# Copyright (c) 2026 Nikolai Zelensky
"""Systemd service unit rendering and installation."""

import ipaddress
import os
import re
import shutil
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

ServiceMode = Literal["user", "system"]
UNIT_NAME = "audiodoc.service"
SYSTEM_UNIT_DIRECTORY = Path("/etc/systemd/system")
DEFAULT_IP_ADDRESS_ALLOW = ("10.8.0.0/24", "127.0.0.1")

_UNIT_TEMPLATE = """[Unit]
Description={description}
After={after}
Wants=network-online.target

[Service]
{directives}

[Install]
WantedBy={wanted_by}
"""


def _escape_systemd_path(value: str) -> str:
    """Escape a path for a systemd path directive."""
    if any(character in value for character in "\x00\r\n"):
        message = "Systemd paths must not contain null bytes or line breaks."
        raise ValueError(message)
    escapes = {"\\": "\\\\", " ": r"\x20", "\t": r"\t", '"': r"\x22", "%": "%%"}
    return "".join(escapes.get(character, character) for character in value)


def _quote_systemd_value(value: str) -> str:
    """Quote a systemd value and escape specifier characters."""
    if any(character in value for character in "\x00\r\n"):
        message = "Systemd values must not contain null bytes or line breaks."
        raise ValueError(message)
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
    return f'"{escaped}"'


def render_service_unit(
    home: Path,
    *,
    mode: ServiceMode,
    memory_high: str = "10G",
    memory_max: str = "12G",
    ip_address_allow: Sequence[str] = DEFAULT_IP_ADDRESS_ALLOW,
) -> str:
    """Render a systemd unit without filesystem or system side effects."""
    if not home.is_absolute():
        message = "The audiodoc home directory must be an absolute path."
        raise ValueError(message)
    if mode not in {"user", "system"}:
        message = f"Unsupported systemd service mode: {mode}"
        raise ValueError(message)
    for name, value in (("MemoryHigh", memory_high), ("MemoryMax", memory_max)):
        if not re.fullmatch(r"[1-9][0-9]*[KMGTP]?", value):
            message = f"{name} must be a positive integer with an optional unit."
            raise ValueError(message)

    addresses: tuple[str, ...] = ()
    directives = ["Type=simple"]
    if mode == "system":
        addresses = tuple(ip_address_allow)
        if not addresses:
            message = "At least one IPAddressAllow entry is required."
            raise ValueError(message)
        for address in addresses:
            try:
                ipaddress.ip_network(address, strict=False)
            except ValueError as error:
                message = f"Invalid IPAddressAllow entry: {address}"
                raise ValueError(message) from error
        directives.extend(("User=audiodoc", "Group=audiodoc"))

    executable = _quote_systemd_value(str(home / ".venv" / "bin" / "audiodoc"))
    directives.extend(
        (
            f"WorkingDirectory={_escape_systemd_path(str(home))}",
            f"EnvironmentFile={_escape_systemd_path(str(home / '.env'))}",
            f"Environment={_quote_systemd_value(f'AUDIODOC_HOME={home}')}",
            "Environment=PYTHONUNBUFFERED=1",
            f"ExecStart={executable} run",
            "Restart=on-failure",
            "RestartSec=5",
            "UMask=0077",
        )
    )
    if mode == "system":
        directives.extend(
            (
                "",
                (
                    "# Tune these values to the actual host; keep headroom for "
                    "llama-server."
                ),
                f"MemoryHigh={memory_high}",
                f"MemoryMax={memory_max}",
                "CPUQuota=600%",
                "TasksMax=256",
                "Nice=10",
                "",
                "# Process and filesystem sandbox.",
                "NoNewPrivileges=true",
                "PrivateTmp=true",
                "ProtectSystem=strict",
                "ProtectHome=true",
                f"ReadWritePaths={_escape_systemd_path(str(home / 'tmp'))}",
                "ProtectKernelTunables=true",
                "ProtectKernelModules=true",
                "ProtectControlGroups=true",
                "RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX",
                "RestrictNamespaces=true",
                "LockPersonality=true",
                "SystemCallFilter=@system-service",
                "",
                "# Example private subnet. Replace it if your VPN/network differs.",
                "IPAddressDeny=any",
                f"IPAddressAllow={' '.join(addresses)}",
                "",
                (
                    "# For GPU inference, review PrivateDevices/DeviceAllow with "
                    "your driver docs."
                ),
            )
        )

    return _UNIT_TEMPLATE.format(
        description=(
            "audiodoc (Whisper + Document Engine)"
            if mode == "system"
            else "audiodoc API service"
        ),
        after=(
            "network-online.target wg-quick@wg0.service"
            if mode == "system"
            else "network-online.target"
        ),
        directives="\n".join(directives),
        wanted_by="multi-user.target" if mode == "system" else "default.target",
    )


def install_service_unit(
    home: Path,
    *,
    mode: ServiceMode,
    force: bool = False,
    unit_directory: Path | None = None,
) -> Path:
    """Install a unit without enabling or starting the service."""
    if unit_directory is None:
        unit_directory = (
            SYSTEM_UNIT_DIRECTORY
            if mode == "system"
            else Path.home() / ".config" / "systemd" / "user"
        )
    unit_path = unit_directory / UNIT_NAME
    backup_path = unit_path.with_name(f"{UNIT_NAME}.bak")
    exists = unit_path.exists() or unit_path.is_symlink()
    if exists and not force:
        message = f"Systemd unit exists: {unit_path}; pass --force to replace it."
        raise FileExistsError(message)
    if exists and (backup_path.exists() or backup_path.is_symlink()):
        message = f"Backup already exists: {backup_path}."
        raise FileExistsError(message)

    content = render_service_unit(home, mode=mode)
    unit_directory.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{UNIT_NAME}.", dir=unit_directory
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary_path.chmod(0o644)
        if exists:
            shutil.copy2(unit_path, backup_path)
            temporary_path.replace(unit_path)
        else:
            os.link(temporary_path, unit_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return unit_path
