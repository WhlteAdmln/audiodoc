# Copyright (c) 2026 Nikolai Zelensky
"""Systemd service unit and CLI tests."""

from pathlib import Path
from typing import cast

import pytest

from audiodoc import service
from audiodoc.service import install_service_unit, render_service_unit

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


@pytest.fixture(name="unit_directory")
def fixture_unit_directory(tmp_path: Path) -> Path:
    """Provide a systemd unit directory that holds an old unit."""
    directory = tmp_path / "systemd"
    directory.mkdir()
    (directory / "audiodoc.service").write_text("old unit\n", encoding="utf-8")
    return directory


def _rendering_error(
    home: Path, mode: str, memory: str, addresses: tuple[str, ...]
) -> str:
    with pytest.raises(ValueError, match=r".") as caught:
        render_service_unit(
            home,
            mode=cast("service.ServiceMode", mode),
            memory_high=memory,
            ip_address_allow=addresses,
        )
    return str(caught.value)


def _install_error(home: Path, directory: Path, *, force: bool) -> str:
    with pytest.raises(FileExistsError) as caught:
        install_service_unit(home, mode="system", force=force, unit_directory=directory)
    return str(caught.value)


@pytest.mark.parametrize(
    ("home", "mode", "golden"),
    [
        ("/srv/audiodoc", "user", USER_GOLDEN),
        ("/opt/audiodoc", "system", SYSTEM_GOLDEN),
    ],
)
def test_render_service_unit_matches_the_golden_unit(
    home: str, mode: str, golden: str
) -> None:
    unit = render_service_unit(Path(home), mode=cast("service.ServiceMode", mode))

    assert unit == golden, f"the {mode} unit changed"


def test_system_unit_limits_and_network_allowlist_are_parameters() -> None:
    unit = render_service_unit(
        Path("/opt/audiodoc"),
        mode="system",
        memory_high="6G",
        memory_max="8G",
        ip_address_allow=("10.9.0.0/16", "127.0.0.1", "fd00::/8"),
    )

    prefixes = ("MemoryHigh=", "MemoryMax=", "IPAddressAllow=")
    lines = [line for line in unit.splitlines() if line.startswith(prefixes)]
    expected = [
        "MemoryHigh=6G",
        "MemoryMax=8G",
        "IPAddressAllow=10.9.0.0/16 127.0.0.1 fd00::/8",
    ]
    assert lines == expected, "the limits and the allowlist must be applied"


def test_render_service_unit_escapes_spaces_quotes_and_specifiers() -> None:
    unit = render_service_unit(Path('/srv/my app/100%"x'), mode="user")

    prefixes = ("WorkingDirectory=", "EnvironmentFile=", 'Environment="', "ExecStart=")
    lines = [line for line in unit.splitlines() if line.startswith(prefixes)]
    expected = [
        "WorkingDirectory=/srv/my\\x20app/100%%\\x22x",
        "EnvironmentFile=/srv/my\\x20app/100%%\\x22x/.env",
        'Environment="AUDIODOC_HOME=/srv/my app/100%%\\"x"',
        'ExecStart="/srv/my app/100%%\\"x/.venv/bin/audiodoc" run',
    ]
    assert lines == expected, "a hostile home must not break the unit syntax"


@pytest.mark.parametrize(
    ("home", "mode", "memory", "addresses", "message"),
    [
        (Path("relative"), "user", "10G", ("127.0.0.1",), "absolute"),
        (Path("/srv/app"), "invalid", "10G", ("127.0.0.1",), "Unsupported"),
        (Path("/srv/app"), "system", "bad", ("127.0.0.1",), "MemoryHigh"),
        (Path("/srv/app"), "system", "0", ("127.0.0.1",), "MemoryHigh"),
        (Path("/srv/app"), "system", "10G\nExecStartPre=/bin/sh", (), "MemoryHigh"),
        (Path("/srv/app"), "system", "10G", (), "At least one"),
        (Path("/srv/app"), "system", "10G", ("not-an-ip",), "Invalid IP"),
        (Path("/srv/app"), "system", "10G", ("10.0.0.0/8\nX=1",), "Invalid IP"),
        (Path("/srv/app\nExecStart=bad"), "user", "10G", (), "line breaks"),
        (Path("/srv/app\rExecStart=bad"), "user", "10G", (), "line breaks"),
        (Path("/srv/app\x00evil"), "user", "10G", (), "null bytes"),
    ],
)
def test_render_rejects_invalid_values(
    home: Path, mode: str, memory: str, addresses: tuple[str, ...], message: str
) -> None:
    error = _rendering_error(home, mode, memory, addresses)

    assert message in error, f"unexpected error {error!r}"


