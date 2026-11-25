# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the version command."""

import pytest

from audiodoc import cli
from audiodoc.cli import version as version_command


@pytest.fixture(name="installed_version")
def fixture_installed_version(monkeypatch: pytest.MonkeyPatch) -> str:
    """Report a fixed installed package version to the version command."""
    installed = "0.1.0"
    monkeypatch.setattr(version_command, "package_version", lambda _name: installed)
    return installed


@pytest.mark.usefixtures("installed_version")
def test_version_exits_successfully() -> None:
    expected_code = 0
    assert cli.main(["version"]) == expected_code, (
        "the version command must exit with code 0"
    )


@pytest.mark.usefixtures("installed_version")
def test_version_prints_installed_package_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli.main(["version"])

    expected_out = "audiodoc 0.1.0\n"
    assert capsys.readouterr().out == expected_out, (
        "the command must print the installed package version"
    )
