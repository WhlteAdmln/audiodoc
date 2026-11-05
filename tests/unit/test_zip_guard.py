import io
import zipfile

import pytest

from backend.document_engine.guards.zip_archive import validate_zip_archive


def test_validate_zip_archive_accepts_small_valid_archive():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("word/document.xml", "<document>safe</document>")

    validate_zip_archive(output.getvalue())


def test_validate_zip_archive_rejects_non_zip_data():
    with pytest.raises(ValueError, match="Некорректный ZIP-контейнер"):
        validate_zip_archive(b"not a zip archive")
