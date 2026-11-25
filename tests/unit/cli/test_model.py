# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the model command."""

import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from audiodoc import cli


@pytest.fixture(name="download_calls")
def fixture_download_calls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> list[tuple[str, str]]:
    """Point AUDIODOC_HOME into tmp_path and record calls to the model downloader."""
    monkeypatch.setenv("AUDIODOC_HOME", str(tmp_path / "home"))
    calls: list[tuple[str, str]] = []

    def fake_download_model(name: str, *, output_dir: str) -> str:
        calls.append((name, output_dir))
        return output_dir

    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda _name: SimpleNamespace(download_model=fake_download_model),
    )
    return calls


@pytest.mark.usefixtures("download_calls")
def test_model_download_exits_successfully() -> None:
    expected_code = 0
    assert cli.main(["model", "download"]) == expected_code, (
        "a successful download must exit with code 0"
    )


def test_model_download_uses_home_models_directory(
    download_calls: list[tuple[str, str]],
    tmp_path: Path,
) -> None:
    cli.main(["model", "download"])

    expected_directory = tmp_path / "home" / "models" / "small"
    expected_calls = [("small", str(expected_directory))]
    assert download_calls == expected_calls, (
        "the small model must be downloaded into the home models directory"
    )


@pytest.mark.usefixtures("download_calls")
def test_model_download_creates_models_directory(tmp_path: Path) -> None:
    cli.main(["model", "download"])

    expected_directory = tmp_path / "home" / "models" / "small"
    assert expected_directory.is_dir(), "the model directory must be created"


@pytest.mark.usefixtures("download_calls")
def test_model_download_prints_model_directory(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli.main(["model", "download"])

    expected_directory = tmp_path / "home" / "models" / "small"
    expected_out = f"Model downloaded to: {expected_directory}\n"
    assert capsys.readouterr().out == expected_out, (
        "the command must print where the model was downloaded"
    )
