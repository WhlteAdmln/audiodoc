# Copyright (c) 2026 Nikolai Zelensky
"""Regression tests for pytest's repository-level configuration."""

import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


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


def test_pytest_plugins_are_pinned() -> None:
    """Keep random ordering and timeout plugins pinned in development requirements."""
    requirements = (
        (PROJECT_ROOT / "requirements-dev.txt").read_text(encoding="utf-8").splitlines()
    )

    assert "pytest-randomly==5.0.0" in requirements
    assert "pytest-timeout==2.4.0" in requirements
