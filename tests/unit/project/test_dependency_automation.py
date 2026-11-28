# Copyright (c) 2026 Nikolai Zelensky
# SPDX-License-Identifier: MIT

"""Tests for the dependency update automation policy."""

import json
import re
from pathlib import Path
from typing import Any

import pytest

ROOT_DIR = Path(__file__).resolve().parents[3]


@pytest.fixture(name="renovate_config")
def renovate_config_fixture() -> dict[str, Any]:
    """Load the Renovate configuration without its full-line comments."""
    lines = (ROOT_DIR / ".github" / "renovate.json5").read_text("utf-8").splitlines()
    text = "\n".join(line for line in lines if not line.lstrip().startswith("//"))
    config: dict[str, Any] = json.loads(text)
    return config


def test_renovate_extends_best_practices(renovate_config: dict[str, Any]) -> None:
    best_practices_preset = "config:best-practices"
    assert best_practices_preset in renovate_config["extends"], (
        "Renovate does not extend the best-practices preset"
    )


def test_renovate_merges_pull_requests_itself(
    renovate_config: dict[str, Any],
) -> None:
    assert renovate_config["automerge"] is True, "Renovate does not merge pull requests"


def test_renovate_does_not_use_platform_automerge(
    renovate_config: dict[str, Any],
) -> None:
    assert renovate_config["platformAutomerge"] is False, (
        "Renovate uses platform automerge"
    )


def test_renovate_waits_for_status_checks(renovate_config: dict[str, Any]) -> None:
    assert renovate_config["ignoreTests"] is False, "Renovate ignores status checks"


def test_renovate_requires_fourteen_day_old_releases(
    renovate_config: dict[str, Any],
) -> None:
    expected_minimumreleaseage = "14 days"
    assert renovate_config["minimumReleaseAge"] == expected_minimumreleaseage, (
        "Renovate does not wait fourteen days for new releases"
    )


def test_renovate_security_fixes_skip_the_release_age(
    renovate_config: dict[str, Any],
) -> None:
    assert renovate_config["vulnerabilityAlerts"]["minimumReleaseAge"] is None, (
        "security fixes wait for the release age"
    )


def test_renovate_never_automerges_major_updates(
    renovate_config: dict[str, Any],
) -> None:
    major_rules = [
        rule
        for rule in renovate_config["packageRules"]
        if rule.get("matchUpdateTypes") == ["major"]
    ]

    expected_automerge = [False]
    assert [rule["automerge"] for rule in major_rules] == expected_automerge, (
        "major updates are merged automatically"
    )


def test_renovate_generic_lock_maintenance_is_off(
    renovate_config: dict[str, Any],
) -> None:
    assert renovate_config["lockFileMaintenance"]["enabled"] is False, (
        "generic lock file maintenance is on"
    )


def test_renovate_lock_refresh_runs_monthly(
    renovate_config: dict[str, Any],
) -> None:
    refresh_rules = [
        rule
        for rule in renovate_config["packageRules"]
        if rule.get("matchUpdateTypes") == ["lockFileMaintenance"]
    ]

    expected_schedules = [["before 6am on the first day of the month"]]
    assert [rule["schedule"] for rule in refresh_rules] == expected_schedules, (
        "the lock refresh does not run monthly"
    )


def test_renovate_lock_refresh_rule_blocks_automerge(
    renovate_config: dict[str, Any],
) -> None:
    refresh_rules = [
        rule
        for rule in renovate_config["packageRules"]
        if rule.get("matchUpdateTypes") == ["lockFileMaintenance"]
    ]

    expected_automerge = [False]
    assert [rule["automerge"] for rule in refresh_rules] == expected_automerge, (
        "the lock refresh is merged automatically"
    )


def test_renovate_regenerates_the_lock_with_pip_compile(
    renovate_config: dict[str, Any],
) -> None:
    lock_command = "pip-compile"
    assert lock_command in renovate_config["enabledManagers"], (
        "Renovate does not regenerate the lock with pip-compile"
    )


def test_renovate_does_not_edit_the_lock_line_by_line(
    renovate_config: dict[str, Any],
) -> None:
    line_manager = "pip_requirements"
    assert line_manager not in renovate_config["enabledManagers"], (
        "Renovate edits the lock line by line"
    )


def test_renovate_python_version_changes_are_left_to_humans(
    renovate_config: dict[str, Any],
) -> None:
    python_rules = [
        rule
        for rule in renovate_config["packageRules"]
        if rule.get("matchDepNames") == ["python"]
    ]

    expected_enabled = [False]
    assert [rule["enabled"] for rule in python_rules] == expected_enabled, (
        "Renovate changes the Python version"
    )


def test_lock_command_writes_options_with_equal_signs() -> None:
    makefile = (ROOT_DIR / "Makefile").read_text("utf-8")

    python_version_option = "--python-version=$(LOCK_PYTHON_VERSION)"
    assert python_version_option in makefile, (
        "the lock command does not write the Python version with an equal sign"
    )


