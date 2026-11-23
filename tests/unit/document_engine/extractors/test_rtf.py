# Copyright (c) 2026 Nikolai Zelensky

"""Tests for extractors rtf."""

from importlib import import_module


def test_rtf_extractor_preserves_plain_text() -> None:
    rtf_module = import_module("audiodoc.document_engine.extractors.rtf")
    assert "RTF test" in rtf_module.extract_rtf(b"{\\rtf1 RTF test}")
