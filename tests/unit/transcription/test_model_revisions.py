# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the pinned Whisper model revisions and their marker file."""

import re
from pathlib import Path

import pytest

from audiodoc.transcription.model_revisions import (
    MODEL_REVISIONS,
    REVISION_MARKER_NAME,
    InstalledModel,
    read_revision_marker,
    remove_revision_marker,
    write_revision_marker,
)


@pytest.mark.parametrize("name", sorted(MODEL_REVISIONS))
def test_pins_each_model_to_a_commit_hash(name: str) -> None:
    commit_hash = re.compile(r"[0-9a-f]{40}")
    assert commit_hash.fullmatch(MODEL_REVISIONS[name]), (
        f"model {name!r} must be pinned to a full commit hash"
    )


def test_reads_the_written_marker(tmp_path: Path) -> None:
    model = InstalledModel("medium.en", "a29b04bd15381511a9af671baec01072039215e3")
    write_revision_marker(tmp_path, model)

    assert read_revision_marker(tmp_path) == model, (
        "the marker must return the recorded name and revision"
    )


def test_returns_none_without_a_marker(tmp_path: Path) -> None:
    assert read_revision_marker(tmp_path / "no-model-here") is None, (
        "a directory without a marker must have no recorded revision"
    )


@pytest.mark.parametrize(
    "content",
    [
        "{not json",
        '["tiny", "d90ca5fe"]',
        '{"name": "base"}',
        '{"name": 7, "revision": "ebe41f70"}',
        '{"name": "large-v2", "revision": null}',
    ],
)
def test_returns_none_for_an_invalid_marker(tmp_path: Path, content: str) -> None:
    (tmp_path / REVISION_MARKER_NAME).write_text(content, encoding="utf-8")

    assert read_revision_marker(tmp_path) is None, (
        f"an invalid marker must have no recorded revision: {content}"
    )


def test_removes_the_marker(tmp_path: Path) -> None:
    write_revision_marker(
        tmp_path, InstalledModel("tiny.en", "0d3d19a32d3338f10357c0889762bd8d64bbdeba")
    )

    remove_revision_marker(tmp_path)

    assert not (tmp_path / REVISION_MARKER_NAME).exists(), (
        "the marker file must be removed"
    )
