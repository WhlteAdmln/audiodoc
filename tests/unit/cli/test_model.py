# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the model command."""

import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from audiodoc import cli


def test_model_download_uses_home_models_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("AUDIODOC_HOME", str(home))
    calls: list[tuple[str, str]] = []

    def fake_download_model(name: str, *, output_dir: str) -> str:
        calls.append((name, output_dir))
        return output_dir

    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda _name: SimpleNamespace(download_model=fake_download_model),
    )

    assert cli.main(["model", "download"]) == 0
    expected_directory = home / "models" / "small"
    assert calls == [("small", str(expected_directory))]
    assert expected_directory.is_dir()
    assert capsys.readouterr().out == f"Model downloaded to: {expected_directory}\n"
