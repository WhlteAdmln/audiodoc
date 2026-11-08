# Copyright (c) 2026 Nikolai Zelensky
"""Определение форматов ZIP-контейнеров по внутренним файлам."""

import io
import zipfile

_MIMETYPE_FORMATS: dict[str, str] = {
    "application/epub+zip": "epub",
    "application/vnd.oasis.opendocument.text": "odt",
    "application/vnd.oasis.opendocument.spreadsheet": "ods",
    "application/vnd.oasis.opendocument.presentation": "odp",
}

_MEMBER_FORMATS: dict[str, str] = {
    "word/document.xml": "docx",
    "xl/workbook.xml": "xlsx",
    "ppt/presentation.xml": "pptx",
}


def _detect_zip_format(data: bytes) -> str | None:
    """Определяет формат ZIP-контейнера по внутренним файлам.

    Член mimetype читается не более чем на 200 байт, чтобы не распаковывать
    потенциально огромный элемент до проверки всего архива.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())

            if "mimetype" in names:
                with archive.open("mimetype") as member:
                    mimetype = member.read(200).decode(
                        "utf-8",
                        errors="ignore",
                    )

                detected = _MIMETYPE_FORMATS.get(mimetype)
                if detected is not None:
                    return detected

            for archive_member, document_format in _MEMBER_FORMATS.items():
                if archive_member in names:
                    return document_format

    except (zipfile.BadZipFile, OSError, RuntimeError):
        return None

    return None
