# Copyright (c) 2026 Nikolai Zelensky
"""Application and queue helpers for API unit tests."""

import asyncio

from fastapi import APIRouter, FastAPI

from audiodoc.api.error_handlers import register_error_handlers
from audiodoc.common.work_queue import WorkQueue
from audiodoc.errors.base import ServerBusyError
from audiodoc.transcription.model import ModelHolder


def app_with_router(
    router: APIRouter,
    *,
    model_holder: ModelHolder | None = None,
    document_queue: WorkQueue | None = None,
    transcription_queue: WorkQueue | None = None,
) -> FastAPI:
    """Build an app with the router, error handlers and the given state."""
    app = FastAPI()
    if model_holder is not None:
        app.state.model_holder = model_holder
    if document_queue is not None:
        app.state.document_queue = document_queue
    if transcription_queue is not None:
        app.state.transcription_queue = transcription_queue
    register_error_handlers(app)
    app.include_router(router)
    return app


def closed_queue() -> WorkQueue:
    """Return a work queue that is already shut down."""
    queue = WorkQueue(workers=1, max_waiting=0, error_factory=ServerBusyError)
    asyncio.run(queue.shutdown())
    return queue
