# Copyright (c) 2026 Nikolai Zelensky
"""Check that removed compatibility shims and working folders stay absent."""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parents[3]


def test_document_engine_processor_shim_is_removed() -> None:
    processor = PROJECT_ROOT / "audiodoc" / "document_engine" / "processor.py"
    assert not processor.exists(), "the legacy processor module is back"


def test_project_root_has_no_stray_test_scripts_or_working_folders() -> None:
    expected_empty: list[Path] = []
    assert list(PROJECT_ROOT.glob("test_*.py")) == expected_empty, (
        "a stray test script is in the project root"
    )


@pytest.mark.parametrize("folder", ["test_documents", "uploads"])
def test_project_root_has_no_working_folder(folder: str) -> None:
    assert not (PROJECT_ROOT / folder).exists(), "a working folder is in the root"


def test_uvicorn_app_module_shim_is_removed() -> None:
    assert not (PROJECT_ROOT / "app.py").exists(), "the legacy app module is back"
