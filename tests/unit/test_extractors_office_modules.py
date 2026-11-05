"""Изолированные тесты экстракторов DOCX, XLSX и PPTX (этап A4)."""

from backend.document_engine.extractors.docx import extract_docx
from backend.document_engine.extractors.pptx import extract_pptx
from backend.document_engine.extractors.xlsx import extract_xlsx
from tests.builders import create_docx, create_pptx, create_xlsx


def test_docx_extracts_paragraphs_and_table_cells():
    text = extract_docx(create_docx())

    assert isinstance(text, str)
    assert "DOCX test" in text
    assert "Document engine works!" in text
    assert "Name | Value" in text


def test_xlsx_extracts_sheet_name_and_rows():
    text = extract_xlsx(create_xlsx())

    assert isinstance(text, str)
    assert "--- Лист: Test sheet ---" in text
    assert "Name | Value" in text
    assert "Document engine | Works!" in text


def test_pptx_extracts_slide_heading_and_text():
    text = extract_pptx(create_pptx())

    assert isinstance(text, str)
    assert "--- Слайд 1 ---" in text
    assert "PPTX test" in text
    assert "Document engine works!" in text
