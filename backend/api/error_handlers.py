# Copyright (c) 2026 Nikolai Zelensky
"""Translate backend and unexpected exceptions into safe HTTP responses."""

import logging
from typing import cast

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.errors.base import AppError

logger = logging.getLogger(__name__)


async def handle_backend_error(
    _request: Request,
    error: Exception,
) -> JSONResponse:
    """Return the public error message, code, status, and optional headers."""
    app_error = cast("AppError", error)
    return JSONResponse(
        {"detail": app_error.public_message, "code": app_error.code},
        status_code=app_error.status_code,
        headers=app_error.headers,
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
        {"detail": "Internal server error", "code": "internal_error"},
        status_code=500,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register handlers for typed errors and unexpected exceptions."""
    app.add_exception_handler(AppError, handle_backend_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
