# Copyright (c) 2026 Nikolai Zelensky
"""Shared FastAPI dependencies for application resources."""

from fastapi import Request

from backend.transcription.model import ModelHolder, model_holder


def get_model_holder(request: Request) -> ModelHolder:
    """Return the model holder owned by the request application.

    The module-level holder remains a compatibility fallback during migration.
    """
    configured_holder: ModelHolder | None = getattr(
        request.app.state, "model_holder", None
    )
    return model_holder if configured_holder is None else configured_holder
