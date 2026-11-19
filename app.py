# Copyright (c) 2026 Nikolai Zelensky
"""Deprecated Uvicorn entry point kept for `uvicorn app:app` compatibility.

New installations run `audiodoc run`. This module exists so that systemd units
written for audiodoc 0.1.0 keep working after an upgrade. It will be removed in
0.3.0.
"""

from importlib import import_module

from fastapi import FastAPI


def _create_compatibility_app() -> FastAPI:
    """Load the environment files, then create the Uvicorn application."""
    env_module = import_module("audiodoc.env_readers")
    env_module.load_env_file()
    main_module = import_module("audiodoc.main")
    return main_module.create_app()


app = _create_compatibility_app()
