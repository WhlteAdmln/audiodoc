# Copyright (c) 2026 Nikolai Zelensky
"""Validate ZIP containers before processing untrusted documents."""

import copy
import io
import stat
import zipfile
import zlib
from pathlib import PureWindowsPath

from backend.document_engine.limits import (
    MAX_ARCHIVE_COMPRESSION_RATIO,
    MAX_ARCHIVE_FILE_SIZE,
    MAX_ARCHIVE_FILES,
    MAX_ARCHIVE_UNPACKED_SIZE,
    READ_CHUNK_SIZE,
)

_NESTED_ARCHIVE_SIGNATURES = (
    b"PK\x03\x04",
    b"PK\x05\x06",
    b"PK\x07\x08",
)


class _InvalidZipContainerError(ValueError):
    """Raised when the input is not a valid ZIP container."""

    def __init__(self) -> None:
        """Initialize the validation error."""
        super().__init__("Invalid ZIP container")


class _CorruptZipArchiveError(ValueError):
    """Raised when the ZIP archive is corrupted."""

    def __init__(self) -> None:
        """Initialize the validation error."""
        super().__init__("Corrupt ZIP archive")


class _ArchiveUnpackedSizeLimitError(ValueError):
    """Raised when the total unpacked archive size exceeds its limit."""

    def __init__(self) -> None:
        """Initialize the validation error."""
        super().__init__("Total unpacked archive size exceeds the limit")


def validate_zip_archive(data: bytes) -> None:
    """Validate ZIP entries, paths, sizes, compression, and integrity."""
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise _InvalidZipContainerError

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            _validate_archive_entries(archive)

    except (
        zipfile.BadZipFile,
        EOFError,
        OSError,
        RuntimeError,
        NotImplementedError,
        zlib.error,
    ) as error:
        raise _CorruptZipArchiveError from error


def _validate_archive_entries(archive: zipfile.ZipFile) -> None:
    files = archive.infolist()
    if len(files) > MAX_ARCHIVE_FILES:
        message = f"Too many files in archive: {len(files)}"
        raise ValueError(message)

    total_unpacked_size = 0
    for item in files:
        declared_size = _validate_archive_entry(item, total_unpacked_size)
        if item.is_dir():
            continue

        actual_size = _read_archive_member(
            archive,
            item,
            total_unpacked_size,
        )
        if actual_size != declared_size:
            message = f"Declared file size does not match actual size: {item.filename}"
            raise ValueError(message)

        total_unpacked_size += actual_size


def _validate_archive_entry(
    item: zipfile.ZipInfo,
    total_unpacked_size: int,
) -> int:
    original_name = item.orig_filename
    normalized_name = original_name.replace("\\", "/")

    if (
        not original_name
        or "\x00" in original_name
        or normalized_name.startswith("/")
        or PureWindowsPath(original_name).drive
        or ".." in normalized_name.split("/")
    ):
        message = f"Unsafe ZIP member path: {item.filename}"
        raise ValueError(message)

    if stat.S_ISLNK(item.external_attr >> 16):
        message = f"ZIP symbolic links are not allowed: {item.filename}"
        raise ValueError(message)

    if item.filename.lower().endswith(".zip"):
        message = f"Nested ZIP archives are not allowed: {item.filename}"
        raise ValueError(message)

    if item.is_dir():
        return 0

    if item.file_size > MAX_ARCHIVE_FILE_SIZE:
        message = f"File inside archive is too large: {item.filename}"
        raise ValueError(message)

    new_total_size = total_unpacked_size + item.file_size
    if new_total_size > MAX_ARCHIVE_UNPACKED_SIZE:
        raise _ArchiveUnpackedSizeLimitError

    if item.file_size > 0:
        if item.compress_size == 0:
            message = f"Suspicious compressed file size: {item.filename}"
            raise ValueError(message)

        ratio = item.file_size / item.compress_size
        if ratio > MAX_ARCHIVE_COMPRESSION_RATIO:
            message = f"Suspicious compression ratio: {item.filename}"
            raise ValueError(message)

    return item.file_size


def _read_archive_member(
    archive: zipfile.ZipFile,
    item: zipfile.ZipInfo,
    total_unpacked_size: int,
) -> int:
    """Read a member with an independent actual-size limit."""
    probe_info = copy.copy(item)
    probe_info.file_size = MAX_ARCHIVE_FILE_SIZE + 1
    actual_size = 0

    with archive.open(probe_info) as member:
        prefix = member.read(4)

        if prefix in _NESTED_ARCHIVE_SIGNATURES:
            message = f"Nested ZIP archive detected: {item.filename}"
            raise ValueError(message)

        actual_size = len(prefix)
        _validate_actual_member_size(item, actual_size, total_unpacked_size)

        while True:
            remaining = MAX_ARCHIVE_FILE_SIZE + 1 - actual_size
            chunk = member.read(min(READ_CHUNK_SIZE, remaining))
            if not chunk:
                break

            actual_size += len(chunk)
            _validate_actual_member_size(item, actual_size, total_unpacked_size)

    return actual_size


def _validate_actual_member_size(
    item: zipfile.ZipInfo,
    actual_size: int,
    total_unpacked_size: int,
) -> None:
    if actual_size > MAX_ARCHIVE_FILE_SIZE:
        message = f"Actual ZIP member size exceeds the limit: {item.filename}"
        raise ValueError(message)

    if total_unpacked_size + actual_size > MAX_ARCHIVE_UNPACKED_SIZE:
        raise _ArchiveUnpackedSizeLimitError

    if actual_size > item.compress_size * MAX_ARCHIVE_COMPRESSION_RATIO:
        message = f"Actual ZIP compression ratio is too high: {item.filename}"
        raise ValueError(message)
