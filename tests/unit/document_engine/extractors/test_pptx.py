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
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    table = slide.shapes.add_table(1, 2, 0, 0, 3_000_000, 500_000).table
    table.cell(0, 0).text = "Name"
    table.cell(0, 1).text = "Value"
    output = BytesIO()
    presentation.save(output)
    data = output.getvalue()

    table_row = "Name | Value"
    assert table_row in process_document_sync(data, "table.pptx")["text"]

    budget = TextBudget(20)
    context = ExtractContext(budget=budget, deadline=Deadline(10))
    extract_pptx(data, context=context)
    assert budget.truncated is True


def test_pptx_extracts_slide_heading_and_text() -> None:
    text = extract_pptx(create_pptx())

    assert isinstance(text, str)
    slide_header = "--- Слайд 1 ---"
    assert slide_header in text
    slide_title = "PPTX test"
    assert slide_title in text
    slide_text = "Document engine works!"
    assert slide_text in text
