# Copyright (c) 2026 Nikolai Zelensky
import os
import time
import uuid

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
