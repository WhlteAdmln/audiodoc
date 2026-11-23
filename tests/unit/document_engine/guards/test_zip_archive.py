# Copyright (c) 2026 Nikolai Zelensky

"""Tests for guards zip archive."""

from __future__ import annotations

import io
import zipfile

import pytest

from audiodoc.document_engine.detection import detect_format
from audiodoc.document_engine.guards import zip_archive as zip_guard
from audiodoc.document_engine.guards.zip_archive import validate_zip_archive


def test_zip_rejects_nonempty_member_with_zero_compressed_size() -> None:
    item = zipfile.ZipInfo("member.bin")
    item.file_size = 1
    item.compress_size = 0

    with pytest.raises(ValueError, match="Suspicious compressed file size"):
        zip_guard._validate_archive_entry(item, 0)


@pytest.mark.parametrize(
    "case",
    [
        (
            "MAX_ARCHIVE_FILE_SIZE",
            2,
            3,
            0,
            10,
            "Actual ZIP member size exceeds the limit",
        ),
        (
            "MAX_ARCHIVE_UNPACKED_SIZE",
            4,
            2,
            3,
            10,
            "Total unpacked archive size exceeds the limit",
        ),
        (
            "MAX_ARCHIVE_COMPRESSION_RATIO",
            2,
            3,
            0,
            1,
            "Actual ZIP compression ratio is too high",
        ),
    ],
)
def test_zip_checks_actual_member_limits(
    case: tuple[str, int, int, int, int, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        limit_name,
        limit,
        actual_size,
        total_size,
        compressed_size,
        expected_message,
    ) = case
    monkeypatch.setattr(zip_guard, limit_name, limit)
    item = zipfile.ZipInfo("member.bin")
    item.compress_size = compressed_size

    with pytest.raises(ValueError, match=expected_message):
        zip_guard._validate_actual_member_size(item, actual_size, total_size)


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
