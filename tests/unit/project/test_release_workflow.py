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


def _read_project_file(*parts: str) -> str:
    return ROOT_DIR.joinpath(*parts).read_text(encoding="utf-8")


def _release_entry(changelog: str, version: str) -> str:
    return changelog.split(f"## [{version}] - ", maxsplit=1)[1].split(
        "\n## [", maxsplit=1
    )[0]


def _first_line(path: Path) -> str:
    return path.read_text(encoding="utf-8").splitlines()[0]


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
    assert (
        extract_release_notes(changelog, "1.2.3") == expected_extract_release_notes
    ), "release notes must contain only the requested version entry"


def test_extract_release_notes_rejects_a_missing_version() -> None:
    changelog = "# Changelog\n\n## [Unreleased]\n"
    expected_message = "Missing release entry."

    with pytest.raises(ValueError, match="Missing release entry") as error:
        extract_release_notes(changelog, "1.0.0")

    assert str(error.value) == expected_message, "a missing version must be reported"


def test_extract_release_notes_rejects_an_empty_version_entry() -> None:
    changelog = "## [1.0.0] - 2026-11-06\n\n## [0.9.0] - 2026-10-01\n"
    expected_message = "Empty release entry."

    with pytest.raises(ValueError, match="Empty release entry") as error:
        extract_release_notes(changelog, "1.0.0")

    assert str(error.value) == expected_message, "an empty entry must be reported"


@pytest.mark.parametrize(
    "fragment",
    [
        "needs: e2e",
        "dry_run:",
        "default: true",
        'GITHUB_REF" != "refs/heads/main"',
        "project_version",
        "git ls-remote",
        "python scripts/release_notes.py",
        "actions/upload-artifact@",
        "name: release-assets-${{ inputs.version }}",
        "actions/attest@",
        "dist/build-provenance.sigstore.json",
    ],
)
def test_release_workflow_requires_e2e_and_defaults_to_dry_run(fragment: str) -> None:
    workflow = _read_project_file(".github", "workflows", "release.yml")
    assert fragment in workflow, f"release.yml must contain {fragment!r}"


@pytest.mark.parametrize(
    "fragment",
    [
        "if: inputs.dry_run == false",
        'gh release create "$tag" dist/*',
        '--notes-file "$RUNNER_TEMP/release-notes.md"',
        "--draft",
        'docker push "${image}:${RELEASE_VERSION}"',
    ],
)
def test_non_dry_release_creates_a_draft_and_publishes_versioned_image(
    fragment: str,
) -> None:
    workflow = _read_project_file(".github", "workflows", "release.yml")
    assert fragment in workflow, f"release.yml must contain {fragment!r}"


def test_non_dry_release_uses_the_changelog_instead_of_generated_notes() -> None:
    workflow = _read_project_file(".github", "workflows", "release.yml")
    generated_notes_option = "--generate-notes"
    assert generated_notes_option not in workflow, "release notes must not be generated"


@pytest.mark.parametrize(
    "fragment",
    [
        "python3 -m build --sdist --wheel --outdir dist .",
        'sdists=("dist/${DIST_NAME}"-*.tar.gz)',
        'wheels=("dist/${DIST_NAME}"-*.whl)',
        'tar -tzf "${sdists[0]}"',
        '"${SDIST_ROOT}/.env.example"',
        '"${SDIST_ROOT}/.env"',
        'sha256sum "${sdists[0]##*/}" "${wheels[0]##*/}" constraints.txt > SHA256SUMS',
    ],
)
def test_release_build_produces_sdist_wheel_and_checksums(fragment: str) -> None:
    script = _read_project_file("scripts", "build_release.sh")
    assert fragment in script, f"build_release.sh must contain {fragment!r}"


def test_release_build_does_not_use_git_archive() -> None:
    script = _read_project_file("scripts", "build_release.sh")
    git_archive = "git archive"
    assert git_archive not in script, "build_release.sh must not use git archive"


@pytest.mark.parametrize(
    "fragment",
    [
        "Build source distribution, wheel and checksums",
        "sdists=(dist/audiodoc-*.tar.gz)",
        "wheels=(dist/audiodoc-*.whl)",
        "sha256sum --check --status SHA256SUMS",
    ],
)
def test_ci_build_job_verifies_both_release_distribution_formats(fragment: str) -> None:
    workflow = _read_project_file(".github", "workflows", "ci.yml")
    assert fragment in workflow, f"ci.yml must contain {fragment!r}"


