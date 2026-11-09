# Copyright (c) 2026 Nikolai Zelensky
"""FastAPI application factory and application lifecycle."""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api import register_routes
from backend.api.auth import check_security_settings
from backend.api.error_handlers import register_error_handlers
from backend.api.middleware import BodySizeLimitMiddleware
from backend.common.logging_setup import configure_logging
from backend.common.request_id import RequestIdMiddleware
from backend.config import Settings, get_settings
from backend.document_engine import document_queue
from backend.document_engine.limits import MAX_DOCUMENT_SIZE
from backend.transcription.model import ModelHolder
from backend.transcription.temp_files import cleanup_stale_files, ensure_temp_dir

API_VERSION = "1"  # Increment this on every breaking API change.


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Validate access configuration and initialize storage and Whisper."""
    configured_settings: Settings = _app.state.settings
    configure_logging(
        configured_settings.LOG_LEVEL,
        [
            part.strip()
            for value in (
                configured_settings.WHISPER_API_KEY,
                configured_settings.DOCUMENT_API_KEY,
            )
            for part in value.split(",")
        ],
    )
    os.umask(0o077)
    check_security_settings(configured_settings)
    ensure_temp_dir()
    cleanup_stale_files()
    document_queue.set_max_waiting(configured_settings.MAX_WAITING_DOCUMENTS)
    await asyncio.to_thread(_app.state.model_holder.load)
    document_queue.start()
    try:
        yield
    finally:
        await document_queue.shutdown()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create a FastAPI application using the supplied configuration.

    Args:
        settings: Application configuration; process settings are used by default.

    Returns:
        A configured FastAPI application.
    """
    configured_settings = get_settings() if settings is None else settings
    docs_enabled = configured_settings.ENABLE_DOCS
    app = FastAPI(
        title="audiodoc",
        version=API_VERSION,
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.state.settings = configured_settings
    app.state.model_holder = ModelHolder(configured_settings)
    register_error_handlers(app)
    app.add_middleware(
        BodySizeLimitMiddleware,
        max_body_size=max(MAX_DOCUMENT_SIZE, configured_settings.MAX_AUDIO_SIZE)
        + 1024 * 1024,
    )
    # Keep request ID outermost so even early body-size rejections carry it.
    app.add_middleware(RequestIdMiddleware)
    register_routes(app)
    return app
