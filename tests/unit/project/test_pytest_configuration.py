# Copyright (c) 2026 Nikolai Zelensky
"""Regression tests for pytest's repository-level configuration."""

import tomllib
from pathlib import Path
from typing import cast

import pytest

from tests.conftest import pytest_collection_modifyitems

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class _MarkerItem:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.markers: list[str] = []

    def add_marker(self, marker: str) -> None:
        """Provide the ``add_marker`` behaviour the test relies on."""
        self.markers.append(marker)


def test_pytest_configuration_is_strict() -> None:
    """Keep pytest's strict settings and marker registry enabled."""
    configuration = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    options = configuration["tool"]["pytest"]["ini_options"]

    expected_addopts = "--strict-markers --strict-config -ra"
    assert options["addopts"] == expected_addopts
    assert options["filterwarnings"] == [
        "error",
        (
            "ignore:^builtin type (SwigPyPacked|SwigPyObject|swigvarlink) "
            "has no __module__ attribute$:DeprecationWarning"
        ),
    ]
    expected_timeout = 30
    assert options["timeout"] == expected_timeout
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


@pytest.mark.parametrize(
    "pinned_plugin", ["pytest-randomly==5.0.0", "pytest-timeout==2.4.0"]
)
def test_pins_pytest_plugin_in_test_extra(pinned_plugin: str) -> None:
    configuration = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    dependencies = configuration["project"]["optional-dependencies"]["test"]
    assert pinned_plugin in dependencies, "the test extra must pin the plugin"
