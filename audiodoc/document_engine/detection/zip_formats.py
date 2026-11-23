# Copyright (c) 2026 Nikolai Zelensky
"""Detect ZIP container formats from their internal files."""

import io
import zipfile

MIMETYPE_MEMBER = "mimetype"
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


def _inspect_zip(data: bytes) -> str | None:
    """Return the format named by the mimetype member or a known member."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = set(archive.namelist())

        if MIMETYPE_MEMBER in names:
            with archive.open(MIMETYPE_MEMBER) as member:
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

    return None


def _detect_zip_format(data: bytes) -> str | None:
    """Detect the ZIP container format from its internal files.

    The mimetype member is read at most 200 bytes to avoid extracting a
    potentially huge member before checking the entire archive.
    """
    try:
        return _inspect_zip(data)

    except (zipfile.BadZipFile, OSError, RuntimeError):
        return None
