# Copyright (c) 2026 Nikolai Zelensky

"""Tests for the lock consistency script."""

import shutil
from pathlib import Path
from zipfile import ZipFile

import pytest
from setuptools.build_meta import build_wheel

from scripts.check_lock import check_lock

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _write_project(path: Path, dependencies: list[str]) -> None:
    dependency_lines = "\n".join(f'    "{dependency}",' for dependency in dependencies)
    path.write_text(
        f"[project]\ndependencies = [\n{dependency_lines}\n]\n",
        encoding="utf-8",
    )


def test_check_lock_accepts_satisfied_constraints(tmp_path: Path) -> None:
    project = tmp_path / "pyproject.toml"
    lock = tmp_path / "requirements-lock.txt"
    _write_project(project, ["Example_Package[extra]>=1.2,<2.0", "other~=3.1"])
    lock.write_text(
        "example-package==1.5.0\nother==3.1.4\n",
        encoding="utf-8",
    )

    expected_empty: list[str] = []
    assert check_lock(project, lock) == expected_empty, "expected an empty list"


def test_check_lock_reports_missing_direct_dependency(tmp_path: Path) -> None:
    project = tmp_path / "pyproject.toml"
    lock = tmp_path / "requirements-lock.txt"
    _write_project(project, ["missing-package>=1"])
    lock.write_text("present-package==1.0\n", encoding="utf-8")

    expected_problems = ["Missing from lock file: missing-package"]
    assert check_lock(project, lock) == expected_problems, (
        "a missing direct dependency was not reported"
    )


def test_check_lock_reports_out_of_range_version(tmp_path: Path) -> None:
    project = tmp_path / "pyproject.toml"
    lock = tmp_path / "requirements-lock.txt"
    _write_project(project, ["example-package>=2,<3"])
    lock.write_text("example-package==1.9\n", encoding="utf-8")

    expected_problems = ["Locked example-package==1.9 does not satisfy <3,>=2"]
    assert check_lock(project, lock) == expected_problems, (
        "an out-of-range locked version was not reported"
    )


@pytest.fixture(name="wheel")
def fixture_wheel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Build a wheel from a copy of the package and return its path."""
    output_dir = tmp_path / "dist"
    output_dir.mkdir()
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    shutil.copytree(PROJECT_ROOT / "audiodoc", source_dir / "audiodoc")
    shutil.copy2(PROJECT_ROOT / "pyproject.toml", source_dir / "pyproject.toml")

    monkeypatch.chdir(source_dir)
    wheel_name: str = build_wheel(str(output_dir))
    return output_dir / wheel_name


def _wheel_paths(wheel: Path) -> list[str]:
    with ZipFile(wheel) as archive:
        return archive.namelist()


def test_builds_exactly_one_wheel_file(wheel: Path) -> None:
    expected_wheels = [wheel]
    built_wheels = [path for path in wheel.parent.glob("*.whl") if path.is_file()]
    assert built_wheels == expected_wheels, "the build did not produce one wheel file"


def test_wheel_excludes_tests_and_scripts(wheel: Path) -> None:
    excluded_prefixes = ("tests/", "scripts/")
    expected_empty: list[str] = []
    leaked_paths = [
        path for path in _wheel_paths(wheel) if path.startswith(excluded_prefixes)
    ]
    assert leaked_paths == expected_empty, "the wheel contains tests or scripts"


def test_wheel_includes_package_modules(wheel: Path) -> None:
    module_path = "audiodoc/main.py"
    assert module_path in _wheel_paths(wheel), "the wheel lacks audiodoc/main.py"
