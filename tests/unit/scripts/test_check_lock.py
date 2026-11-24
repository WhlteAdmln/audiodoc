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

    expected_empty = []
    assert check_lock(project, lock) == expected_empty, "expected an empty list"


def test_check_lock_reports_missing_direct_dependency(tmp_path: Path) -> None:
    project = tmp_path / "pyproject.toml"
    lock = tmp_path / "requirements-lock.txt"
    _write_project(project, ["missing-package>=1"])
    lock.write_text("present-package==1.0\n", encoding="utf-8")

    assert check_lock(project, lock) == ["Missing from lock file: missing-package"]


def test_check_lock_reports_out_of_range_version(tmp_path: Path) -> None:
    project = tmp_path / "pyproject.toml"
    lock = tmp_path / "requirements-lock.txt"
    _write_project(project, ["example-package>=2,<3"])
    lock.write_text("example-package==1.9\n", encoding="utf-8")

    assert check_lock(project, lock) == [
        "Locked example-package==1.9 does not satisfy <3,>=2"
    ]


def test_wheel_excludes_tests_and_scripts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "dist"
    output_dir.mkdir()
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    shutil.copytree(PROJECT_ROOT / "audiodoc", source_dir / "audiodoc")
    shutil.copy2(PROJECT_ROOT / "pyproject.toml", source_dir / "pyproject.toml")

    monkeypatch.chdir(source_dir)
    wheel_name = build_wheel(str(output_dir))

    assert (output_dir / wheel_name).is_file()

    wheels = list(output_dir.glob("*.whl"))
    assert len(wheels) == 1

    with ZipFile(wheels[0]) as archive:
        paths = archive.namelist()

    assert not any(path.startswith(("tests/", "scripts/")) for path in paths)
    module_path = "audiodoc/main.py"
    assert module_path in paths
