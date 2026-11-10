# Copyright (c) 2026 Nikolai Zelensky
"""Command-line entry point for the audiodoc server."""

import uvicorn

from backend.config import load_env_file


def main() -> None:
    """Load the environment and start the application server."""
    load_env_file()
    uvicorn.run("backend.main:create_app", factory=True)