def test_ci_lint_job_runs_every_static_analysis_gate() -> None:
    workflow = (ROOT_DIR / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    lint_command = "run: make types pylint deptry vulture import-lint"
    assert lint_command in workflow, "the lint job must run every static gate"


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


@pytest.mark.parametrize(
    "command",
    [
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
    ],
)
def test_lint_runs_tools_from_project_environment(command: str) -> None:
    makefile = _read_project_file("Makefile")
    assert command in makefile, f"make lint must run {command!r}"


@pytest.mark.parametrize(
    "fragment",
    [
        "language: system",
        "entry: shfmt",
        "entry: ruff",
        "entry: shellcheck",
        "shellcheck-py",
    ],
)
def test_pre_commit_does_not_run_tools_from_the_system(fragment: str) -> None:
    pre_commit_config = _read_project_file(".pre-commit-config.yaml")
    assert fragment not in pre_commit_config, (
        f".pre-commit-config.yaml must not contain {fragment!r}"
    )


def test_pyproject_pins_the_shellcheck_package() -> None:
    pyproject = _read_project_file("pyproject.toml")
    shellcheck_pin = '"shellcheck-py==0.11.0.1"'
    assert shellcheck_pin in pyproject, "pyproject.toml must pin shellcheck-py"


@pytest.mark.parametrize(
    "fragment",
    [
        "PYTHON_VERSION ?= 3.13",
        "PYTHON_BOOTSTRAP ?= python$(PYTHON_VERSION)",
        "PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)",
        'expected="$(PYTHON_VERSION)"',
        'command -v "$(PYTHON_BOOTSTRAP)"',
        ".venv/bin/python -c",
        "rm -rf .venv",
        '"$(PYTHON_BOOTSTRAP)" -m venv .venv',
    ],
)
def test_venv_requires_configured_python_version(fragment: str) -> None:
    makefile = _read_project_file("Makefile")
    assert fragment in makefile, f"Makefile must contain {fragment!r}"


def test_sdist_manifest_includes_only_the_safe_environment_template() -> None:
    manifest = _read_project_file("MANIFEST.in").splitlines()
    expected_manifest = ["include .env.example", "exclude .env"]
    assert manifest == expected_manifest, "MANIFEST.in must ship only .env.example"


def test_project_vendored_files_have_required_headers() -> None:
    headers = {path: _first_line(ROOT_DIR / path) for path in VENDORED_FILES}
    expected_headers = dict.fromkeys(VENDORED_FILES, VENDORED_HEADER)
    assert headers == expected_headers, "every vendored file needs the shared header"


def test_project_has_exactly_one_package_with_vendored_files() -> None:
    package_files = sorted(ROOT_DIR.glob("*/log_filters.py"))
    expected_count = 1
    assert len(package_files) == expected_count, "exactly one package must vendor files"


def test_package_vendored_files_have_required_headers() -> None:
    package_dir = min(ROOT_DIR.glob("*/log_filters.py")).parent
    headers = {name: _first_line(package_dir / name) for name in PACKAGE_VENDORED_FILES}
    expected_headers = dict.fromkeys(PACKAGE_VENDORED_FILES, VENDORED_HEADER)
    assert headers == expected_headers, "every package vendored file needs the header"


def test_declares_project_version_031() -> None:
    pyproject = _read_project_file("pyproject.toml")
    version_line = 'version = "0.3.1"'
    assert version_line in pyproject, "pyproject.toml must declare version 0.3.1"


@pytest.mark.parametrize(
    "fragment",
    [
        "### Added",
        "### Changed",
        "### Removed",
        "Deprecated functionality is not supported starting with 0.3.0.",
    ],
)
def test_changelog_release_030_entry_lists_the_changes(fragment: str) -> None:
    release_entry = _release_entry(_read_project_file("CHANGELOG.md"), "0.3.0")
    assert fragment in release_entry, f"the 0.3.0 entry must contain {fragment!r}"


@pytest.mark.parametrize(
    "section", ["### Added", "### Changed", "### Deprecated", "### Removed"]
)
def test_changelog_keeps_the_release_020_entry(section: str) -> None:
    changelog = _read_project_file("CHANGELOG.md")
    release_entry = changelog.split("## [0.2.0] - ", maxsplit=1)[1]
    assert section in release_entry, f"the 0.2.0 entry must contain {section!r}"
