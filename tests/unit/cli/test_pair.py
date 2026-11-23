# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the pair command."""

from pathlib import Path

import pytest
from dotenv import dotenv_values

from audiodoc import cli


def test_pair_prints_exact_shared_settings_from_env_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("AUDIODOC_HOME", str(home))
    assert cli.main(["init"]) == 0
    capsys.readouterr()
    values = dotenv_values(home / ".env")
    monkeypatch.setenv("AUDIODOC_AUDIO_KEY", "environment-audio-key")
    monkeypatch.setenv("AUDIODOC_DOCUMENT_KEY", "environment-document-key")

    assert cli.main(["pair", "--url", "http://10.8.0.1:8000"]) == 0

    assert capsys.readouterr().out.splitlines() == [
        "AUDIODOC_URL=http://10.8.0.1:8000",
        f"AUDIODOC_AUDIO_KEY={values['AUDIODOC_AUDIO_KEY']}",
        f"AUDIODOC_DOCUMENT_KEY={values['AUDIODOC_DOCUMENT_KEY']}",
    ]


def test_pair_uses_host_and_port_from_env_when_url_is_omitted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("AUDIODOC_HOME", str(tmp_path / "home"))
    assert cli.main(["init", "--host", "10.8.0.1", "--port", "8123"]) == 0
    capsys.readouterr()

    assert cli.main(["pair"]) == 0
    output = capsys.readouterr().out
    expected_splitlines = "AUDIODOC_URL=http://10.8.0.1:8123"
    assert output.splitlines()[0] == expected_splitlines
    expected_count = 3
    assert len(output.splitlines()) == expected_count
