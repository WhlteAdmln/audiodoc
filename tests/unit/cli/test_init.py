# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the init command."""

from pathlib import Path

import pytest

from audiodoc import cli


def _read_env_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        separator = "="
        if line and not line.lstrip().startswith("#") and separator in line:
            name, value = line.split("=", 1)
            values[name] = value
    return values


def test_init_writes_distinct_keys_and_secure_configuration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("AUDIODOC_HOME", str(home))

    assert (
        cli.main(
            [
                "init",
                "--model",
                "medium",
                "--device",
                "cuda",
                "--host",
                "10.8.0.1",
                "--port",
                "8123",
            ]
        )
        == 0
    )

    env_path = home / ".env"
    values = _read_env_values(env_path)
    audio_key = values["AUDIODOC_AUDIO_KEY"]
    document_key = values["AUDIODOC_DOCUMENT_KEY"]

    expected_count = 43
    assert len(audio_key) >= expected_count
    expected_count = 43
    assert len(document_key) >= expected_count
    assert audio_key != document_key
    expected_number = 0o600
    assert env_path.stat().st_mode & 0o777 == expected_number
    expected_whisper_model_size = "medium"
    assert values["WHISPER_MODEL_SIZE"] == expected_whisper_model_size
    expected_whisper_device = "cuda"
    assert values["WHISPER_DEVICE"] == expected_whisper_device
    expected_whisper_compute_type = "float16"
    assert values["WHISPER_COMPUTE_TYPE"] == expected_whisper_compute_type
    expected_audiodoc_host = "10.8.0.1"
    assert values["AUDIODOC_HOST"] == expected_audiodoc_host
    expected_audiodoc_port = "8123"
    assert values["AUDIODOC_PORT"] == expected_audiodoc_port
    expected_allow_unauthenticated = "false"
    assert values["ALLOW_UNAUTHENTICATED"] == expected_allow_unauthenticated


def test_init_refuses_to_overwrite_without_force_and_force_replaces(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("AUDIODOC_HOME", str(home))

    assert cli.main(["init"]) == 0
    env_path = home / ".env"
    original = env_path.read_bytes()
    original_values = _read_env_values(env_path)

    with pytest.raises(SystemExit) as error:
        cli.main(["init"])

    expected_code = 2
    assert error.value.code == expected_code
    assert env_path.read_bytes() == original

    assert cli.main(["init", "--force"]) == 0
    replacement_values = _read_env_values(env_path)
    assert (
        replacement_values["AUDIODOC_AUDIO_KEY"]
        != original_values["AUDIODOC_AUDIO_KEY"]
    )
    assert (
        replacement_values["AUDIODOC_DOCUMENT_KEY"]
        != original_values["AUDIODOC_DOCUMENT_KEY"]
    )
