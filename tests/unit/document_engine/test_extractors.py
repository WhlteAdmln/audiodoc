# Copyright (c) 2026 Nikolai Zelensky

"""Tests for document engine extractors."""

import pytest

from audiodoc.document_engine.extractors import REGISTRY
from tests.support.extractor_matrix import MATRIX


def test_registered_formats_have_matrix_rows() -> None:
    matrix_formats = [row[0] for row in MATRIX]
    assert len(matrix_formats) == len(set(matrix_formats))
    assert set(REGISTRY) == set(matrix_formats)


def test_registry_contains_all_supported_document_formats() -> None:
    expected_formats = {
        "pdf",
        "docx",
        "xlsx",
        "pptx",
        "epub",
        "fb2",
        "djvu",
        "odt",
        "ods",
        "odp",
        "txt",
        "md",
        "csv",
        "html",
        "xml",
        "rtf",
    }

    assert set(REGISTRY) == expected_formats, "the registry formats changed"


def test_registry_reads_markdown_as_plain_text() -> None:
    assert REGISTRY["txt"] is REGISTRY["md"], "Markdown has its own extractor"


def test_odf_registry_entries_dispatch_to_the_correct_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fake_extract_odf(
        data: object,
        filetype: object,
        **_kwargs: object,
    ) -> object:
        calls.append((data, filetype))
        return ""

    monkeypatch.setattr(
        "audiodoc.document_engine.extractors.extract_odf",
        fake_extract_odf,
    )

    for kind in ("odt", "ods", "odp"):
        REGISTRY[kind](b"odf")

    expected = [(b"odf", "odt"), (b"odf", "ods"), (b"odf", "odp")]
    assert calls == expected, "each ODF registry entry must pass its own file type"
