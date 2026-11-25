# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the run command."""

import logging
from collections.abc import Iterable
from ipaddress import IPv4Address
from pathlib import Path

import pytest
import uvicorn

from audiodoc import cli
from audiodoc.cli import run as run_command
from audiodoc.config import Settings


def test_run_loads_configuration_and_starts_uvicorn(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls: list[tuple[str, object]] = []
    env_file = tmp_path / "custom.env"
    all_interfaces_host = str(IPv4Address(0))

    def record_env_file(path: Path | None = None) -> None:
        calls.append(("env", path))

    def record_logging(level: str, secrets: Iterable[str]) -> None:
        calls.append(("logging", (level, tuple(secrets))))

    def record_uvicorn(application: str, **kwargs: object) -> None:
        calls.append(("uvicorn", (application, kwargs)))

    monkeypatch.setattr(run_command, "load_env_file", record_env_file)
    monkeypatch.setattr(run_command, "configure_logging", record_logging)
    monkeypatch.setattr(uvicorn, "run", record_uvicorn)
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("AUDIODOC_AUDIO_KEY", "audio-secret, rotated-secret")
    monkeypatch.setenv("AUDIODOC_DOCUMENT_KEY", "document-secret")
    caplog.set_level(logging.WARNING, logger="audiodoc.cli")

    assert (
        cli.main(
            [
                "run",
                "--host",
                all_interfaces_host,
                "--port",
                "8123",
                "--env-file",
                str(env_file),
            ]
        )
        == 0
    )

    assert calls == [
        ("env", env_file),
        (
            "logging",
            ("DEBUG", ("audio-secret", "rotated-secret", "document-secret")),
        ),
        (
            "uvicorn",
            (
                "audiodoc.main:create_app",
                {
                    "factory": True,
                    "host": all_interfaces_host,
                    "port": 8123,
                    "server_header": False,
                },
            ),
        ),
    ]
    security_warning = "SECURITY WARNING"
    assert security_warning in caplog.text
    assert all_interfaces_host in caplog.text


def test_run_defaults_to_loopback_and_port_8000(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.delenv("AUDIODOC_HOST", raising=False)
    monkeypatch.delenv("AUDIODOC_PORT", raising=False)

    def record_uvicorn(_application: str, **kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(run_command, "load_env_file", lambda _path=None: None)
    monkeypatch.setattr(run_command, "configure_logging", lambda _level, _secrets: None)
    monkeypatch.setattr(uvicorn, "run", record_uvicorn)

    assert cli.main(["run"]) == 0
    assert calls == [
        {
            "factory": True,
            "host": "127.0.0.1",
            "port": 8000,
            "server_header": False,
        }
    ]


def test_run_uses_bind_defaults_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setenv("AUDIODOC_HOST", "10.8.0.1")
    monkeypatch.setenv("AUDIODOC_PORT", "8123")
    monkeypatch.setattr(run_command, "load_env_file", lambda _path=None: None)
    monkeypatch.setattr(run_command, "configure_logging", lambda _level, _secrets: None)
    monkeypatch.setattr(
        uvicorn,
        "run",
        lambda _application, **kwargs: calls.append(kwargs),
    )

    assert cli.main(["run"]) == 0
    expected_host = "10.8.0.1"
    assert calls[0]["host"] == expected_host
    expected_port = 8123
    assert calls[0]["port"] == expected_port


def test_run_loads_environment_before_running_uvicorn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    def record_settings(_environ: object) -> object:
        calls.append("settings")
        return Settings()

    def record_uvicorn(application: object, **kwargs: object) -> None:
        calls.append((application, kwargs))

    monkeypatch.setattr(
        run_command, "load_env_file", lambda _env_file=None: calls.append("environment")
    )
    monkeypatch.setattr(run_command, "load_settings", record_settings)
    monkeypatch.setattr(
        run_command,
        "configure_logging",
        lambda _level, _secrets: calls.append("logging"),
    )
    monkeypatch.setattr(uvicorn, "run", record_uvicorn)

    assert cli.main(["run"]) == 0

    assert calls == [
        "environment",
        "settings",
        "logging",
        (
            "audiodoc.main:create_app",
            {
                "factory": True,
                "host": "127.0.0.1",
                "port": 8000,
                "server_header": False,
            },
        ),
    ]


@pytest.mark.parametrize("host", ["0", "::0", "0:0:0:0:0:0:0:0", "000.0"])
def test_run_warns_about_every_all_interfaces_spelling(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    host: str,
) -> None:
    monkeypatch.setenv("AUDIODOC_HOST", host)
    monkeypatch.setattr(run_command, "load_env_file", lambda _path=None: None)
    monkeypatch.setattr(run_command, "configure_logging", lambda _level, _secrets: None)
    monkeypatch.setattr(uvicorn, "run", lambda _application, **_kwargs: None)
    caplog.set_level(logging.WARNING, logger="audiodoc.cli")

    cli.main(["run"])

    expected_warning = (
        f"SECURITY WARNING: Binding to {host} exposes audiodoc on all network "
        "interfaces. Ensure API keys and firewall rules are configured."
    )
    assert caplog.messages == [expected_warning], "all-interfaces bind not warned"


@pytest.mark.parametrize("host", ["10.8.0.17", "fd00::5e", "audiodoc.lan"])
def test_run_does_not_warn_about_a_specific_address(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    host: str,
) -> None:
    monkeypatch.setenv("AUDIODOC_HOST", host)
    monkeypatch.setattr(run_command, "load_env_file", lambda _path=None: None)
    monkeypatch.setattr(run_command, "configure_logging", lambda _level, _secrets: None)
    monkeypatch.setattr(uvicorn, "run", lambda _application, **_kwargs: None)
    caplog.set_level(logging.WARNING, logger="audiodoc.cli")

    cli.main(["run"])

    expected_empty: list[str] = []
    assert caplog.messages == expected_empty, "specific bind address was warned"
