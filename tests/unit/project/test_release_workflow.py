# Copyright (c) 2026 Nikolai Zelensky
"""Regression tests for release asset generation and workflow configuration."""

import json
from pathlib import Path

import pytest

from scripts.check_vendored import (
    HEADERLESS_VENDORED_FILES,
    PACKAGE_VENDORED_FILES,
    VENDORED_FILES,
    VENDORED_HEADER,
    check_vendored,
)
from scripts.release_notes import extract_release_notes

ROOT_DIR = Path(__file__).resolve().parents[3]


def test_extract_release_notes_selects_only_the_requested_version() -> None:
    """Extract one version section without including adjacent changelog entries."""
    changelog = (
        "# Changelog\n\n"
        "## [Unreleased]\n\n"
        "Unreleased changes.\n\n"
        "## [1.2.3] - 2026-11-06\n\n"
        "### Added\n\n"
        "- Release feature.\n\n"
        "## [1.2.2] - 2026-10-01\n\n"
        "Previous release.\n"
    )

    expected_extract_release_notes = "### Added\n\n- Release feature.\n"
    assert extract_release_notes(changelog, "1.2.3") == expected_extract_release_notes


def test_extract_release_notes_rejects_a_missing_version() -> None:
    """Do not produce release notes when the version is absent."""
    with pytest.raises(ValueError, match="Missing release entry"):
        extract_release_notes("# Changelog\n\n## [Unreleased]\n", "1.0.0")


def test_extract_release_notes_rejects_an_empty_version_entry() -> None:
    """Do not create a release with an empty changelog section."""
    changelog = "## [1.0.0] - 2026-11-06\n\n## [0.9.0] - 2026-10-01\n"

    with pytest.raises(ValueError, match="Empty release entry"):
        extract_release_notes(changelog, "1.0.0")


def test_release_workflow_requires_e2e_and_defaults_to_dry_run() -> None:
    """Ensure a release cannot bypass e2e or publish during its dry run."""
    workflow = (ROOT_DIR / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )

    expected_fragment = "needs: e2e"
    assert expected_fragment in workflow
    expected_fragment = "dry_run:"
    assert expected_fragment in workflow
    expected_fragment = "default: true"
    assert expected_fragment in workflow
    expected_fragment = 'GITHUB_REF" != "refs/heads/main"'
    assert expected_fragment in workflow
    expected_fragment = "project_version"
    assert expected_fragment in workflow
    expected_fragment = "git ls-remote"
    assert expected_fragment in workflow
    expected_fragment = "python scripts/release_notes.py"
    assert expected_fragment in workflow
    expected_fragment = "actions/upload-artifact@"
    assert expected_fragment in workflow
    expected_fragment = "name: release-assets-${{ inputs.version }}"
    assert expected_fragment in workflow
    expected_fragment = "actions/attest@"
    assert expected_fragment in workflow
    expected_fragment = "dist/build-provenance.sigstore.json"
    assert expected_fragment in workflow


def test_non_dry_release_creates_a_draft_and_publishes_versioned_image() -> None:
    """Ensure publishing creates a draft and a versioned GHCR image."""
    workflow = (ROOT_DIR / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )

    expected_fragment = "if: inputs.dry_run == false"
    assert expected_fragment in workflow
    expected_fragment = 'gh release create "$tag" dist/*'
    assert expected_fragment in workflow
    expected_fragment = '--notes-file "$RUNNER_TEMP/release-notes.md"'
    assert expected_fragment in workflow
    expected_fragment = "--draft"
    assert expected_fragment in workflow
    expected_fragment = 'docker push "${image}:${RELEASE_VERSION}"'
    assert expected_fragment in workflow
    expected_fragment = "--generate-notes"
    assert expected_fragment not in workflow


