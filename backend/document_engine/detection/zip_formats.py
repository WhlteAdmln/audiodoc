"""Определение форматов ZIP-контейнеров по внутренним файлам."""

import io
import zipfile


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

                if mimetype == "application/epub+zip":
                    return "epub"

                if mimetype == "application/vnd.oasis.opendocument.text":
                    return "odt"

                if mimetype == "application/vnd.oasis.opendocument.spreadsheet":
                    return "ods"

                if mimetype == "application/vnd.oasis.opendocument.presentation":
                    return "odp"

            if "word/document.xml" in names:
                return "docx"

            if "xl/workbook.xml" in names:
                return "xlsx"

            if "ppt/presentation.xml" in names:
                return "pptx"

    except (zipfile.BadZipFile, OSError, RuntimeError):
        return None

    return None
