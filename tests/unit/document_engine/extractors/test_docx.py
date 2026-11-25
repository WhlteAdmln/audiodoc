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

    expected_text = "DOCX test\nDocument engine works!\nName | Value"
    assert text == expected_text, "paragraphs or table cells were not extracted"


def test_docx_marks_truncation_when_another_paragraph_follows_an_exact_fit() -> None:
    first_paragraph = "Ёлка №3"
    document = Document()
    document.add_paragraph(first_paragraph)
    document.add_paragraph("Zweite Zeile")
    output = BytesIO()
    document.save(output)

    budget = TextBudget(len(first_paragraph))
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    text = extract_docx(output.getvalue(), context=context)

    expected = ("Ёлка №3", True)
    assert (text, budget.truncated) == expected, (
        "an exact fit followed by more text must be marked as truncated"
    )


def test_docx_exact_fit_at_end_of_document_is_not_truncated() -> None:
    last_paragraph = "Fin. ½"
    document = Document()
    document.add_paragraph(last_paragraph)
    output = BytesIO()
    document.save(output)

    budget = TextBudget(len(last_paragraph))
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    text = extract_docx(output.getvalue(), context=context)

    expected = ("Fin. ½", False)
    assert (text, budget.truncated) == expected, (
        "an exact fit at the end of the document must not be truncated"
    )


def test_docx_skips_empty_content_and_truncates_table_rows() -> None:
    document = Document()
    document.add_paragraph("")
    empty_table = document.add_table(rows=1, cols=1)
    empty_table.cell(0, 0).text = ""
    table = document.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "Σίσυφος-42"
    output = BytesIO()
    document.save(output)

    budget = TextBudget(3)
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    text = extract_docx(output.getvalue(), context=context)

    expected = ("Σίσ", True)
    assert (text, budget.truncated) == expected, (
        "empty content was kept or the table row was not truncated"
    )
