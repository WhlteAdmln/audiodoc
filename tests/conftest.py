# Copyright (c) 2026 Nikolai Zelensky
"""Общая конфигурация тестов бэкенда.

Переменные окружения задаются до импорта app: настройки приложения загружаются
при создании приложения.
"""

import os
from pathlib import Path

import pytest

os.environ.setdefault("ALLOW_UNAUTHENTICATED", "true")
os.environ.setdefault("WHISPER_API_KEY", "")
os.environ.setdefault("DOCUMENT_API_KEY", "")
os.environ.setdefault("LOG_LEVEL", "WARNING")

_TEST_MARKERS = {"unit", "integration", "contract", "e2e"}


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
