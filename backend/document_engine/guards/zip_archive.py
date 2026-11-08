"""Проверка ZIP-контейнеров перед обработкой."""

import io
import zipfile

from backend.document_engine.limits import (
    MAX_ARCHIVE_COMPRESSION_RATIO,
    MAX_ARCHIVE_FILE_SIZE,
    MAX_ARCHIVE_FILES,
    MAX_ARCHIVE_UNPACKED_SIZE,
)


def validate_zip_archive(data: bytes) -> None:
    """Проверяет ZIP-архив на чрезмерный размер и подозрительное сжатие."""
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise ValueError("Некорректный ZIP-контейнер")

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            _validate_archive_entries(archive)

            # Проверяем CRC и фактическую целостность содержимого.
            bad_file = archive.testzip()
            if bad_file is not None:
                raise ValueError(f"Повреждён файл внутри архива: {bad_file}")

    except zipfile.BadZipFile as error:
        raise ValueError("Повреждён ZIP-архив") from error


def _validate_archive_entries(archive: zipfile.ZipFile) -> None:
    files = archive.infolist()
    if len(files) > MAX_ARCHIVE_FILES:
        raise ValueError(f"Слишком много файлов в архиве: {len(files)}")

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
        raise ValueError(f"Файл внутри архива слишком большой: {item.filename}")

    new_total_size = total_unpacked_size + item.file_size
    if new_total_size > MAX_ARCHIVE_UNPACKED_SIZE:
        raise ValueError("Превышен общий лимит распакованного размера архива")

    if item.file_size > 0:
        if item.compress_size == 0:
            raise ValueError(f"Подозрительный размер сжатого файла: {item.filename}")

        ratio = item.file_size / item.compress_size
        if ratio > MAX_ARCHIVE_COMPRESSION_RATIO:
            raise ValueError(f"Подозрительная степень сжатия: {item.filename}")

    return item.file_size
