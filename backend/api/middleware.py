"""ASGI middleware that rejects oversized request bodies before parsing multipart."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class _RequestBodyTooLargeError(Exception):
    pass


class BodySizeLimitMiddleware:
    """Reject HTTP bodies larger than ``max_body_size`` bytes."""

    def __init__(self, app: ASGIApp, max_body_size: int) -> None:
        if max_body_size <= 0:
            raise ValueError("max_body_size must be positive")
        self.app = app
        self.max_body_size = max_body_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        declared = headers.get(b"content-length")
        if declared and declared.isdigit() and int(declared) > self.max_body_size:
            response = JSONResponse(
                {"detail": "Request body too large"},
                status_code=413,
            )
            await response(scope, receive, send)
            return

        received = 0
        response_started = False

        async def tracked_send(message: Message) -> None:
            """Pass the response message to the downstream ASGI application."""
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        async def limited_receive() -> Message:
            """Count request bytes and stop the stream after the body limit."""
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body_size:
                    raise _RequestBodyTooLargeError
            return message

        try:
            await self.app(scope, limited_receive, tracked_send)
        except _RequestBodyTooLargeError:
            # If the downstream application already started a response, it cannot
            # be replaced safely. Multipart handlers read the body before replying.
            if response_started:
                return
            response = JSONResponse(
                {"detail": "Request body too large"},
                status_code=413,
            )
            await response(scope, receive, send)
