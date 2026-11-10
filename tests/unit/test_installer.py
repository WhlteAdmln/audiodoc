# Copyright (c) 2026 Nikolai Zelensky
"""Smoke tests for the POSIX release installer CLI."""

import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = PROJECT_ROOT / "install.sh"


def run_installer(*arguments: str) -> subprocess.CompletedProcess[str]:
    shell_path = shutil.which("sh")
    assert shell_path is not None, "A POSIX shell is required"

    return subprocess.run(  # noqa: S603 - resolved shell runs the local installer.
        [shell_path, str(INSTALLER), *arguments],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_installer_help_succeeds() -> None:
    result = run_installer("--help")

    assert result.returncode == 0
    assert "--latest" in result.stdout
    assert "--nightly" in result.stdout
    assert "--systemd" in result.stdout
    assert "--no-model" in result.stdout


def test_installer_rejects_invalid_port_before_installation() -> None:
    result = run_installer("--port", "65536")

    assert result.returncode != 0
    assert "Port must be an integer" in result.stderr


def test_installer_rejects_unsupported_device_before_installation() -> None:
    result = run_installer("--device", "gpu")

    assert result.returncode != 0
    assert "--device must be cpu or cuda" in result.stderr


def test_installer_rejects_unknown_model_before_installation() -> None:
    result = run_installer("--model", "made-up-model")

    assert result.returncode != 0
    assert "Unsupported Whisper model name" in result.stderr


def test_installer_rejects_invalid_host_before_installation() -> None:
    result = run_installer("--host", "0.0.0.0;touch /tmp/unsafe")

    assert result.returncode != 0
    assert "Invalid host address" in result.stderr


def test_installer_uses_shared_audiodoc_environment_names() -> None:
    source = INSTALLER.read_text(encoding="utf-8")

    assert '"AUDIODOC_AUDIO_KEY": key_whisper' in source
    assert '"AUDIODOC_DOCUMENT_KEY": key_document' in source
    assert 'f"AUDIODOC_URL={base_url}\\n"' in source
    assert 'f"AUDIODOC_AUDIO_KEY={key_whisper}\\n"' in source
    assert 'f"AUDIODOC_DOCUMENT_KEY={key_document}\\n"' in source
    assert '"WHISPER_API_KEY": key_whisper' not in source
    assert '"DOCUMENT_API_KEY": key_document' not in source
    assert "WHISPER_API_URL={base_url}" not in source
    assert "DOCUMENT_API_URL={base_url}" not in source
