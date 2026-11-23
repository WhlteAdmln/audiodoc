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

    expected_fragment = "Name | Value"
    assert expected_fragment in process_document_sync(data, "table.pptx")["text"]

    budget = TextBudget(20)
    context = ExtractContext(budget=budget, deadline=Deadline(10))
    extract_pptx(data, context=context)
    assert budget.truncated is True


def test_pptx_extracts_slide_heading_and_text() -> None:
    text = extract_pptx(create_pptx())

    assert isinstance(text, str)
    expected_fragment = "--- Слайд 1 ---"
    assert expected_fragment in text
    expected_fragment = "PPTX test"
    assert expected_fragment in text
    expected_fragment = "Document engine works!"
    assert expected_fragment in text
