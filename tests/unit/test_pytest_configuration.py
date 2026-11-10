# Copyright (c) 2026 Nikolai Zelensky
"""Regression tests for pytest's repository-level configuration."""

import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, cast

from tests.conftest import pytest_collection_modifyitems

if TYPE_CHECKING:
    import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class _MarkerItem:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.markers: list[str] = []

    def add_marker(self, marker: str) -> None:
        self.markers.append(marker)


def test_pytest_configuration_is_strict() -> None:
    """Keep pytest's strict settings and marker registry enabled."""
    configuration = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    options = configuration["tool"]["pytest"]["ini_options"]

    assert options["addopts"] == "--strict-markers --strict-config -ra"
    assert options["filterwarnings"] == [
        "error",
        (
            "ignore:^builtin type (SwigPyPacked|SwigPyObject|swigvarlink) "
            "has no __module__ attribute$:DeprecationWarning"
        ),
    ]
    assert options["timeout"] == 30
    assert {marker.split(":", maxsplit=1)[0] for marker in options["markers"]} == {
        "unit",
        "integration",
        "contract",
        "e2e",
    }
    assert not (PROJECT_ROOT / "pytest.ini").exists()

    marker_names = ("unit", "integration", "contract", "e2e")
    items = [
        _MarkerItem(PROJECT_ROOT / "tests" / marker / "test_example.py")
        for marker in marker_names
    ]
    pytest_collection_modifyitems(cast("list[pytest.Item]", items))
    assert [item.markers for item in items] == [[marker] for marker in marker_names]


def test_pytest_plugins_are_pinned() -> None:
    """Keep random ordering and timeout plugins pinned in the development extra."""
    configuration = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    dependencies = configuration["project"]["optional-dependencies"]["dev"]

    assert "pytest-randomly==5.0.0" in dependencies
    assert "pytest-timeout==2.4.0" in dependencies
