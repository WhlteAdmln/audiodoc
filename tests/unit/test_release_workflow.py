# Copyright (c) 2026 Nikolai Zelensky
"""Regression tests for release asset generation and workflow configuration."""

from pathlib import Path

import pytest

from scripts.release_notes import extract_release_notes

ROOT_DIR = Path(__file__).resolve().parents[2]


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

    assert extract_release_notes(changelog, "1.2.3") == (
        "### Added\n\n- Release feature.\n"
    )


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

    assert "needs: e2e" in workflow
    assert "dry_run:" in workflow
    assert "default: true" in workflow
    assert 'GITHUB_REF" != "refs/heads/main"' in workflow
    assert "project_version" in workflow
    assert "git ls-remote" in workflow
    assert "python scripts/release_notes.py" in workflow
    assert "actions/upload-artifact@" in workflow
    assert "name: release-assets-${{ inputs.version }}" in workflow
    assert "actions/attest@" in workflow
    assert "dist/build-provenance.sigstore.json" in workflow


def test_non_dry_release_creates_a_draft_and_publishes_versioned_image() -> None:
    """Ensure publishing creates a draft and a versioned GHCR image."""
    workflow = (ROOT_DIR / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )

    assert "if: inputs.dry_run == false" in workflow
    assert 'gh release create "$tag" dist/*' in workflow
    assert '--notes-file "$RUNNER_TEMP/release-notes.md"' in workflow
    assert "--draft" in workflow
    assert 'docker push "${image}:${RELEASE_VERSION}"' in workflow
    assert "--generate-notes" not in workflow


def test_release_build_produces_sdist_wheel_and_checksums() -> None:
    """Ensure release builds contain both Python distribution formats."""
    script = (ROOT_DIR / "scripts" / "build_release.sh").read_text(encoding="utf-8")

    assert "python3 -m build --sdist --wheel --outdir dist ." in script
    assert "sdists=(dist/audiodoc-*.tar.gz)" in script
    assert "wheels=(dist/audiodoc-*.whl)" in script
    assert 'tar -tzf "${sdists[0]}"' in script
    assert '"${SDIST_ROOT}/.env.example"' in script
    assert '"${SDIST_ROOT}/.env"' in script
    assert (
        'sha256sum "${sdists[0]##*/}" "${wheels[0]##*/}" constraints.txt > SHA256SUMS'
        in script
    )
    assert "git archive" not in script


def test_ci_build_job_verifies_both_release_distribution_formats() -> None:
    """Ensure CI exercises and verifies the release source distribution."""
    workflow = (ROOT_DIR / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert "Build source distribution, wheel and checksums" in workflow
    assert "sdists=(dist/audiodoc-*.tar.gz)" in workflow
    assert "wheels=(dist/audiodoc-*.whl)" in workflow
    assert "sha256sum --check --status SHA256SUMS" in workflow


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

    assert "check: lint types deptry vulture import-lint test docs-check" in makefile
    docs_check = (
        "docs-check:\n"
        "\t$(PYTHON) -m scripts.check_docs\n"
        "\t$(PYTHON) -m pre_commit run --all-files"
    )
    assert docs_check in makefile
    assert "$(PYTHON) -m ruff check . --fix" in makefile
    assert "$(PYTHON) -m ruff format ." in makefile


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
    assert "language: system" not in pre_commit_config
    assert "entry: shfmt" not in pre_commit_config
    assert "entry: ruff" not in pre_commit_config
    assert "entry: shellcheck" not in pre_commit_config
    assert "shellcheck-py" not in pre_commit_config
    pyproject = (ROOT_DIR / "pyproject.toml").read_text(encoding="utf-8")
    assert '"shellcheck-py==0.11.0.1"' in pyproject


def test_venv_requires_configured_python_version() -> None:
    """Ensure virtual environment creation uses the required Python version."""
    makefile = (ROOT_DIR / "Makefile").read_text(encoding="utf-8")

    assert "PYTHON_VERSION ?= 3.13" in makefile
    assert "PYTHON_BOOTSTRAP ?= python$(PYTHON_VERSION)" in makefile
    assert (
        "PYTHON ?= $(if $(wildcard .venv/bin/python),"
        ".venv/bin/python,python3)" in makefile
    )
    assert 'expected="$(PYTHON_VERSION)"' in makefile
    assert 'command -v "$(PYTHON_BOOTSTRAP)"' in makefile
    assert ".venv/bin/python -c" in makefile
    assert "rm -rf .venv" in makefile
    assert '"$(PYTHON_BOOTSTRAP)" -m venv .venv' in makefile


def test_sdist_manifest_includes_only_the_safe_environment_template() -> None:
    """Ensure the source distribution includes the example but excludes secrets."""
    manifest = (ROOT_DIR / "MANIFEST.in").read_text(encoding="utf-8").splitlines()

    assert manifest == ["include .env.example", "exclude .env"]
