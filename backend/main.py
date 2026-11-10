# Copyright (c) 2026 Nikolai Zelensky
"""FastAPI application factory and application lifecycle."""

import asyncio
import logging
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
from backend.common.work_queue import WorkQueue
from backend.config import Settings, get_settings
from backend.document_engine.limits import (
    MAX_CONCURRENT_DOCUMENTS,
    MAX_DOCUMENT_SIZE,
)
from backend.errors.base import ServerBusyError
from backend.transcription.model import ModelHolder
from backend.transcription.temp_files import cleanup_stale_files, ensure_temp_dir

API_VERSION = "1"  # Increment this on every breaking API change.

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Validate access configuration and initialize storage and Whisper."""
    configured_settings: Settings = _app.state.settings
    transcription_queue: WorkQueue = _app.state.transcription_queue
    document_queue: WorkQueue = _app.state.document_queue
    configure_logging(
        configured_settings.LOG_LEVEL,
        [
            part.strip()
            for value in (
                configured_settings.AUDIODOC_AUDIO_KEY,
                configured_settings.AUDIODOC_DOCUMENT_KEY,
            )
            for part in value.split(",")
        ],
    )
    if configured_settings.deprecated_environment_names:
        logger.warning(
            "Deprecated API key environment variables are in use: %s. "
            "Replace them with AUDIODOC_AUDIO_KEY and AUDIODOC_DOCUMENT_KEY.",
            ", ".join(configured_settings.deprecated_environment_names),
        )
    os.umask(0o077)
    check_security_settings(configured_settings)
    ensure_temp_dir()
    cleanup_stale_files()
    configured_model_holder = ModelHolder(configured_settings)
    _app.state.model_holder = configured_model_holder
    await asyncio.to_thread(configured_model_holder.load)
    transcription_queue.start()
    document_queue.start()
    try:
        yield
    finally:
        await asyncio.gather(
            transcription_queue.shutdown(),
            document_queue.shutdown(),
        )


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
    app.state.transcription_queue = WorkQueue(
        configured_settings.MAX_CONCURRENT_TRANSCRIPTIONS,
        configured_settings.MAX_WAITING_TRANSCRIPTIONS,
        error_factory=ServerBusyError,
    )
    app.state.document_queue = WorkQueue(
        MAX_CONCURRENT_DOCUMENTS,
        configured_settings.MAX_WAITING_DOCUMENTS,
        error_factory=ServerBusyError,
    )
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
