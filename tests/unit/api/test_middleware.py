# Copyright (c) 2026 Nikolai Zelensky

"""Tests for api middleware."""

import asyncio
import contextlib

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.types import Message, Receive, Scope, Send

from audiodoc.api.middleware import BodySizeLimitMiddleware


def test_body_size_middleware_rejects_content_length_before_route() -> None:
    route_called = False
    test_app = FastAPI()

    @test_app.post("/upload")
    async def upload(request: Request) -> object:
        nonlocal route_called
        route_called = True
        return {"size": len(await request.body())}

    test_app.add_middleware(BodySizeLimitMiddleware, max_body_size=10)
    response = TestClient(test_app).post("/upload", content=b"x" * 11)

    expected_status_code = 413
    assert response.status_code == expected_status_code
    assert route_called is False


def test_body_size_middleware_counts_streamed_body_without_content_length() -> None:
    async def app(_scope: object, receive: object, send: object) -> None:
        # Force the downstream app to consume the complete request body.
        while True:
            message = await receive()
            expected_type = "http.request"
            if message["type"] == expected_type and not message.get("more_body"):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    middleware = BodySizeLimitMiddleware(app, max_body_size=5)
    messages = [
        {"type": "http.request", "body": b"123", "more_body": True},
        {"type": "http.request", "body": b"456", "more_body": False},
    ]
    sent = []

    async def receive() -> object:
        return messages.pop(0)

    async def send(message: object) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/upload",
        "raw_path": b"/upload",
        "query_string": b"",
        "headers": [],
        "server": ("testserver", 80),
        "client": ("testclient", 12345),
    }
    asyncio.run(middleware(scope, receive, send))

    expected_type = "http.response.start"
    start = next(message for message in sent if message["type"] == expected_type)
    expected_status = 413
    assert start["status"] == expected_status


@pytest.mark.parametrize("content_length", [None, b"invalid", b"5"])
def test_body_size_middleware_accepts_body_within_limit(
    content_length: bytes | None,
) -> None:
    sent: list[Message] = []

    async def app(_scope: Scope, receive: Receive, send: Send) -> None:
        message = await receive()
        expected_body = b"12345"
        assert message["body"] == expected_body
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [],
            }
        )
        await send({"type": "http.response.body", "body": b"ok"})

    async def receive() -> Message:
        return {
            "type": "http.request",
            "body": b"12345",
            "more_body": False,
        }

    async def send(message: Message) -> None:
        sent.append(message)

    headers = [] if content_length is None else [(b"content-length", content_length)]
    middleware = BodySizeLimitMiddleware(app, max_body_size=5)
    asyncio.run(
        middleware(
            {"type": "http", "headers": headers},
            receive,
            send,
        )
    )

    expected_status = 200
    assert sent[0]["status"] == expected_status


def test_body_size_middleware_rejects_non_positive_limit() -> None:
    async def app(_scope: Scope, _receive: Receive, _send: Send) -> None:
        raise AssertionError

    with pytest.raises(ValueError, match="max_body_size must be positive"):
        BodySizeLimitMiddleware(app, max_body_size=0)


def test_body_size_middleware_passes_non_http_scopes() -> None:
    called = False

    async def app(_scope: Scope, _receive: Receive, _send: Send) -> None:
        nonlocal called
        called = True

    async def receive() -> Message:
        raise AssertionError

    async def send(_message: Message) -> None:
        raise AssertionError

    middleware = BodySizeLimitMiddleware(app, max_body_size=5)
    asyncio.run(middleware({"type": "lifespan"}, receive, send))

    assert called is True


def test_body_size_middleware_ignores_disconnect_messages() -> None:
    sent: list[Message] = []

    async def app(_scope: Scope, receive: Receive, send: Send) -> None:
        message = await receive()
        expected_type = "http.disconnect"
        assert message["type"] == expected_type
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [],
            }
        )

    async def receive() -> Message:
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        sent.append(message)

    middleware = BodySizeLimitMiddleware(app, max_body_size=5)
    asyncio.run(
        middleware(
            {"type": "http", "headers": []},
            receive,
            send,
        )
    )

    expected_status = 200
    assert sent[0]["status"] == expected_status


def test_body_size_middleware_does_not_replace_started_response() -> None:
    sent: list[Message] = []

    async def app(_scope: Scope, receive: Receive, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [],
            }
        )
        await receive()

    async def receive() -> Message:
        return {
            "type": "http.request",
            "body": b"123456",
            "more_body": False,
        }

    async def send(message: Message) -> None:
        sent.append(message)

    middleware = BodySizeLimitMiddleware(app, max_body_size=5)
    asyncio.run(
        middleware(
            {"type": "http", "headers": []},
            receive,
            send,
        )
    )

    assert [message["type"] for message in sent] == ["http.response.start"]


def test_body_size_middleware_replaces_downstream_error_after_oversized_body() -> None:
    sent: list[Message] = []

    async def app(_scope: Scope, receive: Receive, send: Send) -> None:
        with contextlib.suppress(Exception):
            await receive()
        await send(
            {
                "type": "http.response.start",
                "status": 400,
                "headers": [],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b"Invalid multipart body",
            }
        )

    async def receive() -> Message:
        return {
            "type": "http.request",
            "body": b"123456",
            "more_body": False,
        }

    async def send(message: Message) -> None:
        sent.append(message)

    middleware = BodySizeLimitMiddleware(app, max_body_size=5)
    asyncio.run(
        middleware(
            {"type": "http", "headers": []},
            receive,
            send,
        )
    )

    expected_type = "http.response.start"
    start = next(message for message in sent if message["type"] == expected_type)
    expected_type = "http.response.body"
    body = next(message for message in sent if message["type"] == expected_type)
    expected_status = 413
    assert start["status"] == expected_status
    expected_body = b'{"detail":"Request body too large"}'
    assert body["body"] == expected_body
