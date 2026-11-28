# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the model command."""

import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from audiodoc import cli
from audiodoc.transcription.model_revisions import (
    MODEL_REVISIONS,
    InstalledModel,
    read_revision_marker,
    write_revision_marker,
)


@pytest.fixture(name="download_calls")
def fixture_download_calls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> list[tuple[str, str, str]]:
    """Point AUDIODOC_HOME into tmp_path and record calls to the model downloader."""
    monkeypatch.setenv("AUDIODOC_HOME", str(tmp_path / "home"))
    calls: list[tuple[str, str, str]] = []

    def fake_download_model(name: str, *, output_dir: str, revision: str) -> str:
        calls.append((name, output_dir, revision))
        return output_dir

    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda _name: SimpleNamespace(download_model=fake_download_model),
    )
    return calls


@pytest.fixture(name="failing_model_directory")
def fixture_failing_model_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Path:
    """Leave a stale marker in a model directory whose download fails."""
    model_directory = tmp_path / "stale-model"
    model_directory.mkdir()
    write_revision_marker(
        model_directory,
        InstalledModel("base.en", "3d3d5dee26484f91867d81cb899cfcf72b96be6c"),
    )

    def failing_download_model(_name: str, **_kwargs: str) -> str:
        message = "the model hub is unreachable"
        raise OSError(message)

    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda _name: SimpleNamespace(download_model=failing_download_model),
    )
    return model_directory


@pytest.mark.usefixtures("download_calls")
def test_model_download_exits_successfully() -> None:
    expected_code = 0
    assert cli.main(["model", "download"]) == expected_code, (
        "a successful download must exit with code 0"
    )


def test_model_download_uses_home_models_directory_and_pinned_revision(
    download_calls: list[tuple[str, str, str]],
    tmp_path: Path,
) -> None:
    cli.main(["model", "download"])

    expected_directory = tmp_path / "home" / "models" / "small"
    expected_calls = [("small", str(expected_directory), MODEL_REVISIONS["small"])]
    assert download_calls == expected_calls, (
        "the small model must be downloaded at its pinned revision "
        "into the home models directory"
    )


@pytest.mark.usefixtures("download_calls")
def test_model_download_creates_models_directory(tmp_path: Path) -> None:
    cli.main(["model", "download"])

    expected_directory = tmp_path / "home" / "models" / "small"
    assert expected_directory.is_dir(), "the model directory must be created"


@pytest.mark.usefixtures("download_calls")
def test_model_download_records_the_pinned_revision(tmp_path: Path) -> None:
    model_directory = tmp_path / "distil-model"
    cli.main(
        [
            "model",
            "download",
            "--name",
            "distil-large-v3",
            "--dir",
            str(model_directory),
        ]
    )

    expected = InstalledModel("distil-large-v3", MODEL_REVISIONS["distil-large-v3"])
    assert read_revision_marker(model_directory) == expected, (
        "a successful download must record the model name and pinned revision"
    )


def test_model_download_removes_stale_marker_when_download_fails(
    failing_model_directory: Path,
) -> None:
    with pytest.raises(OSError, match="unreachable"):
        cli.main(
            [
                "model",
                "download",
                "--name",
                "large-v2",
                "--dir",
                str(failing_model_directory),
            ]
        )

    assert read_revision_marker(failing_model_directory) is None, (
        "a failed download must not keep the revision of an earlier download"
    )


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
