# Copyright (c) 2026 Nikolai Zelensky
"""Bearer authentication dependencies and fail-closed startup validation."""

import hmac
from collections.abc import Awaitable, Callable

from fastapi import Header, HTTPException

from backend.config import Settings


def require_key(
    get_expected: Callable[[], str],
) -> Callable[..., Awaitable[None]]:
    """Return a FastAPI dependency validating Authorization: Bearer <key>."""

    async def dependency(authorization: str | None = Header(default=None)) -> None:
        """Validate the request header against the current expected key value."""
        expected = get_expected()
        if not expected:
            # Startup validation permits this only for explicit local development.
            return

        scheme, _, token = (authorization or "").partition(" ")
        accepted_keys = [key.strip() for key in expected.split(",") if key.strip()]
        supplied = token.strip()
        valid = scheme.lower() == "bearer" and any(
            hmac.compare_digest(supplied.encode("utf-8"), key.encode("utf-8"))
            for key in accepted_keys
        )

        if not valid:
            raise HTTPException(
                status_code=401,
                detail="Unauthorized",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return dependency


def check_security_settings(settings: Settings) -> None:
    """Fail closed when API keys are absent unless local bypass is explicit."""
    missing = []
    for name in ("WHISPER_API_KEY", "DOCUMENT_API_KEY"):
        configured = [
            key.strip() for key in getattr(settings, name, "").split(",") if key.strip()
        ]
        if not configured:
            missing.append(name)

    if missing and not settings.ALLOW_UNAUTHENTICATED:
        raise RuntimeError(
            "\u041d\u0435 заданы ключи: " + ", ".join(missing) + ". "
            "Задайте их в .env (те же значения, что в .env бота) "
            "или поставьте ALLOW_UNAUTHENTICATED=true только для локальной разработки."
        )
