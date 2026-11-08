# Copyright (c) 2026 Nikolai Zelensky
"""Register the HTTP routers that expose backend services."""

from importlib import import_module
from typing import Protocol, cast

from fastapi import APIRouter, FastAPI


class _RouterModule(Protocol):
    router: APIRouter


def register_routes(app: FastAPI) -> None:
    """Attach health, transcription, and document routers to an app.

    Args:
        app: FastAPI application receiving the API routers.

    Returns:
        None.

    """
    # Import routers only when assembling the application. This keeps helpers
    # such as backend.api.auth independently importable in narrow unit tests.
    documents = cast(
        "_RouterModule",
        import_module(".documents", package=__name__),
    )
    health = cast("_RouterModule", import_module(".health", package=__name__))
    ready = cast("_RouterModule", import_module(".ready", package=__name__))
    transcribe = cast(
        "_RouterModule",
        import_module(".transcribe", package=__name__),
    )

    app.include_router(health.router)
    app.include_router(ready.router)
    app.include_router(transcribe.router)
    app.include_router(documents.router)


__all__ = ["register_routes"]
