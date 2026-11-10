# Copyright (c) 2026 Nikolai Zelensky
"""Application entry point for the Uvicorn server."""

from importlib import import_module

from fastapi import FastAPI


def _create_compatibility_app() -> FastAPI:
    """Create the Uvicorn app without loading environment files."""
    main_module = import_module("audiodoc.main")
    return main_module.create_app()


app = _create_compatibility_app()
