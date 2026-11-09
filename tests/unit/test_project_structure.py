# Copyright (c) 2026 Nikolai Zelensky
"""Check that removed compatibility shims and legacy folders stay absent."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]


def test_document_engine_processor_shim_is_removed() -> None:
    processor = PROJECT_ROOT / "backend" / "document_engine" / "processor.py"
    assert not processor.exists()


def test_project_root_has_no_legacy_test_scripts_or_working_folders() -> None:
    assert not list(PROJECT_ROOT.glob("test_*.py"))
    assert not (PROJECT_ROOT / "test_documents").exists()
    assert not (PROJECT_ROOT / "uploads").exists()
