# Copyright (c) 2026 Nikolai Zelensky
"""Изолированные тесты экстракторов DOCX, XLSX и PPTX."""

from io import BytesIO

from docx import Document

from backend.common.deadline import Deadline
from backend.common.text_budget import TextBudget
from backend.document_engine.extractors.base import ExtractContext
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


def test_docx_marks_truncation_when_another_paragraph_follows_an_exact_fit():
    document = Document()
    document.add_paragraph("abc")
    document.add_paragraph("def")
    output = BytesIO()
    document.save(output)

    budget = TextBudget(3)
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    assert extract_docx(output.getvalue(), context=context) == "abc"
    assert budget.truncated is True


def test_docx_exact_fit_at_end_of_document_is_not_truncated():
    document = Document()
    document.add_paragraph("abc")
    output = BytesIO()
    document.save(output)

    budget = TextBudget(3)
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    assert extract_docx(output.getvalue(), context=context) == "abc"
    assert budget.truncated is False


def test_docx_skips_empty_content_and_truncates_table_rows():
    """Cover empty paragraphs, empty table rows, and table truncation."""
    document = Document()
    document.add_paragraph("")
    empty_table = document.add_table(rows=1, cols=1)
    empty_table.cell(0, 0).text = ""
    table = document.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "abcdef"
    output = BytesIO()
    document.save(output)

    budget = TextBudget(3)
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    assert extract_docx(output.getvalue(), context=context) == "abc"
    assert budget.truncated is True
