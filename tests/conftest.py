# Copyright (c) 2026 Nikolai Zelensky
"""Shared test configuration.

Set environment variables before importing app because application settings are loaded
when the application is created.
"""

import os
from pathlib import Path

import pytest

os.environ.setdefault("ALLOW_UNAUTHENTICATED", "true")
os.environ.setdefault("AUDIODOC_AUDIO_KEY", "")
os.environ.setdefault("AUDIODOC_DOCUMENT_KEY", "")
os.environ.setdefault("LOG_LEVEL", "WARNING")

_TEST_MARKERS = frozenset({"unit", "integration", "contract", "e2e"})


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Apply test markers based on the top-level test directory."""
    tests_root = Path(__file__).resolve().parent

    for item in items:
        try:
            relative_path = item.path.resolve().relative_to(tests_root)
        except ValueError:
            continue

        if relative_path.parts and relative_path.parts[0] in _TEST_MARKERS:
            item.add_marker(relative_path.parts[0])
