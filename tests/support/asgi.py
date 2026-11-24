# Copyright (c) 2026 Nikolai Zelensky
"""Fake ASGI applications, receive channels and send channels for middleware tests."""

import contextlib
from collections.abc import Iterable

from starlette.types import Message, Receive, Scope, Send

HTTP_SCOPE_TYPE = "http"
HTTP_REQUEST = "http.request"
HTTP_RESPONSE_START = "http.response.start"
HTTP_RESPONSE_BODY = "http.response.body"


def http_scope(headers: Iterable[tuple[bytes, bytes]] = ()) -> Scope:
    """Build a minimal HTTP scope with the given raw headers."""
    return {
        "type": HTTP_SCOPE_TYPE,
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/upload",
        "raw_path": b"/upload",
        "query_string": b"",
        "headers": list(headers),
        "server": ("testserver", 80),
        "client": ("testclient", 12345),
    }


def body_messages(*chunks: bytes) -> list[Message]:
    """Split a request body into ``http.request`` messages."""
    last = len(chunks) - 1
    return [
        {"type": HTTP_REQUEST, "body": chunk, "more_body": index < last}
        for index, chunk in enumerate(chunks)
    ]


class ScriptedReceive:
    """Hand out prepared messages, then report a disconnect."""

    def __init__(self, messages: Iterable[Message]) -> None:
        """Store the messages in the order they are received."""
        self.messages = list(messages)

    async def __call__(self) -> Message:
        """Return the next prepared message."""
        if self.messages:
            return self.messages.pop(0)
        return {"type": "http.disconnect"}


class RecordingSend:
    """Keep every message the application sends."""

    def __init__(self) -> None:
        """Start with no messages."""
        self.messages: list[Message] = []

    async def __call__(self, message: Message) -> None:
        """Record one message."""
        self.messages.append(message)

    @property
    def types(self) -> list[str]:
        """Return the types of the recorded messages in order."""
        return [message["type"] for message in self.messages]

    @property
    def status(self) -> int | None:
        """Return the status of the first response start, if any."""
        for message in self.messages:
            if message["type"] == HTTP_RESPONSE_START:
                return int(message["status"])
        return None

    @property
    def body(self) -> bytes:
        """Return the concatenated response body."""
        return b"".join(
            message.get("body", b"")
            for message in self.messages
            if message["type"] == HTTP_RESPONSE_BODY
        )

    def header_values(self, name: bytes) -> list[bytes]:
        """Return every value of one response header, by lower-case name."""
        values: list[bytes] = []
        for message in self.messages:
            if message["type"] == HTTP_RESPONSE_START:
                values.extend(
                    value
                    for key, value in message.get("headers", [])
                    if key.lower() == name
                )
        return values


class BodyReadingApp:
    """Read the whole request body, then answer with a fixed response."""

    def __init__(
        self,
        status: int = 200,
        headers: Iterable[tuple[bytes, bytes]] = (),
    ) -> None:
        """Store the response the application sends."""
        self.status = status
        self.headers = list(headers)
        self.calls = 0
        self.received: list[Message] = []

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Consume the request and respond."""
        self.calls += 1
        if scope["type"] != HTTP_SCOPE_TYPE:
            return
        while True:
            message = await receive()
            self.received.append(message)
            if message["type"] != HTTP_REQUEST or not message.get("more_body"):
                break
        await send(
            {
                "type": HTTP_RESPONSE_START,
                "status": self.status,
                "headers": self.headers,
            }
        )
        await send({"type": HTTP_RESPONSE_BODY, "body": b"ok"})


class EarlyResponseApp:
    """Start the response before reading the request body."""

    async def __call__(self, _scope: Scope, receive: Receive, send: Send) -> None:
        """Send the response start, then read the body."""
        await send({"type": HTTP_RESPONSE_START, "status": 200, "headers": []})
        await receive()


class ErrorSwallowingApp:
    """Hide a failed body read and answer with its own error response."""

    async def __call__(self, _scope: Scope, receive: Receive, send: Send) -> None:
        """Read once, ignore any error and send a 400 response."""
        with contextlib.suppress(Exception):
            await receive()
        await send({"type": HTTP_RESPONSE_START, "status": 400, "headers": []})
        await send({"type": HTTP_RESPONSE_BODY, "body": b"Invalid multipart body"})
