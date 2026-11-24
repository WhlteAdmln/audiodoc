# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the service command."""

from pathlib import Path

import pytest

from audiodoc import cli
from audiodoc.service import render_service_unit


def test_prints_and_installs_user_unit_without_starting_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    user_home = tmp_path / "user"
    app_home = tmp_path / "application"
    monkeypatch.setenv("HOME", str(user_home))
    monkeypatch.setenv("AUDIODOC_HOME", str(app_home))
    unit_path = user_home / ".config/systemd/user/audiodoc.service"

    assert cli.main(["service", "install", "--print"]) == 0
    assert capsys.readouterr().out == render_service_unit(app_home, mode="user")
    assert not unit_path.exists()
    assert cli.main(["service", "install"]) == 0
    assert unit_path.read_text(encoding="utf-8") == render_service_unit(
        app_home, mode="user"
    )
    output = capsys.readouterr().out
    not_started_notice = "The service was not enabled or started."
    assert not_started_notice in output
    enable_command = "systemctl --user enable --now audiodoc.service"
    assert enable_command in output


def test_prints_hardened_system_unit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "audiodoc"
    monkeypatch.setenv("AUDIODOC_HOME", str(home))
    assert cli.main(["service", "install", "--system", "--print"]) == 0
    assert capsys.readouterr().out == render_service_unit(home, mode="system")