def test_install_refuses_to_overwrite_an_existing_unit(
    tmp_path: Path, unit_directory: Path
) -> None:
    _install_error(tmp_path / "app", unit_directory, force=False)

    content = (unit_directory / "audiodoc.service").read_text(encoding="utf-8")
    expected = "old unit\n"
    assert content == expected, "the old unit must stay without --force"


def test_install_with_force_saves_a_backup_of_the_old_unit(
    tmp_path: Path, unit_directory: Path
) -> None:
    install_service_unit(
        tmp_path / "app", mode="system", force=True, unit_directory=unit_directory
    )

    backup = (unit_directory / "audiodoc.service.bak").read_text(encoding="utf-8")
    expected = "old unit\n"
    assert backup == expected, "the backup must hold the old unit"


def test_install_with_force_writes_the_rendered_unit(
    tmp_path: Path, unit_directory: Path
) -> None:
    unit_path = install_service_unit(
        tmp_path / "app", mode="system", force=True, unit_directory=unit_directory
    )

    expected = render_service_unit(tmp_path / "app", mode="system")
    assert unit_path.read_text(encoding="utf-8") == expected, "wrong unit content"


def test_install_with_force_refuses_to_overwrite_an_existing_backup(
    tmp_path: Path, unit_directory: Path
) -> None:
    (unit_directory / "audiodoc.service.bak").write_text("first\n", encoding="utf-8")

    error = _install_error(tmp_path / "app", unit_directory, force=True)

    expected_message = "Backup already exists"
    assert expected_message in error, f"unexpected error {error!r}"


def test_install_refuses_a_symlinked_unit_without_force(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "systemd"
    directory.mkdir()
    target = tmp_path / "чужой.service"
    target.write_text("[Unit]\n", encoding="utf-8")
    (directory / "audiodoc.service").symlink_to(target)

    error = _install_error(tmp_path / "app", directory, force=False)

    expected_message = "Systemd unit exists"
    assert expected_message in error, f"unexpected error {error!r}"


def test_install_with_force_replaces_a_symlink_instead_of_its_target(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "systemd"
    directory.mkdir()
    target = tmp_path / "чужой.service"
    target.write_text("[Unit]\n", encoding="utf-8")
    (directory / "audiodoc.service").symlink_to(target)

    unit_path = install_service_unit(
        tmp_path / "app", mode="system", force=True, unit_directory=directory
    )

    observed = (unit_path.is_symlink(), target.read_text(encoding="utf-8"))
    expected = (False, "[Unit]\n")
    assert observed == expected, "--force must not write through a symlink"


def test_install_makes_the_unit_world_readable_but_not_writable(
    tmp_path: Path,
) -> None:
    unit_path = install_service_unit(
        tmp_path / "app", mode="system", unit_directory=tmp_path / "новый каталог"
    )

    expected_mode = 0o644
    assert unit_path.stat().st_mode & 0o777 == expected_mode, "the unit must be 0644"


def test_install_leaves_no_temporary_file_behind(
    tmp_path: Path, unit_directory: Path
) -> None:
    install_service_unit(
        tmp_path / "app", mode="system", force=True, unit_directory=unit_directory
    )

    names = sorted(path.name for path in unit_directory.iterdir())
    expected = ["audiodoc.service", "audiodoc.service.bak"]
    assert names == expected, "a temporary unit file was left behind"


def test_install_uses_system_unit_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "SYSTEM_UNIT_DIRECTORY", tmp_path)

    unit_path = install_service_unit(tmp_path / "app", mode="system")

    expected = tmp_path / "audiodoc.service"
    assert unit_path == expected, "the system unit must go to the system directory"


def test_install_uses_the_user_unit_directory_under_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "пользователь"
    monkeypatch.setenv("HOME", str(home))

    unit_path = install_service_unit(tmp_path / "app", mode="user")

    expected = home / ".config" / "systemd" / "user" / "audiodoc.service"
    assert unit_path == expected, "the user unit must go under the user's home"


def test_deploy_example_and_installer_use_the_canonical_renderer() -> None:
    root = Path(__file__).resolve().parents[2]
    example = (root / "deploy/audiodoc.service.example").read_text(encoding="utf-8")
    installer = (root / "install.sh").read_text(encoding="utf-8")

    print_command = "audiodoc service install --system --print"
    service_section = "[Service]"
    install_command = "-m audiodoc service install --user"
    unit_heredoc = 'cat >"$SYSTEMD_UNIT_FILE" <<EOF'
    observed = (
        print_command in example,
        service_section in example,
        install_command in installer,
        unit_heredoc in installer,
    )
    expected = (True, False, True, False)
    assert observed == expected, "units must come only from the renderer"
