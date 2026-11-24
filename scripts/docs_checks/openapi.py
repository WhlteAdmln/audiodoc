# Copyright (c) 2026 Nikolai Zelensky
"""Check that every OpenAPI snapshot path is in the API guide."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def check_openapi_paths(root: Path) -> list[str]:
    """Check that every OpenAPI snapshot path appears in the API guide."""
    snapshot_path = root / "contract" / "openapi.json"
    docs_path = root / "docs" / "api.md"

    if not snapshot_path.is_file() or not docs_path.is_file():
        return ["contract/openapi.json or docs/api.md: file not found"]

    try:
        schema = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"contract/openapi.json: invalid JSON: {error}"]

    if not isinstance(schema, dict) or not isinstance(schema.get("paths"), dict):
        return ["contract/openapi.json: missing paths object"]

    api_text = docs_path.read_text(encoding="utf-8")
    missing = sorted(path for path in schema["paths"] if path not in api_text)

    if missing:
        return ["docs/api.md: missing OpenAPI paths: " + ", ".join(missing)]
    return []
