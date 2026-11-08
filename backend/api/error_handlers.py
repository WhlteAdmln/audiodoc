# Copyright (c) 2026 Nikolai Zelensky
"""Translate backend and unexpected exceptions into safe HTTP responses."""

import logging
from typing import cast

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.errors.base import BackendError

logger = logging.getLogger(__name__)


async def handle_backend_error(
    _request: Request,
    error: Exception,
) -> JSONResponse:
    """Return the public error message, status code, and optional headers."""
    backend_error = cast("BackendError", error)
    return JSONResponse(
        {"detail": backend_error.public_message},
        status_code=backend_error.status_code,
        headers=backend_error.headers,
    )


async def handle_unexpected_error(
    _request: Request,
    error: Exception,
) -> JSONResponse:
    """Log an unexpected failure and hide its implementation details."""
    logger.error(
        "Unhandled backend exception",
        exc_info=(type(error), error, error.__traceback__),
    )
    return JSONResponse(
        {"detail": "Internal server error"},
        status_code=500,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register handlers for typed errors and unexpected exceptions."""
    app.add_exception_handler(BackendError, handle_backend_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
