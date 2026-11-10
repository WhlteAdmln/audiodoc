# Copyright (c) 2026 Nikolai Zelensky
"""Command-line interface tests."""

import logging
import runpy
from collections.abc import Iterable
from ipaddress import IPv4Address
from pathlib import Path

import pytest

from audiodoc import cli


def test_version_prints_installed_package_version(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "package_version", lambda _name: "0.1.0")

    assert cli.main(["version"]) == 0
    assert capsys.readouterr().out == "audiodoc 0.1.0\n"


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

    monkeypatch.setattr(cli, "load_env_file", record_env_file)
    monkeypatch.setattr(cli, "configure_logging", record_logging)
    monkeypatch.setattr(cli.uvicorn, "run", record_uvicorn)
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
    assert "SECURITY WARNING" in caplog.text
    assert all_interfaces_host in caplog.text


def test_run_defaults_to_loopback_and_port_8000(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def record_uvicorn(_application: str, **kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(cli, "load_env_file", lambda _path=None: None)
    monkeypatch.setattr(cli, "configure_logging", lambda _level, _secrets: None)
    monkeypatch.setattr(cli.uvicorn, "run", record_uvicorn)

    assert cli.main(["run"]) == 0
    assert calls == [
        {
            "factory": True,
            "host": "127.0.0.1",
            "port": 8000,
            "server_header": False,
        }
    ]


def test_config_check_reports_valid_configuration(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "load_env_file", lambda _path=None: None)
    monkeypatch.setenv("ALLOW_UNAUTHENTICATED", "true")
    for name in (
        "AUDIODOC_AUDIO_KEY",
        "AUDIODOC_DOCUMENT_KEY",
        "WHISPER_API_KEY",
        "DOCUMENT_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    assert cli.main(["config", "check"]) == 0
    assert capsys.readouterr().out == "Configuration is valid.\n"


def test_config_check_collects_problems_without_printing_secrets(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "load_env_file", lambda _path=None: None)
    monkeypatch.setenv("WHISPER_API_KEY", "audio-secret")
    monkeypatch.setenv("WHISPER_CPU_THREADS", "secret-value")
    monkeypatch.setenv("WHISPER_OFFLINE", "sometimes")
    monkeypatch.setenv("MAX_AUDIO_SIZE", "0")
    monkeypatch.setenv("ALLOW_UNAUTHENTICATED", "invalid-secret-value")
    monkeypatch.setenv("LOG_LEVEL", "secret-log-level")
    for name in ("AUDIODOC_AUDIO_KEY", "AUDIODOC_DOCUMENT_KEY", "DOCUMENT_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    assert cli.main(["config", "check"]) == 1
    output = capsys.readouterr().out

    for name in (
        "WHISPER_CPU_THREADS",
        "WHISPER_OFFLINE",
        "MAX_AUDIO_SIZE",
        "ALLOW_UNAUTHENTICATED",
        "AUDIODOC_DOCUMENT_KEY",
        "LOG_LEVEL",
    ):
        assert name in output

    for secret in (
        "audio-secret",
        "secret-value",
        "invalid-secret-value",
        "secret-log-level",
    ):
        assert secret not in output


def test_run_rejects_out_of_range_port(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(["run", "--port", "70000"])

    assert error.value.code == 2
    assert "between 1 and 65535" in capsys.readouterr().err


def test_python_module_entry_point_invokes_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry_point = Path(__file__).resolve().parents[2] / "audiodoc" / "__main__.py"
    monkeypatch.setattr(cli, "main", lambda: 7)

    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(entry_point), run_name="__main__")

    assert error.value.code == 7
