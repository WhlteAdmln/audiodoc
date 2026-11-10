# Copyright (c) 2026 Nikolai Zelensky
"""ASGI middleware that rejects oversized request bodies before parsing multipart."""

from dataclasses import dataclass

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class _InvalidBodySizeLimitError(ValueError):
    """Raised when the configured request body size limit is invalid."""

    def __init__(self) -> None:
        """Initialize the validation error."""
        super().__init__("max_body_size must be positive")


class _RequestBodyTooLargeError(Exception):
    pass


@dataclass(slots=True)
class _BodyLimitState:
    """Track request size and response state during one HTTP request."""

    received: int = 0
    response_started: bool = False
    body_too_large: bool = False
    response_replaced: bool = False


def _declared_body_exceeds_limit(scope: Scope, max_body_size: int) -> bool:
    """Check whether Content-Length exceeds the configured body limit."""
    declared = dict(scope.get("headers", [])).get(b"content-length")
    return bool(declared and declared.isdigit() and int(declared) > max_body_size)


async def _send_body_too_large_response(
    scope: Scope,
    receive: Receive,
    send: Send,
) -> None:
    """Send the standard response for an oversized request body."""
    response = JSONResponse(
        {"detail": "Request body too large"},
        status_code=413,
    )
    await response(scope, receive, send)


class _LimitedReceive:
    """Receive ASGI request messages while enforcing the body limit."""

    def __init__(
        self,
        receive: Receive,
        state: _BodyLimitState,
        max_body_size: int,
    ) -> None:
        """Initialize the limited receiver."""
        self.receive = receive
        self.state = state
        self.max_body_size = max_body_size

    async def __call__(self) -> Message:
        """Receive a message and reject bodies exceeding the limit."""
        message = await self.receive()
        if message["type"] == "http.request":
            self.state.received += len(message.get("body", b""))
            if self.state.received > self.max_body_size:
                self.state.body_too_large = True
                raise _RequestBodyTooLargeError
        return message


class _TrackedSend:
    """Track response messages and replace downstream oversized-body errors."""

    def __init__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        state: _BodyLimitState,
    ) -> None:
        """Initialize the tracked sender."""
        self.scope = scope
        self.receive = receive
        self.send = send
        self.state = state

    async def __call__(self, message: Message) -> None:
        """Forward response messages while preserving the body-limit response."""
        if self.state.response_replaced:
            return
        if self.state.body_too_large and not self.state.response_started:
            if message["type"] == "http.response.start":
                self.state.response_started = True
                self.state.response_replaced = True
                await _send_body_too_large_response(
                    self.scope,
                    self.receive,
                    self.send,
                )
            return
        if message["type"] == "http.response.start":
            self.state.response_started = True
        await self.send(message)


class BodySizeLimitMiddleware:
    """Reject HTTP bodies larger than ``max_body_size`` bytes."""

    def __init__(self, app: ASGIApp, max_body_size: int) -> None:
        """Initialize the middleware with an ASGI app and body size limit.

        Args:
            app: Downstream ASGI application.
            max_body_size: Maximum permitted request body size in bytes.
        """
        if max_body_size <= 0:
            raise _InvalidBodySizeLimitError
        self.app = app
        self.max_body_size = max_body_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process an ASGI request and enforce the body size limit."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if _declared_body_exceeds_limit(scope, self.max_body_size):
            await _send_body_too_large_response(scope, receive, send)
            return

        state = _BodyLimitState()
        try:
            await self.app(
                scope,
                _LimitedReceive(receive, state, self.max_body_size),
                _TrackedSend(scope, receive, send, state),
            )
        except _RequestBodyTooLargeError:
            # Do not replace a response that has already started.
            if not state.response_started:
                await _send_body_too_large_response(scope, receive, send)
