# Copyright (c) 2026 Nikolai Zelensky
"""Shared FastAPI dependencies for application resources."""

from typing import cast

from fastapi import Request

from backend.transcription.model import ModelHolder


def get_model_holder(request: Request) -> ModelHolder:
    """Return the model holder owned by the request application."""
    return cast("ModelHolder", request.app.state.model_holder)
