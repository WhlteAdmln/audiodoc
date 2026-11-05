import pytest

pytest.importorskip("ebooklib")
pytest.importorskip("striprtf")

from backend.document_engine import process_document_sync
from tests.builders import (
    create_docx,
    create_epub,
    create_fb2,
    create_ods,
    create_odt,
    create_odp,
    create_pdf,
    create_pptx,
    create_xlsx,
)


@pytest.mark.parametrize(
    ("builder", "filename", "expected_format", "expected_text"),
    [
        (create_docx, "test.docx", "docx", "Document engine works!"),
        (create_xlsx, "test.xlsx", "xlsx", "Document engine"),
        (create_pptx, "test.pptx", "pptx", "Document engine works!"),
        (create_odt, "test.odt", "odt", "Document engine works!"),
        (create_ods, "test.ods", "ods", "Document engine"),
        (create_odp, "test.odp", "odp", "Document engine works!"),
        (create_epub, "test.epub", "epub", "Document engine works!"),
        (create_fb2, "test.fb2", "fb2", "Document engine works!"),
        (create_pdf, "test.pdf", "pdf", "PDF document test"),
    ],
)
def test_office_and_pdf_formats(
    builder,
    filename,
    expected_format,
    expected_text,
    tmp_path,
):
    data = builder()
    path = tmp_path / filename
    path.write_bytes(data)

    result = process_document_sync(path.read_bytes(), path.name)

    assert result["format"] == expected_format
    assert expected_text in result["text"]
    assert result["characters"] == len(result["text"])
