# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the OpenAPI documentation check."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from scripts.docs_checks.openapi import check_openapi_paths

if TYPE_CHECKING:
    from pathlib import Path


def _write_files(root: Path, schema: object, guide: str) -> None:
    (root / "contract").mkdir()
    (root / "docs").mkdir()
    (root / "contract" / "openapi.json").write_text(
        json.dumps(schema), encoding="utf-8"
    )
    (root / "docs" / "api.md").write_text(guide, encoding="utf-8")


def test_accepts_a_guide_that_names_every_path(tmp_path: Path) -> None:
    _write_files(
        tmp_path,
        {"paths": {"/v1/ping": {}, "/v1/äudio": {}}},
        "`/v1/ping`, `/v1/äudio`",
    )
    expected_empty: list[str] = []

    errors = check_openapi_paths(tmp_path)

    assert errors == expected_empty, "a complete guide must pass"


def test_reports_a_path_missing_from_the_guide(tmp_path: Path) -> None:
    _write_files(tmp_path, {"paths": {"/v1/ping": {}, "/v1/äudio": {}}}, "`/v1/ping`")
    expected = ["docs/api.md: missing OpenAPI paths: /v1/äudio"]

    errors = check_openapi_paths(tmp_path)

    assert errors == expected, "a path missing from the guide must be reported"


def test_reports_a_snapshot_without_paths(tmp_path: Path) -> None:
    _write_files(tmp_path, {"openapi": "3.1.0"}, "nothing")
    expected = ["contract/openapi.json: missing paths object"]

    errors = check_openapi_paths(tmp_path)

    assert errors == expected, "a snapshot without paths must be reported"
