# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the config command."""

from pathlib import Path

import pytest

from audiodoc import cli

CHECKED_VARIABLES = (
    "AUDIODOC_AUDIO_KEY",
    "AUDIODOC_DOCUMENT_KEY",
    "ALLOW_UNAUTHENTICATED",
    "WHISPER_CPU_THREADS",
    "WHISPER_OFFLINE",
    "MAX_AUDIO_SIZE",
    "LOG_LEVEL",
)
HOSTILE_ENVIRONMENT = {
    "AUDIODOC_AUDIO_KEY": "audio-secret",
    "WHISPER_CPU_THREADS": "secret-value",
    "WHISPER_OFFLINE": "sometimes",
    "MAX_AUDIO_SIZE": "0",
    "ALLOW_UNAUTHENTICATED": "invalid-secret-value",
    "LOG_LEVEL": "secret-log-level\nConfiguration is valid.",
}


@pytest.fixture(name="home")
def fixture_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Isolate the command from real .env files and checked variables."""
    home = tmp_path / "home"
    home.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.setenv("AUDIODOC_HOME", str(home))
    for name in CHECKED_VARIABLES:
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)
    return home


def _check(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    environment: dict[str, str],
) -> tuple[int, str]:
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    code = cli.main(["config", "check"])
    return code, capsys.readouterr().out


@pytest.mark.usefixtures("home")
def test_config_check_reports_a_valid_configuration(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    result = _check(monkeypatch, capsys, {"ALLOW_UNAUTHENTICATED": "true"})

    expected = (0, "Configuration is valid.\n")
    assert result == expected, "a valid configuration must pass"


@pytest.mark.usefixtures("home")
def test_config_check_fails_on_problems(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, _output = _check(monkeypatch, capsys, HOSTILE_ENVIRONMENT)

    expected_code = 1
    assert code == expected_code, "problems must give exit code 1"


@pytest.mark.parametrize(
    "name",
    [
        "WHISPER_CPU_THREADS",
        "WHISPER_OFFLINE",
        "MAX_AUDIO_SIZE",
        "ALLOW_UNAUTHENTICATED",
        "AUDIODOC_DOCUMENT_KEY",
        "LOG_LEVEL",
    ],
)
@pytest.mark.usefixtures("home")
def test_config_check_names_every_problem(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], name: str
) -> None:
    _code, output = _check(monkeypatch, capsys, HOSTILE_ENVIRONMENT)

    assert name in output, f"{name} is missing from the report"


@pytest.mark.parametrize(
    "value",
    [
        "audio-secret",
        "secret-value",
        "invalid-secret-value",
        "secret-log-level",
        "Configuration is valid.",
    ],
)
@pytest.mark.usefixtures("home")
def test_config_check_never_prints_configured_values(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], value: str
) -> None:
    _code, output = _check(monkeypatch, capsys, HOSTILE_ENVIRONMENT)

    assert value not in output, "a configured value leaked into the report"


def test_config_check_reads_the_env_file_of_the_home(
    home: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (home / ".env").write_text(
        "ALLOW_UNAUTHENTICATED=true\nMAX_AUDIO_SIZE=-7\n", encoding="utf-8"
    )

    code, output = _check(monkeypatch, capsys, {})

    name = "MAX_AUDIO_SIZE"
    value = "-7"
    observed = (code, name in output, value in output)
    expected = (1, True, False)
    assert observed == expected, "the home .env must be checked without echoing it"