def test_lock_command_runs_uv_from_the_virtual_environment() -> None:
    makefile = (ROOT_DIR / "Makefile").read_text("utf-8")

    venv_uv_command = "$(PYTHON_SCRIPTS_DIR)/uv pip compile"
    assert venv_uv_command in makefile, (
        "the lock command does not run uv from the virtual environment"
    )


def test_lock_command_names_the_output_file_with_an_equal_sign() -> None:
    makefile = (ROOT_DIR / "Makefile").read_text("utf-8")

    output_file_option = "--output-file=requirements-lock.txt"
    assert output_file_option in makefile, (
        "the lock command does not name the output file with an equal sign"
    )


def test_renovate_updates_pydantic_and_its_core_together(
    renovate_config: dict[str, Any],
) -> None:
    group_name_key = "groupName"
    groups = {
        rule["groupName"]: set(rule["matchPackageNames"])
        for rule in renovate_config["packageRules"]
        if group_name_key in rule
    }

    expected_packages = {"pydantic", "pydantic-core"}
    assert expected_packages <= groups["pydantic"], (
        "pydantic and pydantic-core are not updated together"
    )


def test_renovate_digest_pins_skip_the_release_age(
    renovate_config: dict[str, Any],
) -> None:
    digest_pin_type = "pinDigest"
    digest_rules = [
        rule
        for rule in renovate_config["packageRules"]
        if digest_pin_type in rule.get("matchUpdateTypes", [])
    ]

    expected_release_ages = [None]
    assert [rule["minimumReleaseAge"] for rule in digest_rules] == (
        expected_release_ages
    ), "digest pins wait for the release age"


def test_renovate_leaves_workflow_actions_to_humans(
    renovate_config: dict[str, Any],
) -> None:
    action_rules = [
        rule
        for rule in renovate_config["packageRules"]
        if rule.get("matchManagers") == ["github-actions"]
    ]

    expected_automerge = [False]
    assert [rule["automerge"] for rule in action_rules] == expected_automerge, (
        "workflow action updates are merged automatically"
    )


def test_renovate_leaves_pre_commit_hooks_to_humans(
    renovate_config: dict[str, Any],
) -> None:
    hook_rules = [
        rule
        for rule in renovate_config["packageRules"]
        if rule.get("matchManagers") == ["pre-commit"]
    ]

    expected_automerge = [False]
    assert [rule["automerge"] for rule in hook_rules] == expected_automerge, (
        "pre-commit hook updates are merged automatically"
    )


def test_renovate_leaves_build_tooling_to_humans(
    renovate_config: dict[str, Any],
) -> None:
    build_tool = "setuptools"
    build_rules = [
        rule
        for rule in renovate_config["packageRules"]
        if build_tool in rule.get("matchPackageNames", [])
    ]

    expected_automerge = [False]
    assert [rule["automerge"] for rule in build_rules] == expected_automerge, (
        "build tooling updates are merged automatically"
    )


def test_renovate_vulnerability_alerts_use_only_supported_options(
    renovate_config: dict[str, Any],
) -> None:
    unsupported_option = "prPriority"
    assert unsupported_option not in renovate_config["vulnerabilityAlerts"], (
        "vulnerability alerts use an unsupported option"
    )


def test_dependabot_version_updates_are_removed() -> None:
    dependabot_config = ROOT_DIR / ".github" / "dependabot.yml"
    assert not dependabot_config.exists(), "the Dependabot configuration still exists"


def test_renovate_runs_the_regex_manager(renovate_config: dict[str, Any]) -> None:
    regex_manager = "custom.regex"
    assert regex_manager in renovate_config["enabledManagers"], (
        "Renovate does not run the regex manager"
    )


@pytest.mark.parametrize(
    ("path", "expected_image"),
    [
        ("compose.yaml", "python:3.12-slim"),
        ("compose.cuda.yaml", "nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04"),
        (".github/workflows/ci.yml", "nginx:stable-alpine"),
    ],
)
def test_renovate_regex_manager_finds_digest_pinned_images(
    renovate_config: dict[str, Any],
    path: str,
    expected_image: str,
) -> None:
    text = (ROOT_DIR / path).read_text("utf-8")
    found_images = [
        f"{match['depName']}:{match['currentValue']}"
        for manager in renovate_config["customManagers"]
        if re.search(manager["managerFilePatterns"][0].strip("/"), path)
        for pattern in manager["matchStrings"]
        for match in re.finditer(pattern.replace("(?<", "(?P<"), text)
    ]

    assert expected_image in found_images, (
        f"the Renovate regex manager misses the image in {path}"
    )


def test_renovate_leaves_regex_manager_tag_updates_to_humans(
    renovate_config: dict[str, Any],
) -> None:
    regex_manager = "custom.regex"
    regex_rules = [
        rule
        for rule in renovate_config["packageRules"]
        if rule.get("matchManagers") == [regex_manager]
    ]

    expected_automerge = [False]
    assert [rule["automerge"] for rule in regex_rules] == expected_automerge, (
        "Renovate merges tag updates of the regex managers"
    )
