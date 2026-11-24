# Copyright (c) 2026 Nikolai Zelensky

"""Tests for project api layers."""

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[3]


AUDIODOC_ROOT = PROJECT_ROOT / "audiodoc"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _audiodoc_packages(path: Path) -> set[str]:
    return {
        name.split(".")[1]
        for name in _imports(path)
        if name.startswith("audiodoc.") and len(name.split(".")) > 1
    }


def test_api_handlers_depend_on_the_application_services() -> None:
    document_api = _audiodoc_packages(AUDIODOC_ROOT / "api" / "documents.py")
    transcription_api = _audiodoc_packages(AUDIODOC_ROOT / "api" / "transcribe.py")

    document_service = "document_engine"
    assert document_service in document_api
    transcription_service = "transcription"
    assert transcription_service in transcription_api
