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


def _custom_run_arguments(host: str, env_file: Path) -> list[str]:
    return ["run", "--host", host, "--port", "8123", "--env-file", str(env_file)]


@pytest.fixture(name="configured_calls")
def fixture_configured_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, object]]:
    """Record environment, logging and uvicorn calls with secrets configured."""
    calls: list[tuple[str, object]] = []

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
    return calls


@pytest.fixture(name="uvicorn_kwargs")
def fixture_uvicorn_kwargs(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    """Record the keyword arguments of uvicorn runs without side effects."""
    calls: list[dict[str, object]] = []

    def record_uvicorn(_application: str, **kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(run_command, "load_env_file", lambda _path=None: None)
    monkeypatch.setattr(run_command, "configure_logging", lambda _level, _secrets: None)
    monkeypatch.setattr(uvicorn, "run", record_uvicorn)
    return calls


@pytest.fixture(name="ordered_calls")
def fixture_ordered_calls(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """Record the order of environment, settings, logging and uvicorn calls."""
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
    return calls


def test_run_loads_configuration_and_starts_uvicorn(
    configured_calls: list[tuple[str, object]],
    tmp_path: Path,
) -> None:
    env_file = tmp_path / "custom.env"
    all_interfaces_host = str(IPv4Address(0))

    cli.main(_custom_run_arguments(all_interfaces_host, env_file))

    expected_calls = [
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
    assert configured_calls == expected_calls, "wrong configuration or uvicorn calls"


@pytest.mark.usefixtures("configured_calls")
def test_run_returns_zero_after_starting_uvicorn_with_options(tmp_path: Path) -> None:
    env_file = tmp_path / "options.env"

    exit_code = cli.main(_custom_run_arguments(str(IPv4Address(0)), env_file))

    expected_code = 0
    assert exit_code == expected_code, "the run command did not succeed"


@pytest.mark.usefixtures("configured_calls")
def test_run_warns_about_all_interfaces_host_option(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    env_file = tmp_path / "warned.env"
    all_interfaces_host = str(IPv4Address(0))
    caplog.set_level(logging.WARNING, logger="audiodoc.cli")

    cli.main(_custom_run_arguments(all_interfaces_host, env_file))

    expected_warning = f"SECURITY WARNING: Binding to {all_interfaces_host} "
    assert expected_warning in caplog.text, "all-interfaces host option not warned"


def test_run_defaults_to_loopback_and_port_8000(
    monkeypatch: pytest.MonkeyPatch,
    uvicorn_kwargs: list[dict[str, object]],
) -> None:
    monkeypatch.delenv("AUDIODOC_HOST", raising=False)
    monkeypatch.delenv("AUDIODOC_PORT", raising=False)

    cli.main(["run"])

    expected_kwargs = [
        {
            "factory": True,
            "host": "127.0.0.1",
            "port": 8000,
            "server_header": False,
        }
    ]
    assert uvicorn_kwargs == expected_kwargs, "wrong default uvicorn arguments"


def test_run_uses_bind_defaults_from_environment(
    monkeypatch: pytest.MonkeyPatch,
    uvicorn_kwargs: list[dict[str, object]],
) -> None:
    monkeypatch.setenv("AUDIODOC_HOST", "10.8.0.1")
    monkeypatch.setenv("AUDIODOC_PORT", "8123")

    cli.main(["run"])

    expected_bind = [("10.8.0.1", 8123)]
    actual_bind = [(kwargs["host"], kwargs["port"]) for kwargs in uvicorn_kwargs]
    assert actual_bind == expected_bind, "the environment bind was not used"


@pytest.mark.parametrize(
    "bind_environment",
    [{}, {"AUDIODOC_HOST": "10.8.0.1", "AUDIODOC_PORT": "8123"}],
)
@pytest.mark.usefixtures("uvicorn_kwargs")
def test_run_returns_zero_after_starting_uvicorn(
    monkeypatch: pytest.MonkeyPatch,
    bind_environment: dict[str, str],
) -> None:
    monkeypatch.delenv("AUDIODOC_HOST", raising=False)
    monkeypatch.delenv("AUDIODOC_PORT", raising=False)
    for name, value in bind_environment.items():
        monkeypatch.setenv(name, value)

    exit_code = cli.main(["run"])

    expected_code = 0
    assert exit_code == expected_code, "the run command did not succeed"


def test_run_loads_environment_before_running_uvicorn(
    ordered_calls: list[object],
) -> None:
    cli.main(["run"])

    expected_calls = [
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
    assert ordered_calls == expected_calls, "wrong order of startup calls"


@pytest.mark.usefixtures("ordered_calls")
def test_run_returns_zero_after_ordered_startup() -> None:
    exit_code = cli.main(["run"])

    expected_code = 0
    assert exit_code == expected_code, "the run command did not succeed"


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
