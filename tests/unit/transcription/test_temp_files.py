# Copyright (c) 2026 Nikolai Zelensky

"""Tests for transcription temp files."""

import asyncio
import os
import time
import uuid
from pathlib import Path

import pytest

import audiodoc.transcription.temp_files as temp_audio
from audiodoc.config import settings


def _raise_during_temp_file(error_type: type[BaseException]) -> None:
    with temp_audio.temp_audio_file("voice.ogg") as path:
        path.write_bytes(b"audio")
        raise error_type


def test_temp_audio_file_is_private_and_removed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "TEMP_DIR", str(tmp_path / "private"))
    with temp_audio.temp_audio_file("../../voice.ogg") as path:
        path.write_bytes(b"audio")
        assert path.parent == tmp_path / "private"
        expected_suffix = ".ogg"
        assert path.suffix == expected_suffix
        assert path.exists()
        expected_number = 0o700
        assert path.parent.stat().st_mode & 0o777 == expected_number
        expected_name = "posix"
        if os.name == expected_name:
            expected_number = 0o600
            assert path.stat().st_mode & 0o777 == expected_number
    assert not path.exists()


@pytest.mark.parametrize(
    "error_type",
    [RuntimeError, asyncio.CancelledError],
)
def test_temp_audio_file_is_removed_after_error_or_cancellation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, error_type: object
) -> None:
    monkeypatch.setattr(settings, "TEMP_DIR", str(tmp_path / "private"))

    with pytest.raises(error_type):
        _raise_during_temp_file(error_type)

    expected_empty = []
    assert list((tmp_path / "private").iterdir()) == expected_empty, (
        "expected an empty list"
    )


@pytest.mark.parametrize(
    "original_name",
    ["voice.русский", "voice.ogg\\evil"],
)
def test_temp_audio_file_discards_unsafe_suffix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, original_name: str
) -> None:
    monkeypatch.setattr(settings, "TEMP_DIR", str(tmp_path / "private"))

    with temp_audio.temp_audio_file(original_name) as path:
        expected_empty = ""
        assert path.suffix == expected_empty, "expected an empty string"


def test_cleanup_stale_files_removes_only_old_managed_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    directory = tmp_path / "private"
    directory.mkdir()
    stale = directory / f"{uuid.uuid4().hex}.ogg"
    fresh = directory / f"{uuid.uuid4().hex}.ogg"
    unrelated = directory / "operator-notes.txt"
    stale.write_bytes(b"old")
    fresh.write_bytes(b"new")
    unrelated.write_bytes(b"keep")
    old_time = time.time() - temp_audio.STALE_AFTER_SECONDS - 10
    os.utime(stale, (old_time, old_time))

    monkeypatch.setattr(settings, "TEMP_DIR", str(directory))
    temp_audio.cleanup_stale_files()

    assert not stale.exists()
    assert fresh.exists()
    assert unrelated.exists()


def test_blank_temp_dir_uses_private_project_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / "дом аудио"
    monkeypatch.setenv("AUDIODOC_HOME", str(home))
    monkeypatch.setattr(settings, "TEMP_DIR", "  \t ")
    expected = home / "tmp"
    assert temp_audio.temp_dir() == expected, "a blank setting must use the default"


def test_relative_temp_dir_resolves_under_application_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / "home-7"
    monkeypatch.setenv("AUDIODOC_HOME", str(home))
    monkeypatch.setattr(settings, "TEMP_DIR", "cache/../audio tmp")
    expected = home / "cache/../audio tmp"
    assert temp_audio.temp_dir() == expected, "a relative path must sit under home"


def test_configured_temp_dir_is_expanded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "TEMP_DIR", "~/audiodoc-private")
    expected = Path("~/audiodoc-private").expanduser()
    assert temp_audio.temp_dir() == expected, "a leading tilde must be expanded"


def test_temp_dir_follows_settings_changed_after_import(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    configured = tmp_path / "late" / "audio"
    monkeypatch.setattr(settings, "TEMP_DIR", str(configured))
    assert temp_audio.ensure_temp_dir() == configured, (
        "the directory must be resolved when it is used, not at import"
    )


def test_ensure_temp_dir_restricts_permissions_of_existing_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    directory = tmp_path / "private"
    directory.mkdir()
    directory.chmod(0o755)
    monkeypatch.setattr(settings, "TEMP_DIR", str(directory))

    result = temp_audio.ensure_temp_dir()

    assert result == directory
    expected_name = "posix"
    if os.name == expected_name:
        expected_number = 0o700
        assert directory.stat().st_mode & 0o777 == expected_number


def test_cleanup_stale_files_ignores_symlinks_and_directories(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    directory = tmp_path / "private"
    directory.mkdir()
    target = directory / "operator-notes.txt"
    target.write_bytes(b"keep")
    link = directory / f"{uuid.uuid4().hex}.ogg"
    link.symlink_to(target)
    managed_directory = directory / uuid.uuid4().hex
    managed_directory.mkdir()
    monkeypatch.setattr(settings, "TEMP_DIR", str(directory))

    temp_audio.cleanup_stale_files()

    assert link.is_symlink()
    assert managed_directory.is_dir()
    expected_read_bytes = b"keep"
    assert target.read_bytes() == expected_read_bytes


def test_cleanup_stale_files_ignores_unlink_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    directory = tmp_path / "private"
    directory.mkdir()
    stale = directory / f"{uuid.uuid4().hex}.ogg"
    stale.write_bytes(b"old")
    old_time = time.time() - temp_audio.STALE_AFTER_SECONDS - 10
    os.utime(stale, (old_time, old_time))
    monkeypatch.setattr(settings, "TEMP_DIR", str(directory))

    original_unlink = Path.unlink

    def fail_stale_unlink(path: Path, *, missing_ok: bool = False) -> None:
        if path == stale:
            raise OSError
        original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_stale_unlink)
    temp_audio.cleanup_stale_files()

    assert stale.exists()
