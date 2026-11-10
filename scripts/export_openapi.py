# Copyright (c) 2026 Nikolai Zelensky
"""Export the stable OpenAPI contract snapshot."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from audiodoc.config import Settings
from audiodoc.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = PROJECT_ROOT / "contract" / "openapi.json"


def render_openapi() -> str:
    """Build and serialize the OpenAPI schema with stable key ordering."""
    schema = create_app(Settings(ENABLE_DOCS=True)).openapi()
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def main() -> int:
    """Write the current OpenAPI schema to the contract snapshot."""
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(render_openapi(), encoding="utf-8")
    sys.stdout.write(f"Wrote {SNAPSHOT_PATH.relative_to(PROJECT_ROOT)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
