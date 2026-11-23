# Copyright (c) 2026 Nikolai Zelensky

"""Tests for guards zip archive."""

from __future__ import annotations

import io
import zipfile

import pytest

from audiodoc.document_engine.detection import detect_format
from audiodoc.document_engine.guards import zip_archive as zip_guard
from audiodoc.document_engine.guards.zip_archive import validate_zip_archive
from tests.support.zip_archives import ZipMember, lying_zip


def test_zip_rejects_nonempty_member_with_zero_compressed_size() -> None:
    archive = lying_zip(
        [ZipMember("Отчёт.txt", b"z", declared_compress_size=0)],
    )
    with pytest.raises(ValueError, match="Suspicious compressed file size"):
        validate_zip_archive(archive)


def test_zip_rejects_member_larger_than_declared_size_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(zip_guard, "MAX_ARCHIVE_FILE_SIZE", 2)
    archive = lying_zip([ZipMember("ä/b.bin", b"\x00\xff\x10", declared_file_size=2)])
    with pytest.raises(ValueError, match="Actual ZIP member size exceeds the limit"):
        validate_zip_archive(archive)


def test_zip_rejects_members_whose_actual_total_exceeds_the_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(zip_guard, "MAX_ARCHIVE_UNPACKED_SIZE", 4)
    archive = lying_zip(
        [
            ZipMember("first.xml", b"<a/"),
            ZipMember("second.xml", b"\t\n", declared_file_size=1),
        ],
    )
    with pytest.raises(
        ValueError,
        match="Total unpacked archive size exceeds the limit",
    ):
        validate_zip_archive(archive)


def test_zip_rejects_member_that_inflates_beyond_the_ratio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(zip_guard, "MAX_ARCHIVE_COMPRESSION_RATIO", 1)
    archive = lying_zip(
        [
            ZipMember(
                "bomb.txt",
                b"Q" * 4096,
                compression=zipfile.ZIP_DEFLATED,
                declared_file_size=3,
            ),
        ],
    )
    with pytest.raises(ValueError, match="Actual ZIP compression ratio is too high"):
        validate_zip_archive(archive)


def test_mimetype_member_is_read_with_a_fixed_200_byte_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", b"0" * (4 * 1024 * 1024))

    original_read = zipfile.ZipExtFile.read
    requested_sizes = []

    def tracked_read(self: object, n: int = -1) -> object:
        requested_sizes.append(n)
        return original_read(self, n)

    monkeypatch.setattr(zipfile.ZipExtFile, "read", tracked_read)
    assert detect_format(output.getvalue(), "unknown.zip") is None
    assert requested_sizes == [200]


def test_validate_zip_archive_accepts_small_valid_archive() -> None:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("word/document.xml", "<document>safe</document>")

    validate_zip_archive(output.getvalue())


def test_validate_zip_archive_rejects_non_zip_data() -> None:
    with pytest.raises(ValueError, match="Invalid ZIP container"):
        validate_zip_archive(b"not a zip archive")
