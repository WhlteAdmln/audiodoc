# Copyright (c) 2026 Nikolai Zelensky
"""Regression tests for pytest's repository-level configuration."""

import tomllib
from pathlib import Path
from typing import cast

import pytest

from tests.conftest import pytest_collection_modifyitems
from tests.support.pytest_items import FakeMarkerItem

PROJECT_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(name="pytest_options")
def fixture_pytest_options() -> dict[str, object]:
    """Return the pytest options of pyproject.toml."""
    configuration = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    return cast("dict[str, object]", configuration["tool"]["pytest"]["ini_options"])


@pytest.mark.parametrize(
    ("option", "expected_value"),
    [
        ("addopts", "--strict-markers --strict-config -ra"),
        (
            "filterwarnings",
            [
                "error",
                (
                    "ignore:^builtin type (SwigPyPacked|SwigPyObject|swigvarlink) "
                    "has no __module__ attribute$:DeprecationWarning"
                ),
            ],
        ),
        ("timeout", 30),
    ],
)
def test_pytest_configuration_is_strict(
    pytest_options: dict[str, object], option: str, expected_value: object
) -> None:
    assert pytest_options[option] == expected_value, f"pytest {option} changed"


def test_declares_the_four_test_markers(pytest_options: dict[str, object]) -> None:
    markers = cast("list[str]", pytest_options["markers"])
    marker_names = {marker.split(":", maxsplit=1)[0] for marker in markers}
    expected_names = {"unit", "integration", "contract", "e2e"}
    assert marker_names == expected_names, "the declared markers changed"


def test_keeps_pytest_configuration_out_of_pytest_ini() -> None:
    pytest_ini = PROJECT_ROOT / "pytest.ini"
    assert not pytest_ini.exists(), "pytest.ini would override pyproject.toml"


def test_marks_each_test_by_its_directory() -> None:
    marker_names = ("unit", "integration", "contract", "e2e")
    items = [
        FakeMarkerItem(PROJECT_ROOT / "tests" / marker / "test_example.py")
        for marker in marker_names
    ]

    pytest_collection_modifyitems(cast("list[pytest.Item]", items))

    expected_markers = [[marker] for marker in marker_names]
    assert [item.markers for item in items] == expected_markers, (
        "a test got the wrong directory marker"
    )


@pytest.mark.parametrize(
    "pinned_plugin", ["pytest-randomly==5.0.0", "pytest-timeout==2.4.0"]
)
def test_pins_pytest_plugin_in_test_extra(pinned_plugin: str) -> None:
    configuration = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    dependencies = configuration["project"]["optional-dependencies"]["test"]
    assert pinned_plugin in dependencies, "the test extra must pin the plugin"
