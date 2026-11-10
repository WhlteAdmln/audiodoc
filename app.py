# Copyright (c) 2026 Nikolai Zelensky
"""Application entry point for the Uvicorn server."""

from importlib import import_module

from fastapi import FastAPI

from audiodoc.config import load_env_file


def _create_compatibility_app() -> FastAPI:
    """Load the legacy environment file before creating the Uvicorn app."""
    load_env_file()
    main_module = import_module("audiodoc.main")
    return main_module.create_app()


app = _create_compatibility_app()
