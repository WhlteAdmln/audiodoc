# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the python -m audiodoc entry point."""

import runpy
from pathlib import Path

import pytest

from audiodoc import cli


def test_invokes_cli_main_and_exits_with_its_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry_point = Path(__file__).resolve().parents[2] / "audiodoc" / "__main__.py"
    monkeypatch.setattr(cli, "main", lambda: 7)

    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(entry_point), run_name="__main__")

    expected_code = 7
    assert error.value.code == expected_code
