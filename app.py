# Copyright (c) 2026 Nikolai Zelensky
"""Application entry point for the Uvicorn server."""

from fastapi import FastAPI

from backend.config import load_env_file
from backend.main import create_app


def _create_compatibility_app() -> FastAPI:
    """Load the legacy environment file before creating the Uvicorn app."""
    load_env_file()
    return create_app()


app = _create_compatibility_app()
