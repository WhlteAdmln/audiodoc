# Copyright (c) 2026 Nikolai Zelensky
"""Shared FastAPI dependencies for application resources."""

from typing import cast

from fastapi import Request

from backend.common.work_queue import WorkQueue
from backend.transcription.model import ModelHolder


def get_model_holder(request: Request) -> ModelHolder:
    """Return the model holder owned by the request application."""
    return cast("ModelHolder", request.app.state.model_holder)


def get_transcription_queue(request: Request) -> WorkQueue:
    """Return the transcription queue owned by the request application."""
    return cast("WorkQueue", request.app.state.transcription_queue)


def get_document_queue(request: Request) -> WorkQueue:
    """Return the document queue owned by the request application."""
    return cast("WorkQueue", request.app.state.document_queue)
