# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the version command."""

import pytest

from audiodoc import cli
from audiodoc.cli import version as version_command


def test_version_prints_installed_package_version(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(version_command, "package_version", lambda _name: "0.1.0")

    assert cli.main(["version"]) == 0
    expected_out = "audiodoc 0.1.0\n"
    assert capsys.readouterr().out == expected_out
