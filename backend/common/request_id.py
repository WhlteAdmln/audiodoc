"""Request-scoped correlation IDs for HTTP responses and application logs."""

import contextvars
import logging
import re
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{8,64}")


class RequestIdMiddleware:
    """Validate or create X-Request-ID and echo it on every HTTP response."""

    def __init__(self, app: ASGIApp) -> None:
        """Initialize the middleware with the downstream ASGI application.

        Args:
            app: Downstream ASGI application.
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process an ASGI request with a validated correlation ID."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        supplied = headers.get(b"x-request-id", b"").decode("latin-1")
        request_id = (
            supplied if _VALID_REQUEST_ID.fullmatch(supplied) else uuid.uuid4().hex
        )
        token = request_id_var.set(request_id)

        async def send_with_request_id(message: Message) -> None:
            """Echo the validated identifier on the ASGI response start."""
            if message["type"] == "http.response.start":
                response_headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() != b"x-request-id"
                ]
                response_headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = response_headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            request_id_var.reset(token)


class RequestIdFilter(logging.Filter):
    """Add the current request ID to each log record handled by the root logger."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Attach the active request ID to the log record."""
        record.request_id = request_id_var.get()
        return True
