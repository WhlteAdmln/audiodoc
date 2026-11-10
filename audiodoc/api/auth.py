# Copyright (c) 2026 Nikolai Zelensky
"""Bearer authentication dependencies and fail-closed startup validation."""

import hmac
from collections.abc import Awaitable, Callable

from fastapi import Header, HTTPException, Request

from audiodoc.config import Settings, get_settings


class _SharedAPIKeyError(RuntimeError):
    """Raised when API keys are shared between protected APIs."""

    def __init__(self) -> None:
        """Initialize the shared API key error."""
        super().__init__(
            "AUDIODOC_AUDIO_KEY and AUDIODOC_DOCUMENT_KEY "
            "must not share any key values."
        )


def require_key(
    get_expected: Callable[[Settings], str],
) -> Callable[..., Awaitable[None]]:
    """Return a FastAPI dependency validating Authorization: Bearer <key>."""

    async def dependency(
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> None:
        """Validate the request header against the current expected key value."""
        configured_settings: Settings | None = getattr(
            request.app.state, "settings", None
        )
        if configured_settings is None:
            # Preserve compatibility for routers mounted without create_app().
            configured_settings = get_settings()
        expected = get_expected(configured_settings)
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
    """Fail closed when API keys are absent or shared between APIs."""
    missing: list[str] = []
    configured_keys: dict[str, set[str]] = {}
    key_settings = (
        ("AUDIODOC_AUDIO_KEY", "WHISPER_API_KEY"),
        ("AUDIODOC_DOCUMENT_KEY", "DOCUMENT_API_KEY"),
    )

    for name, legacy_name in key_settings:
        value = getattr(settings, name, "") or getattr(settings, legacy_name, "")
        configured = {key.strip() for key in value.split(",") if key.strip()}
        configured_keys[name] = configured

        if not configured:
            missing.append(f"{name} (legacy: {legacy_name})")

    if missing and not settings.ALLOW_UNAUTHENTICATED:
        raise RuntimeError(
            "Missing API keys: " + ", ".join(missing) + ". "
            "Set them in .env (using the same values as in the bot's .env) "
            "or set ALLOW_UNAUTHENTICATED=true for local development only."
        )

    if configured_keys["AUDIODOC_AUDIO_KEY"] & configured_keys["AUDIODOC_DOCUMENT_KEY"]:
        raise _SharedAPIKeyError
