# Copyright (c) 2026 Nikolai Zelensky

"""Tests for odf odp."""

from io import BytesIO

from odf.draw import Page
from odf.opendocument import load as load_odf
from odf.text import H

from audiodoc.common.deadline import Deadline
from audiodoc.common.text_budget import TextBudget
from audiodoc.document_engine.extractors.base import ExtractContext
from audiodoc.document_engine.extractors.odf import extract_odf
from audiodoc.document_engine.extractors.odf.odp import extract_odp
from tests.support.builders import (
    create_odp,
)
from tests.support.odf_documents import load_document


def test_odp_extracts_headings_and_truncates_slide_text() -> None:
    """Cover ODP headings and truncation while extracting a slide."""
    document = load_odf(BytesIO(create_odp()))
    page = document.getElementsByType(Page)[0]
    page.addElement(H(outlinelevel=1, text="ODP heading"), check_grammar=False)

    assert "ODP heading" in extract_odp(document)

    budget = TextBudget(20)
    context = ExtractContext(budget=budget, deadline=Deadline(10))
    text = extract_odp(document, context=context)
    assert len(text) <= 20
    assert budget.truncated is True


def test_odp_extracts_slide_headings_and_paragraphs() -> None:
    data = create_odp()
    text = extract_odf(data, "odp")

    assert text == "--- Слайд 1 ---\nODP test\nDocument engine works!"
    assert extract_odp(load_document(data)) == text
