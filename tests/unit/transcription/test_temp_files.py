# Copyright (c) 2026 Nikolai Zelensky

"""Tests for transcription temp files."""

import asyncio
import os
import re
import time
import uuid
from pathlib import Path

import pytest

import audiodoc.transcription.temp_files as temp_audio
from audiodoc.config import settings


@pytest.fixture(name="private_dir")
def fixture_private_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point the temporary audio directory at a fresh path under tmp_path."""
    directory = tmp_path / "приватный tmp"
    monkeypatch.setattr(settings, "TEMP_DIR", str(directory))
    return directory


def _raise_during_temp_file(error_type: type[BaseException]) -> None:
    with temp_audio.temp_audio_file("voice.ogg") as path:
        path.write_bytes(b"audio")
        raise error_type


def _age(path: Path) -> None:
    old_time = time.time() - temp_audio.STALE_AFTER_SECONDS - 10
    os.utime(path, (old_time, old_time), follow_symlinks=False)


def test_temp_audio_file_stays_in_the_private_directory_for_a_traversal_name(
    private_dir: Path,
) -> None:
    with temp_audio.temp_audio_file("../../../etc/voice.ogg") as path:
        parent = path.parent

    assert parent == private_dir, "the original name must not choose the directory"


def test_temp_audio_file_has_a_random_name_and_the_original_suffix(
    private_dir: Path,
) -> None:
    with temp_audio.temp_audio_file("Запись 2026.ogg") as path:
        name = path.relative_to(private_dir).as_posix()

    assert re.fullmatch(r"[0-9a-f]{32}\.ogg", name) is not None, f"bad {name!r}"


def test_temp_audio_files_get_distinct_names(private_dir: Path) -> None:
    with (
        temp_audio.temp_audio_file("a.wav") as first,
        temp_audio.temp_audio_file("a.wav") as second,
    ):
        names = {first.name, second.name}

    expected_count = 2
    assert len(names) == expected_count, f"names collide in {private_dir}"


def test_temp_audio_file_exists_inside_the_context(private_dir: Path) -> None:
    with temp_audio.temp_audio_file("voice.mp3") as path:
        exists = path.is_file()

    assert exists is True, f"the file must be created in {private_dir}"


def test_temp_audio_file_is_readable_only_by_the_owner(private_dir: Path) -> None:
    with temp_audio.temp_audio_file("voice.flac") as path:
        mode = path.stat().st_mode & 0o777

    expected_mode = 0o600
    assert mode == expected_mode, f"a file in {private_dir} must be 0600"


def test_temp_audio_file_directory_is_private(private_dir: Path) -> None:
    with temp_audio.temp_audio_file("voice.ogg"):
        mode = private_dir.stat().st_mode & 0o777

    expected_mode = 0o700
    assert mode == expected_mode, "the temporary directory must be 0700"


def test_temp_audio_file_is_removed_after_the_context(private_dir: Path) -> None:
    with temp_audio.temp_audio_file("voice.ogg") as path:
        path.write_bytes(b"\x00audio")

    assert path.exists() is False, f"the file must not stay in {private_dir}"


@pytest.mark.parametrize(
    "error_type",
    [RuntimeError, asyncio.CancelledError, KeyboardInterrupt],
)
def test_temp_audio_file_is_removed_after_error_or_cancellation(
    private_dir: Path, error_type: type[BaseException]
) -> None:
    with pytest.raises(error_type):
        _raise_during_temp_file(error_type)

    expected_empty: list[Path] = []
    assert list(private_dir.iterdir()) == expected_empty, "no file may be left"


def test_temp_audio_file_tolerates_a_file_removed_by_the_caller(
    private_dir: Path,
) -> None:
    with temp_audio.temp_audio_file("voice.ogg") as path:
        path.unlink()

    expected_empty: list[Path] = []
    assert list(private_dir.iterdir()) == expected_empty, "cleanup must not fail"


@pytest.mark.parametrize(
    "original_name",
    ["voice.русский", "voice.ogg\\evil", "voice.og\x00g", "", ".bashrc", "voice"],
)
def test_temp_audio_file_drops_an_unsafe_or_missing_suffix(
    private_dir: Path, original_name: str
) -> None:
    with temp_audio.temp_audio_file(original_name) as path:
        suffix = path.suffix

    expected_empty = ""
    assert suffix == expected_empty, f"unexpected suffix in {private_dir}"


def test_temp_audio_file_shortens_a_long_suffix(private_dir: Path) -> None:
    with temp_audio.temp_audio_file("voice.abcdefghijklmnop") as path:
        suffix = path.suffix

    expected = ".abcdefghi"
    assert suffix == expected, f"the suffix in {private_dir} must be cut to 10"


@pytest.mark.parametrize(
    ("name", "stale", "kept"),
    [
        ("3f2a9c0d4b1e8f7a6c5d4e3f2a1b0c9d.ogg", True, False),
        ("0123456789abcdef0123456789abcdef", True, False),
        ("a1b2c3d4e5f60718293a4b5c6d7e8f90.wav", False, True),
        ("operator-notes.txt", True, True),
        ("3F2A9C0D4B1E8F7A6C5D4E3F2A1B0C9D.ogg", True, True),
        ("3f2a9c0d4b1e8f7a6c5d4e3f2a1b0c9.ogg", True, True),
        ("x3f2a9c0d4b1e8f7a6c5d4e3f2a1b0c9d.ogg", True, True),
    ],
)
def test_cleanup_stale_files_removes_only_old_managed_files(
    private_dir: Path, name: str, *, stale: bool, kept: bool
) -> None:
    private_dir.mkdir()
    path = private_dir / name
    path.write_bytes(b"OggS\x00\x02")
    if stale:
        _age(path)

    temp_audio.cleanup_stale_files()

    assert path.exists() is kept, f"wrong cleanup decision for {name!r}"


def test_cleanup_stale_files_ignores_symlinks_and_directories(
    private_dir: Path,
) -> None:
    private_dir.mkdir()
    target = private_dir / "operator-notes.txt"
    target.write_bytes(b"keep")
    link = private_dir / f"{uuid.uuid4().hex}.ogg"
    link.symlink_to(target)
    managed_directory = private_dir / uuid.uuid4().hex
    managed_directory.mkdir()
    for path in (target, link, managed_directory):
        _age(path)

    temp_audio.cleanup_stale_files()

    observed = (link.is_symlink(), managed_directory.is_dir(), target.read_bytes())
    expected = (True, True, b"keep")
    assert observed == expected, "links, their targets and directories must stay"


def test_cleanup_stale_files_continues_after_an_unlink_error(
    monkeypatch: pytest.MonkeyPatch, private_dir: Path
) -> None:
    private_dir.mkdir()
    locked = private_dir / f"{uuid.uuid4().hex}.ogg"
    removable = private_dir / f"{uuid.uuid4().hex}.wav"
    for path in (locked, removable):
        path.write_bytes(b"old")
        _age(path)
    original_unlink = Path.unlink

    def fail_for_locked(path: Path, *, missing_ok: bool = False) -> None:
        if path == locked:
            raise PermissionError(path)
        original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_for_locked)
    temp_audio.cleanup_stale_files()

    observed = (locked.exists(), removable.exists())
    expected = (True, False)
    assert observed == expected, "one failing file must not stop the cleanup"


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


@pytest.mark.parametrize("existing_mode", [0o755, 0o777, 0o500])
def test_ensure_temp_dir_restricts_permissions_of_existing_directory(
    private_dir: Path, existing_mode: int
) -> None:
    private_dir.mkdir()
    private_dir.chmod(existing_mode)

    mode = temp_audio.ensure_temp_dir().stat().st_mode & 0o777

    expected_mode = 0o700
    assert mode == expected_mode, "an existing directory must be tightened to 0700"
