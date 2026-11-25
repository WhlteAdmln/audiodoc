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


def _build_table_pptx() -> bytes:
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    table = slide.shapes.add_table(1, 2, 0, 0, 3_000_000, 500_000).table
    table.cell(0, 0).text = "Name"
    table.cell(0, 1).text = "Value"
    output = BytesIO()
    presentation.save(output)
    return output.getvalue()


def test_pptx_extracts_table_rows() -> None:
    data = _build_table_pptx()

    text = process_document_sync(data, "table.pptx")["text"]

    table_row = "Name | Value"
    assert table_row in text, "the table row was not extracted"


def test_pptx_truncates_table_text() -> None:
    data = _build_table_pptx()
    budget = TextBudget(20)
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    extract_pptx(data, context=context)

    assert budget.truncated is True, "table text over the budget was not truncated"


def test_pptx_extracts_slide_heading_and_text() -> None:
    text = extract_pptx(create_pptx())

    expected_text = "--- Слайд 1 ---\nPPTX test\nDocument engine works!"
    assert text == expected_text, "the slide heading or text was not extracted"
