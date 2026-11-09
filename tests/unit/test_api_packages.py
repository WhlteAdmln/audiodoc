# Copyright (c) 2026 Nikolai Zelensky
"""Verify that API handlers delegate to their application services."""

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _backend_packages(path: Path) -> set[str]:
    return {
        name.split(".")[1]
        for name in _imports(path)
        if name.startswith("backend.") and len(name.split(".")) > 1
    }


def test_api_handlers_depend_on_the_application_services() -> None:
    document_api = _backend_packages(BACKEND_ROOT / "api" / "documents.py")
    transcription_api = _backend_packages(BACKEND_ROOT / "api" / "transcribe.py")

    assert "document_engine" in document_api
    assert "transcription" in transcription_api
