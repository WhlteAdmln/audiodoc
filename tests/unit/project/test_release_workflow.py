# Copyright (c) 2026 Nikolai Zelensky
"""Regression tests for release asset generation and workflow configuration."""

from pathlib import Path

import pytest

from scripts.check_vendored import (
    PACKAGE_VENDORED_FILES,
    VENDORED_FILES,
    VENDORED_HEADER,
)
from scripts.release_notes import extract_release_notes

ROOT_DIR = Path(__file__).resolve().parents[3]


def test_extract_release_notes_selects_only_the_requested_version() -> None:
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
    with pytest.raises(ValueError, match="Missing release entry"):
        extract_release_notes("# Changelog\n\n## [Unreleased]\n", "1.0.0")


def test_extract_release_notes_rejects_an_empty_version_entry() -> None:
    changelog = "## [1.0.0] - 2026-11-06\n\n## [0.9.0] - 2026-10-01\n"

    with pytest.raises(ValueError, match="Empty release entry"):
        extract_release_notes(changelog, "1.0.0")


def test_release_workflow_requires_e2e_and_defaults_to_dry_run() -> None:
    workflow = (ROOT_DIR / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )

    e2e_dependency = "needs: e2e"
    assert e2e_dependency in workflow
    dry_run_input = "dry_run:"
    assert dry_run_input in workflow
    dry_run_default = "default: true"
    assert dry_run_default in workflow
    main_branch_guard = 'GITHUB_REF" != "refs/heads/main"'
    assert main_branch_guard in workflow
    version_check = "project_version"
    assert version_check in workflow
    tag_check = "git ls-remote"
    assert tag_check in workflow
    notes_script = "python scripts/release_notes.py"
    assert notes_script in workflow
    upload_action = "actions/upload-artifact@"
    assert upload_action in workflow
    artifact_name = "name: release-assets-${{ inputs.version }}"
    assert artifact_name in workflow
    attest_action = "actions/attest@"
    assert attest_action in workflow
    provenance_file = "dist/build-provenance.sigstore.json"
    assert provenance_file in workflow


def test_non_dry_release_creates_a_draft_and_publishes_versioned_image() -> None:
    workflow = (ROOT_DIR / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )

    non_dry_condition = "if: inputs.dry_run == false"
    assert non_dry_condition in workflow
    release_create = 'gh release create "$tag" dist/*'
    assert release_create in workflow
    notes_option = '--notes-file "$RUNNER_TEMP/release-notes.md"'
    assert notes_option in workflow
    draft_option = "--draft"
    assert draft_option in workflow
    versioned_push = 'docker push "${image}:${RELEASE_VERSION}"'
    assert versioned_push in workflow
    generated_notes_option = "--generate-notes"
    assert generated_notes_option not in workflow


def test_release_build_produces_sdist_wheel_and_checksums() -> None:
    script = (ROOT_DIR / "scripts" / "build_release.sh").read_text(encoding="utf-8")

    build_command = "python3 -m build --sdist --wheel --outdir dist ."
    assert build_command in script
    sdist_glob = 'sdists=("dist/${DIST_NAME}"-*.tar.gz)'
    assert sdist_glob in script
    wheel_glob = 'wheels=("dist/${DIST_NAME}"-*.whl)'
    assert wheel_glob in script
    sdist_listing = 'tar -tzf "${sdists[0]}"'
    assert sdist_listing in script
    env_example_entry = '"${SDIST_ROOT}/.env.example"'
    assert env_example_entry in script
    env_entry = '"${SDIST_ROOT}/.env"'
    assert env_entry in script
    checksum_command = (
        'sha256sum "${sdists[0]##*/}" "${wheels[0]##*/}" constraints.txt > SHA256SUMS'
    )
    assert checksum_command in script
    git_archive = "git archive"
    assert git_archive not in script


