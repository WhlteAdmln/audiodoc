# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the service command."""

from pathlib import Path

import pytest

from audiodoc import cli
from audiodoc.service import render_service_unit


@pytest.fixture(name="user_service_paths")
def fixture_user_service_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path]:
    """Point HOME and AUDIODOC_HOME at temporary folders and return the paths."""
    user_home = tmp_path / "user"
    app_home = tmp_path / "application"
    monkeypatch.setenv("HOME", str(user_home))
    monkeypatch.setenv("AUDIODOC_HOME", str(app_home))
    return app_home, user_home / ".config/systemd/user/audiodoc.service"


def test_prints_user_unit_without_installing_it(
    user_service_paths: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    app_home, unit_path = user_service_paths

    exit_code = cli.main(["service", "install", "--print"])

    expected = (0, render_service_unit(app_home, mode="user"), False)
    actual = (exit_code, capsys.readouterr().out, unit_path.exists())
    assert actual == expected, "--print must print the unit and install nothing"


def test_installs_user_unit(
    user_service_paths: tuple[Path, Path],
) -> None:
    app_home, unit_path = user_service_paths

    exit_code = cli.main(["service", "install"])

    expected = (0, render_service_unit(app_home, mode="user"))
    actual = (exit_code, unit_path.read_text(encoding="utf-8"))
    assert actual == expected, "the user unit was not installed"


@pytest.mark.usefixtures("user_service_paths")
@pytest.mark.parametrize(
    "expected_line",
    [
        "The service was not enabled or started.",
        "systemctl --user enable --now audiodoc.service",
    ],
)
def test_installs_user_unit_without_starting_it(
    capsys: pytest.CaptureFixture[str],
    expected_line: str,
) -> None:
    cli.main(["service", "install"])

    output = capsys.readouterr().out

    assert expected_line in output, f"the install output lacks {expected_line!r}"


def test_prints_hardened_system_unit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "audiodoc"
    monkeypatch.setenv("AUDIODOC_HOME", str(home))

    exit_code = cli.main(["service", "install", "--system", "--print"])

    expected = (0, render_service_unit(home, mode="system"))
    actual = (exit_code, capsys.readouterr().out)
    assert actual == expected, "the hardened system unit was not printed"
