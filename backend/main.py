# Copyright (c) 2026 Nikolai Zelensky
"""FastAPI application factory and application lifecycle."""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Resolve the dotenv path before importing backend.config: its package initializer
# eagerly imports Settings; importing config.paths here would load settings too early.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=False)

from fastapi import FastAPI  # noqa: E402

from backend.api import register_routes  # noqa: E402
from backend.api.auth import check_security_settings  # noqa: E402
from backend.api.error_handlers import register_error_handlers  # noqa: E402
from backend.api.middleware import BodySizeLimitMiddleware  # noqa: E402
from backend.common.logging_setup import configure_logging  # noqa: E402
from backend.common.request_id import RequestIdMiddleware  # noqa: E402
from backend.config import settings  # noqa: E402
from backend.document_engine import document_queue  # noqa: E402
from backend.document_engine.limits import MAX_DOCUMENT_SIZE  # noqa: E402
from backend.transcription.model import model_holder  # noqa: E402
from backend.transcription.temp_files import (  # noqa: E402
    cleanup_stale_files,
    ensure_temp_dir,
)

configure_logging(
    settings.LOG_LEVEL,
    [
        part.strip()
        for value in (settings.WHISPER_API_KEY, settings.DOCUMENT_API_KEY)
        for part in value.split(",")
    ],
)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Validate access configuration and initialize storage and Whisper."""
    os.umask(0o077)
    check_security_settings(settings)
    ensure_temp_dir()
    cleanup_stale_files()
    await asyncio.to_thread(model_holder.load)
    yield


def create_app() -> FastAPI:
    """Create the FastAPI application, middleware, and API routes.

    Returns:
        A configured FastAPI application using the backend lifespan handler.

    """
    app = FastAPI(
        title="audiodoc",
        lifespan=lifespan,
        docs_url="/docs" if settings.ENABLE_DOCS else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.ENABLE_DOCS else None,
    )
    document_queue.set_max_waiting(settings.MAX_WAITING_DOCUMENTS)
    register_error_handlers(app)
    app.add_middleware(
        BodySizeLimitMiddleware,
        max_body_size=max(MAX_DOCUMENT_SIZE, settings.MAX_AUDIO_SIZE) + 1024 * 1024,
    )
    # Keep request ID outermost so even early body-size rejections carry it.
    app.add_middleware(RequestIdMiddleware)
    register_routes(app)
    return app


app = create_app()
