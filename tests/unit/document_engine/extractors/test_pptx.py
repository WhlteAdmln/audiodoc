# Copyright (c) 2026 Nikolai Zelensky

"""Tests for extractors pptx."""

from io import BytesIO

from pptx import Presentation

from audiodoc.common.deadline import Deadline
from audiodoc.common.text_budget import TextBudget
from audiodoc.document_engine import process_document_sync
from audiodoc.document_engine.extractors.base import ExtractContext
from audiodoc.document_engine.extractors.pptx import extract_pptx
from tests.support.builders import (
    create_pptx,
)


def test_pptx_extracts_table_rows_and_truncates_table_text() -> None:
    """Cover PPTX table rows and budget exhaustion inside a table."""
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    table = slide.shapes.add_table(1, 2, 0, 0, 3_000_000, 500_000).table
    table.cell(0, 0).text = "Name"
    table.cell(0, 1).text = "Value"
    output = BytesIO()
    presentation.save(output)
    data = output.getvalue()

    assert "Name | Value" in process_document_sync(data, "table.pptx")["text"]

    budget = TextBudget(20)
    context = ExtractContext(budget=budget, deadline=Deadline(10))
    extract_pptx(data, context=context)
    assert budget.truncated is True


def test_pptx_extracts_slide_heading_and_text() -> None:
    text = extract_pptx(create_pptx())

    assert isinstance(text, str)
    assert "--- Слайд 1 ---" in text
    assert "PPTX test" in text
    assert "Document engine works!" in text