def test_release_build_produces_sdist_wheel_and_checksums() -> None:
    """Ensure release builds contain both Python distribution formats."""
    script = (ROOT_DIR / "scripts" / "build_release.sh").read_text(encoding="utf-8")

    expected_fragment = "python3 -m build --sdist --wheel --outdir dist ."
    assert expected_fragment in script
    expected_fragment = 'sdists=("dist/${DIST_NAME}"-*.tar.gz)'
    assert expected_fragment in script
    expected_fragment = 'wheels=("dist/${DIST_NAME}"-*.whl)'
    assert expected_fragment in script
    expected_fragment = 'tar -tzf "${sdists[0]}"'
    assert expected_fragment in script
    expected_fragment = '"${SDIST_ROOT}/.env.example"'
    assert expected_fragment in script
    expected_fragment = '"${SDIST_ROOT}/.env"'
    assert expected_fragment in script
    expected_fragment = (
        'sha256sum "${sdists[0]##*/}" "${wheels[0]##*/}" constraints.txt > SHA256SUMS'
    )
    assert expected_fragment in script
    expected_fragment = "git archive"
    assert expected_fragment not in script


def test_ci_build_job_verifies_both_release_distribution_formats() -> None:
    """Ensure CI exercises and verifies the release source distribution."""
    workflow = (ROOT_DIR / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    expected_fragment = "Build source distribution, wheel and checksums"
    assert expected_fragment in workflow
    expected_fragment = "sdists=(dist/audiodoc-*.tar.gz)"
    assert expected_fragment in workflow
    expected_fragment = "wheels=(dist/audiodoc-*.whl)"
    assert expected_fragment in workflow
    expected_fragment = "sha256sum --check --status SHA256SUMS"
    assert expected_fragment in workflow


def test_ci_lint_job_runs_every_static_analysis_gate() -> None:
    """Type checking, dependency, dead-code and import gates must run in CI."""
    workflow = (ROOT_DIR / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    expected_fragment = "run: make types pylint deptry vulture import-lint"
    assert expected_fragment in workflow


def test_ci_jobs_use_the_required_make_targets() -> None:
    """Ensure every CI job delegates its checks to the Makefile."""
    workflow = (ROOT_DIR / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    for job in (
        "lint",
        "test",
        "integration",
        "e2e",
        "audit",
        "build",
        "docker",
        "installer",
    ):
        assert f"\n  {job}:\n" in workflow

    for command in (
        "run: make lint",
        "make test 2>&1 | tee pytest.log",
        "make integration 2>&1 | tee pytest.log",
        "make e2e 2>&1 | tee pytest.log",
        "run: make audit",
        "run: make build VERSION=",
        "run: make docker",
        "run: make installer",
    ):
        assert command in workflow


def test_make_check_includes_documentation_and_fix_formats_code() -> None:
    """Keep local aggregate checks aligned with the CI Makefile entry point."""
    makefile = (ROOT_DIR / "Makefile").read_text(encoding="utf-8")

    expected_fragment = (
        "check: lint types pylint deptry vulture import-lint test docs-check"
    )
    assert expected_fragment in makefile
    docs_check = (
        "docs-check:\n"
        "\t$(PYTHON) -m scripts.check_docs\n"
        "\t$(PYTHON) -m pre_commit run --all-files"
    )
    assert docs_check in makefile
    expected_fragment = "$(PYTHON) -m ruff check . --fix"
    assert expected_fragment in makefile
    expected_fragment = "$(PYTHON) -m ruff format ."
    assert expected_fragment in makefile


def test_lint_runs_tools_from_project_environment() -> None:
    """Keep lint tools inside the project virtual environment."""
    makefile = (ROOT_DIR / "Makefile").read_text(encoding="utf-8")
    for command in (
        "$(PYTHON_SCRIPTS_DIR)/shfmt -i 0 -d install.sh",
        "$(PYTHON_SCRIPTS_DIR)/shellcheck $(shell git ls-files '*.sh' '*.sh.example')",
        (
            "find scripts -type f -name '*.sh' -exec "
            "$(PYTHON_SCRIPTS_DIR)/shfmt -i 2 -sr -d {} +"
        ),
        (
            "find deploy -type f -name '*.sh' -exec "
            "$(PYTHON_SCRIPTS_DIR)/shfmt -i 2 -sr -d {} +"
        ),
        (
            "find deploy -type f -name '*.sh.example' -exec "
            "$(PYTHON_SCRIPTS_DIR)/shfmt -i 2 -sr -d {} +"
        ),
    ):
        assert command in makefile

    pre_commit_config = (ROOT_DIR / ".pre-commit-config.yaml").read_text(
        encoding="utf-8"
    )
    expected_fragment = "language: system"
    assert expected_fragment not in pre_commit_config
    expected_fragment = "entry: shfmt"
    assert expected_fragment not in pre_commit_config
    expected_fragment = "entry: ruff"
    assert expected_fragment not in pre_commit_config
    expected_fragment = "entry: shellcheck"
    assert expected_fragment not in pre_commit_config
    expected_fragment = "shellcheck-py"
    assert expected_fragment not in pre_commit_config
    pyproject = (ROOT_DIR / "pyproject.toml").read_text(encoding="utf-8")
    expected_fragment = '"shellcheck-py==0.11.0.1"'
    assert expected_fragment in pyproject


def test_venv_requires_configured_python_version() -> None:
    """Ensure virtual environment creation uses the required Python version."""
    makefile = (ROOT_DIR / "Makefile").read_text(encoding="utf-8")

    expected_fragment = "PYTHON_VERSION ?= 3.13"
    assert expected_fragment in makefile
    expected_fragment = "PYTHON_BOOTSTRAP ?= python$(PYTHON_VERSION)"
    assert expected_fragment in makefile
    expected_fragment_2 = (
        "PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)"
    )
    assert expected_fragment_2 in makefile
    expected_fragment = 'expected="$(PYTHON_VERSION)"'
    assert expected_fragment in makefile
    expected_fragment = 'command -v "$(PYTHON_BOOTSTRAP)"'
    assert expected_fragment in makefile
    expected_fragment = ".venv/bin/python -c"
    assert expected_fragment in makefile
    expected_fragment = "rm -rf .venv"
    assert expected_fragment in makefile
    expected_fragment = '"$(PYTHON_BOOTSTRAP)" -m venv .venv'
    assert expected_fragment in makefile


def test_sdist_manifest_includes_only_the_safe_environment_template() -> None:
    """Ensure the source distribution includes the example but excludes secrets."""
    manifest = (ROOT_DIR / "MANIFEST.in").read_text(encoding="utf-8").splitlines()

    assert manifest == ["include .env.example", "exclude .env"]


def _minimal_pyproject(
    package_name: str,
    ruff_line_length: int,
    pytest_addopts: str,
) -> str:
    return (
        f"{VENDORED_HEADER}\n\n"
        "[tool.ruff]\n"
        f"line-length = {ruff_line_length}\n\n"
        "[tool.deptry]\n"
        f"known_first_party = [{json.dumps(package_name)}]\n\n"
        "[tool.importlinter]\n"
        f"root_package = {json.dumps(package_name)}\n\n"
        "[[tool.importlinter.contracts]]\n"
        f"source_modules = [{json.dumps(f'{package_name}.api')}]\n"
        f"forbidden_modules = [{json.dumps(f'{package_name}.main')}]\n\n"
        "[tool.pytest.ini_options]\n"
        f"addopts = {json.dumps(pytest_addopts)}\n"
    )


def _write_vendored_repository(
    root: Path,
    package_name: str,
    *,
    ruff_line_length: int = 88,
    pytest_addopts: str = "-q",
) -> None:
    """Create a minimal repository containing all vendored files."""
    for relative_path in VENDORED_FILES:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        pyproject_path = "pyproject.toml"
        content = (
            _minimal_pyproject(package_name, ruff_line_length, pytest_addopts)
            if relative_path == pyproject_path
            else f"{VENDORED_HEADER}\nshared content\n"
        )
        path.write_text(content, encoding="utf-8")

    for relative_path in HEADERLESS_VENDORED_FILES:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("shared content\n", encoding="utf-8")

    package_dir = root / package_name
    package_dir.mkdir(parents=True, exist_ok=True)
    for filename in PACKAGE_VENDORED_FILES:
        (package_dir / filename).write_text(
            f"{VENDORED_HEADER}\nshared module\n",
            encoding="utf-8",
        )


def test_check_vendored_accepts_package_names_and_non_lint_settings(
    tmp_path: Path,
) -> None:
    """Ignore package names and project settings outside the shared lint tables."""
    local = tmp_path / "audiodoc"
    other = tmp_path / "bot-obormot"
    _write_vendored_repository(local, "audiodoc")
    _write_vendored_repository(other, "bot_obormot", pytest_addopts="-vv")

    assert not check_vendored(other, root=local)


def test_check_vendored_reports_lint_configuration_differences(
    tmp_path: Path,
) -> None:
    """Compare lint tables while ignoring package-specific references."""
    local = tmp_path / "audiodoc"
    other = tmp_path / "bot-obormot"
    _write_vendored_repository(local, "audiodoc")
    _write_vendored_repository(other, "bot_obormot", ruff_line_length=100)

    assert check_vendored(other, root=local) == [
        "pyproject.toml: lint configuration differs from other repository"
    ]


def test_check_vendored_reports_file_and_header_errors(tmp_path: Path) -> None:
    """Report changed content, missing headers, and missing package modules."""
    local = tmp_path / "audiodoc"
    other = tmp_path / "bot-obormot"
    _write_vendored_repository(local, "audiodoc")
    _write_vendored_repository(other, "bot_obormot")
    (local / ".pre-commit-config.yaml").write_text(
        f"{VENDORED_HEADER}\nlocal content\n",
        encoding="utf-8",
    )
    (local / ".editorconfig").write_text("root = true\n", encoding="utf-8")
    (other / "bot_obormot" / "env_readers.py").unlink()

    errors = check_vendored(other, root=local)

    expected_fragment = ".pre-commit-config.yaml: content differs from other repository"
    assert expected_fragment in errors
    assert f"{local / '.editorconfig'}: missing VENDORED header" in errors
    assert f"{other / 'bot_obormot' / 'env_readers.py'}: file not found" in errors


def test_check_vendored_reports_headerless_file_differences(tmp_path: Path) -> None:
    """Compare shared files that cannot carry a header byte for byte."""
    local = tmp_path / "audiodoc"
    other = tmp_path / "bot-obormot"
    _write_vendored_repository(local, "audiodoc")
    _write_vendored_repository(other, "bot_obormot")
    (other / "AGENTS.md").write_text("changed\n", encoding="utf-8")

    assert check_vendored(other, root=local) == [
        "AGENTS.md: content differs from other repository"
    ]


def test_project_vendored_files_have_required_headers() -> None:
    """Ensure every vendored project file starts with the required marker."""
    for relative_path in VENDORED_FILES:
        path = ROOT_DIR / relative_path
        first_line = path.read_text(encoding="utf-8").splitlines()[0]
        assert first_line == VENDORED_HEADER

    package_files = sorted(ROOT_DIR.glob("*/log_filters.py"))
    assert len(package_files) == 1
    for filename in PACKAGE_VENDORED_FILES:
        first_line = (
            (package_files[0].parent / filename)
            .read_text(encoding="utf-8")
            .splitlines()[0]
        )
        assert first_line == VENDORED_HEADER


def test_project_version_and_changelog_prepare_release_030() -> None:
    """Require the 0.3.0 version and its changelog sections."""
    pyproject = (ROOT_DIR / "pyproject.toml").read_text(encoding="utf-8")
    changelog = (ROOT_DIR / "CHANGELOG.md").read_text(encoding="utf-8")
    release_entry = changelog.split("## [0.3.0] - ", maxsplit=1)[1].split(
        "\n## [", maxsplit=1
    )[0]

    expected_fragment = 'version = "0.3.0"'
    assert expected_fragment in pyproject
    for section in ("### Added", "### Changed", "### Removed"):
        assert section in release_entry
    expected_fragment = "Deprecated functionality is not supported starting with 0.3.0."
    assert expected_fragment in release_entry


def test_changelog_keeps_the_release_020_entry() -> None:
    """Version 0.2.0 keeps its historical changelog entry."""
    changelog = (ROOT_DIR / "CHANGELOG.md").read_text(encoding="utf-8")
    release_entry = changelog.split("## [0.2.0] - ", maxsplit=1)[1]

    for section in ("### Added", "### Changed", "### Deprecated", "### Removed"):
        assert section in release_entry