def test_ci_build_job_verifies_both_release_distribution_formats() -> None:
    workflow = (ROOT_DIR / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    build_step = "Build source distribution, wheel and checksums"
    assert build_step in workflow
    sdist_glob = "sdists=(dist/audiodoc-*.tar.gz)"
    assert sdist_glob in workflow
    wheel_glob = "wheels=(dist/audiodoc-*.whl)"
    assert wheel_glob in workflow
    checksum_check = "sha256sum --check --status SHA256SUMS"
    assert checksum_check in workflow


def test_ci_lint_job_runs_every_static_analysis_gate() -> None:
    workflow = (ROOT_DIR / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    lint_command = "run: make types pylint deptry vulture import-lint"
    assert lint_command in workflow


@pytest.mark.parametrize(
    "job",
    ["lint", "test", "integration", "e2e", "audit", "build", "docker", "installer"],
)
def test_ci_defines_the_required_job(job: str) -> None:
    workflow = (ROOT_DIR / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    assert f"\n  {job}:\n" in workflow, f"ci.yml must define the {job} job"


@pytest.mark.parametrize(
    "command",
    [
        "run: make lint",
        "run: make test-no-skips",
        "run: make test-integration-no-skips",
        "run: make test-e2e-no-skips",
        "run: make audit",
        "run: make build VERSION=",
        "run: make docker",
        "run: make installer",
    ],
)
def test_ci_runs_the_required_make_command(command: str) -> None:
    workflow = (ROOT_DIR / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    assert command in workflow, f"ci.yml must run {command!r}"


@pytest.mark.parametrize(
    ("target", "call"),
    [
        ("test-no-skips", "$(call run_without_skips,test,Unit)"),
        (
            "test-integration-no-skips",
            "$(call run_without_skips,test-integration,Integration)",
        ),
        ("test-e2e-no-skips", "$(call run_without_skips,test-e2e,E2E)"),
    ],
)
def test_no_skips_target_fails_on_skipped_tests(target: str, call: str) -> None:
    makefile = (ROOT_DIR / "Makefile").read_text(encoding="utf-8")
    assert f"{target}:\n\t{call}\n" in makefile, f"{target} must reject skips"


def test_release_e2e_job_rejects_skipped_tests() -> None:
    workflow = (ROOT_DIR / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    expected_command = "run: make test-e2e-no-skips"
    assert expected_command in workflow, "release e2e job must reject skipped tests"


def test_check_target_runs_every_local_ci_gate() -> None:
    makefile = (ROOT_DIR / "Makefile").read_text(encoding="utf-8")
    joined = makefile.replace("\\\n", " ")
    check_line = next(line for line in joined.splitlines() if line.startswith("check:"))
    gates = check_line.removeprefix("check:").split()
    expected_gates = [
        "lint",
        "types",
        "pylint",
        "deptry",
        "vulture",
        "import-lint",
        "pip-check",
        "test-no-skips",
        "audit",
        "release-check",
        "docs-check",
    ]
    assert gates == expected_gates, "make check must run every local CI gate"


def test_docs_check_runs_script_and_pre_commit() -> None:
    makefile = (ROOT_DIR / "Makefile").read_text(encoding="utf-8")
    docs_check = (
        "docs-check:\n"
        "\t$(PYTHON) -m scripts.check_docs\n"
        "\t$(PYTHON) -m pre_commit run --all-files"
    )
    assert docs_check in makefile, "docs-check must run the script and pre-commit"


@pytest.mark.parametrize(
    "fix_command",
    ["$(PYTHON) -m ruff check . --fix", "$(PYTHON) -m ruff format ."],
)
def test_fix_target_runs_ruff(fix_command: str) -> None:
    makefile = (ROOT_DIR / "Makefile").read_text(encoding="utf-8")
    assert fix_command in makefile, "make fix must run the ruff command"


def test_lint_runs_tools_from_project_environment() -> None:
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
    system_language = "language: system"
    assert system_language not in pre_commit_config
    shfmt_entry = "entry: shfmt"
    assert shfmt_entry not in pre_commit_config
    ruff_entry = "entry: ruff"
    assert ruff_entry not in pre_commit_config
    shellcheck_entry = "entry: shellcheck"
    assert shellcheck_entry not in pre_commit_config
    shellcheck_package = "shellcheck-py"
    assert shellcheck_package not in pre_commit_config
    pyproject = (ROOT_DIR / "pyproject.toml").read_text(encoding="utf-8")
    shellcheck_pin = '"shellcheck-py==0.11.0.1"'
    assert shellcheck_pin in pyproject


def test_venv_requires_configured_python_version() -> None:
    makefile = (ROOT_DIR / "Makefile").read_text(encoding="utf-8")

    python_version = "PYTHON_VERSION ?= 3.13"
    assert python_version in makefile
    bootstrap_python = "PYTHON_BOOTSTRAP ?= python$(PYTHON_VERSION)"
    assert bootstrap_python in makefile
    venv_python = (
        "PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)"
    )
    assert venv_python in makefile
    version_check = 'expected="$(PYTHON_VERSION)"'
    assert version_check in makefile
    bootstrap_lookup = 'command -v "$(PYTHON_BOOTSTRAP)"'
    assert bootstrap_lookup in makefile
    venv_probe = ".venv/bin/python -c"
    assert venv_probe in makefile
    venv_removal = "rm -rf .venv"
    assert venv_removal in makefile
    venv_creation = '"$(PYTHON_BOOTSTRAP)" -m venv .venv'
    assert venv_creation in makefile


def test_sdist_manifest_includes_only_the_safe_environment_template() -> None:
    manifest = (ROOT_DIR / "MANIFEST.in").read_text(encoding="utf-8").splitlines()

    assert manifest == ["include .env.example", "exclude .env"]


def test_project_vendored_files_have_required_headers() -> None:
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
    pyproject = (ROOT_DIR / "pyproject.toml").read_text(encoding="utf-8")
    changelog = (ROOT_DIR / "CHANGELOG.md").read_text(encoding="utf-8")
    release_entry = changelog.split("## [0.3.0] - ", maxsplit=1)[1].split(
        "\n## [", maxsplit=1
    )[0]

    version_line = 'version = "0.3.0"'
    assert version_line in pyproject
    for section in ("### Added", "### Changed", "### Removed"):
        assert section in release_entry
    deprecation_note = "Deprecated functionality is not supported starting with 0.3.0."
    assert deprecation_note in release_entry


def test_changelog_keeps_the_release_020_entry() -> None:
    changelog = (ROOT_DIR / "CHANGELOG.md").read_text(encoding="utf-8")
    release_entry = changelog.split("## [0.2.0] - ", maxsplit=1)[1]

    for section in ("### Added", "### Changed", "### Deprecated", "### Removed"):
        assert section in release_entry
