# Copyright (c) 2026 Nikolai Zelensky

"""Tests for extractors docx."""

from io import BytesIO

from docx import Document

from audiodoc.common.deadline import Deadline
from audiodoc.common.text_budget import TextBudget
from audiodoc.document_engine.extractors.base import ExtractContext
from audiodoc.document_engine.extractors.docx import extract_docx
from tests.support.builders import create_docx


def test_docx_extracts_paragraphs_and_table_cells() -> None:
    text = extract_docx(create_docx())

    assert isinstance(text, str)
    title = "DOCX test"
    assert title in text
    paragraph = "Document engine works!"
    assert paragraph in text
    table_row = "Name | Value"
    assert table_row in text


def test_docx_marks_truncation_when_another_paragraph_follows_an_exact_fit() -> None:
    document = Document()
    document.add_paragraph("abc")
    document.add_paragraph("def")
    output = BytesIO()
    document.save(output)

    budget = TextBudget(3)
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    expected_extract_docx = "abc"
    assert extract_docx(output.getvalue(), context=context) == expected_extract_docx
    assert budget.truncated is True


def test_docx_exact_fit_at_end_of_document_is_not_truncated() -> None:
    document = Document()
    document.add_paragraph("abc")
    output = BytesIO()
    document.save(output)

    budget = TextBudget(3)
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    expected_extract_docx = "abc"
    assert extract_docx(output.getvalue(), context=context) == expected_extract_docx
    assert budget.truncated is False


def test_docx_skips_empty_content_and_truncates_table_rows() -> None:
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

    expected_extract_docx = "abc"
    assert extract_docx(output.getvalue(), context=context) == expected_extract_docx
    assert budget.truncated is True
