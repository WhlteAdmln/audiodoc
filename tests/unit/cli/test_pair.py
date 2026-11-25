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
    init_code = cli.main(["init"])
    capsys.readouterr()
    values = dotenv_values(home / ".env")
    monkeypatch.setenv("AUDIODOC_AUDIO_KEY", "environment-audio-key")
    monkeypatch.setenv("AUDIODOC_DOCUMENT_KEY", "environment-document-key")

    pair_code = cli.main(["pair", "--url", "http://10.8.0.1:8000"])

    actual = (init_code, pair_code, capsys.readouterr().out.splitlines())
    expected = (
        0,
        0,
        [
            "AUDIODOC_URL=http://10.8.0.1:8000",
            f"AUDIODOC_AUDIO_KEY={values['AUDIODOC_AUDIO_KEY']}",
            f"AUDIODOC_DOCUMENT_KEY={values['AUDIODOC_DOCUMENT_KEY']}",
        ],
    )
    assert actual == expected, "pair must print the settings of the env file"


def test_pair_uses_host_and_port_from_env_when_url_is_omitted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("AUDIODOC_HOME", str(tmp_path / "home"))
    init_code = cli.main(["init", "--host", "10.8.0.1", "--port", "8123"])
    capsys.readouterr()

    pair_code = cli.main(["pair"])
    lines = capsys.readouterr().out.splitlines()

    actual = (init_code, pair_code, lines[0], len(lines))
    expected = (0, 0, "AUDIODOC_URL=http://10.8.0.1:8123", 3)
    assert actual == expected, "pair must build the URL from the env host and port"


@pytest.mark.parametrize(
    ("host", "port"),
    [("0", "8417"), ("::0", "9031"), ("0:0:0:0:0:0:0:0", "8662"), ("::", "8209")],
)
def test_pair_renders_every_all_interfaces_spelling_as_loopback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    host: str,
    port: str,
) -> None:
    monkeypatch.setenv("AUDIODOC_HOME", str(tmp_path / "home"))
    cli.main(["init", "--host", host, "--port", port])
    capsys.readouterr()

    cli.main(["pair"])

    expected_url = f"AUDIODOC_URL=http://127.0.0.1:{port}"
    assert capsys.readouterr().out.splitlines()[0] == expected_url, "wrong pair URL"
