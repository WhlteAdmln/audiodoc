# Copyright (c) 2026 Nikolai Zelensky

"""Tests for odf odp."""

from io import BytesIO

import pytest
from odf.draw import Page
from odf.opendocument import OpenDocument
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


@pytest.fixture(name="document_with_heading")
def fixture_document_with_heading() -> OpenDocument:
    """Return a presentation whose first slide has an added heading."""
    document = load_odf(BytesIO(create_odp()))
    page = document.getElementsByType(Page)[0]
    page.addElement(H(outlinelevel=1, text="ODP heading"), check_grammar=False)
    return document


def test_odp_extracts_headings_and_truncates_slide_text(
    document_with_heading: OpenDocument,
) -> None:
    heading = "ODP heading"
    assert heading in extract_odp(document_with_heading), "the heading is missing"


def test_odp_truncates_slide_text_to_budget(
    document_with_heading: OpenDocument,
) -> None:
    context = ExtractContext(budget=TextBudget(20), deadline=Deadline(10))

    text = extract_odp(document_with_heading, context=context)

    expected_count = 20
    assert len(text) <= expected_count, "the text exceeds the budget"


def test_odp_marks_budget_as_truncated(
    document_with_heading: OpenDocument,
) -> None:
    budget = TextBudget(20)
    context = ExtractContext(budget=budget, deadline=Deadline(10))

    extract_odp(document_with_heading, context=context)

    assert budget.truncated is True, "the budget is not marked as truncated"


def test_odp_extracts_slide_headings_and_paragraphs() -> None:
    data = create_odp()
    text = extract_odf(data, "odp")

    expected_text = "--- Слайд 1 ---\nODP test\nDocument engine works!"
    assert text == expected_text, "wrong slide text from the ODF dispatcher"


def test_odp_extracts_slide_headings_and_paragraphs_from_loaded_document() -> None:
    data = create_odp()

    text = extract_odp(load_document(data))

    expected_text = "--- Слайд 1 ---\nODP test\nDocument engine works!"
    assert text == expected_text, "wrong slide text from a loaded document"
