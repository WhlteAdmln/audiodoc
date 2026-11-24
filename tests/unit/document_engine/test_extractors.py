# Copyright (c) 2026 Nikolai Zelensky

"""Tests for document engine extractors."""

from audiodoc.document_engine.extractors import REGISTRY
from tests.support.extractor_matrix import MATRIX


def test_registered_formats_have_matrix_rows() -> None:
    matrix_formats = [row[0] for row in MATRIX]
    assert len(matrix_formats) == len(set(matrix_formats))
    assert set(REGISTRY) == set(matrix_formats)
