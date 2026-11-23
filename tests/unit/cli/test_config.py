# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the config command."""

import pytest

from audiodoc import cli
from audiodoc.cli import config as config_command


def test_config_check_reports_valid_configuration(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(config_command, "load_env_file", lambda _path=None: None)
    monkeypatch.setenv("ALLOW_UNAUTHENTICATED", "true")
    for name in ("AUDIODOC_AUDIO_KEY", "AUDIODOC_DOCUMENT_KEY"):
        monkeypatch.delenv(name, raising=False)

    assert cli.main(["config", "check"]) == 0
    expected_out = "Configuration is valid.\n"
    assert capsys.readouterr().out == expected_out


def test_config_check_collects_problems_without_printing_secrets(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(config_command, "load_env_file", lambda _path=None: None)
    monkeypatch.setenv("AUDIODOC_AUDIO_KEY", "audio-secret")
    monkeypatch.setenv("WHISPER_CPU_THREADS", "secret-value")
    monkeypatch.setenv("WHISPER_OFFLINE", "sometimes")
    monkeypatch.setenv("MAX_AUDIO_SIZE", "0")
    monkeypatch.setenv("ALLOW_UNAUTHENTICATED", "invalid-secret-value")
    monkeypatch.setenv("LOG_LEVEL", "secret-log-level")
    monkeypatch.delenv("AUDIODOC_DOCUMENT_KEY", raising=False)

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
