"""Register the HTTP routers that expose backend services."""

from fastapi import FastAPI


def register_routes(app: FastAPI) -> None:
    """Attach health, transcription, and document routers to an app.

    Args:
        app: FastAPI application receiving the API routers.

    Returns:
        None.

    """
    # Import routers only when assembling the application. This keeps helpers
    # such as backend.api.auth independently importable in narrow unit tests.
    from backend.api import documents, health, ready, transcribe

    app.include_router(health.router)
    app.include_router(ready.router)
    app.include_router(transcribe.router)
    app.include_router(documents.router)


__all__ = ["register_routes"]
