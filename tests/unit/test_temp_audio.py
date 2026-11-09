# Copyright (c) 2026 Nikolai Zelensky
import asyncio
import os
import time
import uuid
from pathlib import Path

import pytest

import backend.transcription.temp_files as temp_audio


def test_temp_audio_file_is_private_and_removed(monkeypatch, tmp_path):
    monkeypatch.setattr(temp_audio, "TEMP_DIR", tmp_path / "private")
    with temp_audio.temp_audio_file("../../voice.ogg") as path:
        path.write_bytes(b"audio")
        assert path.parent == tmp_path / "private"
        assert path.suffix == ".ogg"
        assert path.exists()
        assert path.parent.stat().st_mode & 0o777 == 0o700
        if os.name == "posix":
            assert path.stat().st_mode & 0o777 == 0o600
    assert not path.exists()


def _raise_during_temp_file(error_type: type[BaseException]) -> None:
    with temp_audio.temp_audio_file("voice.ogg") as path:
        path.write_bytes(b"audio")
        raise error_type


@pytest.mark.parametrize(
    "error_type",
    [RuntimeError, asyncio.CancelledError],
)
def test_temp_audio_file_is_removed_after_error_or_cancellation(
    monkeypatch, tmp_path, error_type
):
    monkeypatch.setattr(temp_audio, "TEMP_DIR", tmp_path / "private")

    with pytest.raises(error_type):
        _raise_during_temp_file(error_type)

    assert list((tmp_path / "private").iterdir()) == []


@pytest.mark.parametrize(
    "original_name",
    ["voice.русский", "voice.ogg\\evil"],
)
def test_temp_audio_file_discards_unsafe_suffix(monkeypatch, tmp_path, original_name):
    monkeypatch.setattr(temp_audio, "TEMP_DIR", tmp_path / "private")

    with temp_audio.temp_audio_file(original_name) as path:
        assert path.suffix == ""


def test_cleanup_stale_files_removes_only_old_managed_files(monkeypatch, tmp_path):
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

    monkeypatch.setattr(temp_audio, "TEMP_DIR", directory)
    temp_audio.cleanup_stale_files()

    assert not stale.exists()
    assert fresh.exists()
    assert unrelated.exists()


def test_blank_temp_dir_uses_private_project_default():
    assert temp_audio._resolve_temp_dir("") == temp_audio.DEFAULT_TEMP_DIR
    assert temp_audio._resolve_temp_dir(None) == temp_audio.DEFAULT_TEMP_DIR


def test_configured_temp_dir_is_expanded():
    assert temp_audio._resolve_temp_dir("~/audiodoc-private") == (
        Path("~/audiodoc-private").expanduser()
    )


def test_ensure_temp_dir_restricts_permissions_of_existing_directory(
    monkeypatch, tmp_path
):
    directory = tmp_path / "private"
    directory.mkdir()
    directory.chmod(0o755)
    monkeypatch.setattr(temp_audio, "TEMP_DIR", directory)

    result = temp_audio.ensure_temp_dir()

    assert result == directory
    if os.name == "posix":
        assert directory.stat().st_mode & 0o777 == 0o700


def test_cleanup_stale_files_ignores_symlinks_and_directories(monkeypatch, tmp_path):
    directory = tmp_path / "private"
    directory.mkdir()
    target = directory / "operator-notes.txt"
    target.write_bytes(b"keep")
    link = directory / f"{uuid.uuid4().hex}.ogg"
    link.symlink_to(target)
    managed_directory = directory / uuid.uuid4().hex
    managed_directory.mkdir()
    monkeypatch.setattr(temp_audio, "TEMP_DIR", directory)

    temp_audio.cleanup_stale_files()

    assert link.is_symlink()
    assert managed_directory.is_dir()
    assert target.read_bytes() == b"keep"


def test_cleanup_stale_files_ignores_unlink_errors(monkeypatch, tmp_path):
    directory = tmp_path / "private"
    directory.mkdir()
    stale = directory / f"{uuid.uuid4().hex}.ogg"
    stale.write_bytes(b"old")
    old_time = time.time() - temp_audio.STALE_AFTER_SECONDS - 10
    os.utime(stale, (old_time, old_time))
    monkeypatch.setattr(temp_audio, "TEMP_DIR", directory)

    original_unlink = Path.unlink

    def fail_stale_unlink(path: Path, *, missing_ok: bool = False) -> None:
        if path == stale:
            raise OSError
        original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_stale_unlink)
    temp_audio.cleanup_stale_files()

    assert stale.exists()
