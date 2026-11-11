# Copyright (c) 2026 Nikolai Zelensky
"""Systemd service unit and CLI tests."""

from pathlib import Path
from typing import cast

import pytest

from audiodoc import cli, service
from audiodoc.service import ServiceMode, install_service_unit, render_service_unit

USER_GOLDEN = """[Unit]
Description=audiodoc API service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/srv/audiodoc
EnvironmentFile=/srv/audiodoc/.env
Environment="AUDIODOC_HOME=/srv/audiodoc"
Environment=PYTHONUNBUFFERED=1
ExecStart="/srv/audiodoc/.venv/bin/audiodoc" run
Restart=on-failure
RestartSec=5
UMask=0077

[Install]
WantedBy=default.target
"""

SYSTEM_GOLDEN = """[Unit]
Description=audiodoc (Whisper + Document Engine)
After=network-online.target wg-quick@wg0.service
Wants=network-online.target

[Service]
Type=simple
User=audiodoc
Group=audiodoc
WorkingDirectory=/opt/audiodoc
EnvironmentFile=/opt/audiodoc/.env
Environment="AUDIODOC_HOME=/opt/audiodoc"
Environment=PYTHONUNBUFFERED=1
ExecStart="/opt/audiodoc/.venv/bin/audiodoc" run
Restart=on-failure
RestartSec=5
UMask=0077

# Tune these values to the actual host; keep headroom for llama-server.
MemoryHigh=10G
MemoryMax=12G
CPUQuota=600%
TasksMax=256
Nice=10

# Process and filesystem sandbox.
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/audiodoc/tmp
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
RestrictNamespaces=true
LockPersonality=true
SystemCallFilter=@system-service

# Example private subnet. Replace it if your VPN/network differs.
IPAddressDeny=any
IPAddressAllow=10.8.0.0/24 127.0.0.1

# For GPU inference, review PrivateDevices/DeviceAllow with your driver docs.

[Install]
WantedBy=multi-user.target
"""


def test_render_units_match_golden_strings() -> None:
    """Keep both systemd unit modes stable."""
    assert render_service_unit(Path("/srv/audiodoc"), mode="user") == USER_GOLDEN
    assert render_service_unit(Path("/opt/audiodoc"), mode="system") == SYSTEM_GOLDEN


def test_system_unit_limits_and_network_allowlist_are_parameters() -> None:
    """Render host-specific resource and network limits."""
    unit = render_service_unit(
        Path("/opt/audiodoc"),
        mode="system",
        memory_high="6G",
        memory_max="8G",
        ip_address_allow=("10.9.0.0/16", "127.0.0.1"),
    )
    assert "MemoryHigh=6G\nMemoryMax=8G\n" in unit
    assert "IPAddressAllow=10.9.0.0/16 127.0.0.1\n" in unit


@pytest.mark.parametrize(
    ("home", "mode", "memory", "addresses", "message"),
    [
        (Path("relative"), "user", "10G", ("127.0.0.1",), "absolute"),
        (Path("/srv/app"), "invalid", "10G", ("127.0.0.1",), "Unsupported"),
        (Path("/srv/app"), "system", "bad", ("127.0.0.1",), "MemoryHigh"),
        (Path("/srv/app"), "system", "10G", (), "At least one"),
        (Path("/srv/app"), "system", "10G", ("not-an-ip",), "Invalid IP"),
        (Path("/srv/app\nExecStart=bad"), "user", "10G", (), "line breaks"),
    ],
)
def test_render_rejects_invalid_values(
    home: Path, mode: str, memory: str, addresses: tuple[str, ...], message: str
) -> None:
    """Reject invalid paths, modes, limits, and IP allowlist values."""
    with pytest.raises(ValueError, match=message):
        render_service_unit(
            home,
            mode=cast("ServiceMode", mode),
            memory_high=memory,
            ip_address_allow=addresses,
        )


def test_install_refuses_overwrite_and_saves_backup_with_force(
    tmp_path: Path,
) -> None:
    """Preserve existing units unless force is explicitly requested."""
    directory = tmp_path / "systemd"
    unit_path = directory / "audiodoc.service"
    directory.mkdir()
    unit_path.write_text("old unit\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        install_service_unit(tmp_path / "app", mode="system", unit_directory=directory)
    assert unit_path.read_text(encoding="utf-8") == "old unit\n"

    install_service_unit(
        tmp_path / "app", mode="system", force=True, unit_directory=directory
    )
    backup_path = directory / "audiodoc.service.bak"
    assert backup_path.read_text(encoding="utf-8") == "old unit\n"
    assert unit_path.read_text(encoding="utf-8") == render_service_unit(
        tmp_path / "app", mode="system"
    )
    with pytest.raises(FileExistsError, match="Backup already exists"):
        install_service_unit(
            tmp_path / "app", mode="system", force=True, unit_directory=directory
        )


def test_install_uses_system_unit_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Use the systemd system directory for system mode."""
    monkeypatch.setattr(service, "SYSTEM_UNIT_DIRECTORY", tmp_path)
    assert install_service_unit(tmp_path / "app", mode="system") == (
        tmp_path / "audiodoc.service"
    )


def test_cli_prints_and_installs_user_unit_without_starting_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exercise print and install modes through the public CLI."""
    user_home = tmp_path / "user"
    app_home = tmp_path / "application"
    monkeypatch.setenv("HOME", str(user_home))
    monkeypatch.setenv("AUDIODOC_HOME", str(app_home))
    unit_path = user_home / ".config/systemd/user/audiodoc.service"

    assert cli.main(["service", "install", "--print"]) == 0
    assert capsys.readouterr().out == render_service_unit(app_home, mode="user")
    assert not unit_path.exists()
    assert cli.main(["service", "install"]) == 0
    assert unit_path.read_text(encoding="utf-8") == USER_GOLDEN.replace(
        "/srv/audiodoc", str(app_home)
    )
    output = capsys.readouterr().out
    assert "The service was not enabled or started." in output
    assert "systemctl --user enable --now audiodoc.service" in output


def test_cli_prints_hardened_system_unit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Print the system unit without writing files or invoking systemctl."""
    home = tmp_path / "audiodoc"
    monkeypatch.setenv("AUDIODOC_HOME", str(home))
    assert cli.main(["service", "install", "--system", "--print"]) == 0
    assert capsys.readouterr().out == render_service_unit(home, mode="system")


def test_deploy_example_and_installer_use_the_canonical_renderer() -> None:
    """Prevent separate systemd unit sources in deployment and installation."""
    root = Path(__file__).resolve().parents[2]
    example = (root / "deploy/audiodoc.service.example").read_text(encoding="utf-8")
    installer = (root / "install.sh").read_text(encoding="utf-8")
    assert "audiodoc service install --system --print" in example
    assert "[Service]" not in example
    assert "-m audiodoc service install --user" in installer
    assert 'cat >"$SYSTEMD_UNIT_FILE" <<EOF' not in installer
