# Copyright (c) 2026 Nikolai Zelensky

"""Tests for extractors odf."""

from audiodoc.document_engine.extractors.odf import extract_odf
from tests.support.builders import create_odt


def test_unknown_odf_type_returns_empty_text() -> None:
    expected_empty = ""
    assert extract_odf(create_odt(), "unknown") == expected_empty, (
        "expected an empty string"
    )
