# Copyright (c) 2026 Nikolai Zelensky
"""Проверка ZIP-контейнеров перед обработкой."""

import io
import zipfile

from backend.document_engine.limits import (
    MAX_ARCHIVE_COMPRESSION_RATIO,
    MAX_ARCHIVE_FILE_SIZE,
    MAX_ARCHIVE_FILES,
    MAX_ARCHIVE_UNPACKED_SIZE,
)


class _InvalidZipContainerError(ValueError):
    """Raised when the input is not a valid ZIP container."""

    def __init__(self) -> None:
        """Initialize the validation error."""
        super().__init__("Некорректный ZIP-контейнер")


class _CorruptZipArchiveError(ValueError):
    """Raised when the ZIP archive is corrupted."""

    def __init__(self) -> None:
        """Initialize the validation error."""
        super().__init__("Повреждён ZIP-архив")


class _ArchiveUnpackedSizeLimitError(ValueError):
    """Raised when the total unpacked archive size exceeds its limit."""

    def __init__(self) -> None:
        """Initialize the validation error."""
        super().__init__("Превышен общий лимит распакованного размера архива")


def validate_zip_archive(data: bytes) -> None:
    """Проверяет ZIP-архив на чрезмерный размер и подозрительное сжатие."""
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise _InvalidZipContainerError

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            _validate_archive_entries(archive)

            # Проверяем CRC и фактическую целостность содержимого.
            bad_file = archive.testzip()
            if bad_file is not None:
                message = f"Повреждён файл внутри архива: {bad_file}"
                raise ValueError(message)

    except zipfile.BadZipFile as error:
        raise _CorruptZipArchiveError from error


def _validate_archive_entries(archive: zipfile.ZipFile) -> None:
    files = archive.infolist()
    if len(files) > MAX_ARCHIVE_FILES:
        message = f"Слишком много файлов в архиве: {len(files)}"
        raise ValueError(message)

    total_unpacked_size = 0
    for item in files:
        total_unpacked_size += _validate_archive_entry(item, total_unpacked_size)


def _validate_archive_entry(
    item: zipfile.ZipInfo,
    total_unpacked_size: int,
) -> int:
    if item.is_dir():
        return 0

    if item.file_size > MAX_ARCHIVE_FILE_SIZE:
        message = f"Файл внутри архива слишком большой: {item.filename}"
        raise ValueError(message)

    new_total_size = total_unpacked_size + item.file_size
    if new_total_size > MAX_ARCHIVE_UNPACKED_SIZE:
        raise _ArchiveUnpackedSizeLimitError

    if item.file_size > 0:
        if item.compress_size == 0:
            message = f"Подозрительный размер сжатого файла: {item.filename}"
            raise ValueError(message)

        ratio = item.file_size / item.compress_size
        if ratio > MAX_ARCHIVE_COMPRESSION_RATIO:
            message = f"Подозрительная степень сжатия: {item.filename}"
            raise ValueError(message)

    return item.file_size
