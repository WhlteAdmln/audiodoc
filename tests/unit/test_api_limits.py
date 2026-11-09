# Copyright (c) 2026 Nikolai Zelensky
import asyncio
import io

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from starlette.types import Message, Receive, Scope, Send

import backend.common.limited_upload as upload_limits
from backend.api.middleware import (
    BodySizeLimitMiddleware,
    _RequestBodyTooLargeError,
)
from backend.common.limited_upload import read_upload_limited, save_upload_limited


def test_body_size_middleware_rejects_content_length_before_route() -> None:
    route_called = False
    test_app = FastAPI()

    @test_app.post("/upload")
    async def upload(request: Request):
        nonlocal route_called
        route_called = True
        return {"size": len(await request.body())}

    test_app.add_middleware(BodySizeLimitMiddleware, max_body_size=10)
    response = TestClient(test_app).post("/upload", content=b"x" * 11)

    assert response.status_code == 413
    assert route_called is False


def test_body_size_middleware_counts_streamed_body_without_content_length() -> None:
    async def app(scope, receive, send):
        # Force the downstream app to consume the complete request body.
        while True:
            message = await receive()
            if message["type"] == "http.request" and not message.get("more_body"):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    middleware = BodySizeLimitMiddleware(app, max_body_size=5)
    messages = [
        {"type": "http.request", "body": b"123", "more_body": True},
        {"type": "http.request", "body": b"456", "more_body": False},
    ]
    sent = []

    async def receive():
        return messages.pop(0)

    async def send(message):
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

    start = next(
        message for message in sent if message["type"] == "http.response.start"
    )
    assert start["status"] == 413


@pytest.mark.parametrize("content_length", [None, b"invalid", b"5"])
def test_body_size_middleware_accepts_body_within_limit(
    content_length: bytes | None,
) -> None:
    sent: list[Message] = []

    async def app(_scope: Scope, receive: Receive, send: Send) -> None:
        message = await receive()
        assert message["body"] == b"12345"
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

    assert sent[0]["status"] == 200


def test_read_upload_limited_accepts_file_at_limit() -> None:
    upload = UploadFile(file=io.BytesIO(b"12345"), filename="a.txt")
    assert asyncio.run(read_upload_limited(upload, 5)) == b"12345"


def test_read_upload_limited_rejects_file_over_limit() -> None:
    upload = UploadFile(file=io.BytesIO(b"123456"), filename="a.txt")
    with pytest.raises(HTTPException) as error:
        asyncio.run(read_upload_limited(upload, 5))
    assert error.value.status_code == 413


def test_save_upload_limited_rejects_file_over_limit(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(upload_limits, "CHUNK_SIZE", 5)
    upload = UploadFile(file=io.BytesIO(b"123456"), filename="voice.ogg")
    target = tmp_path / "voice.ogg"
    with pytest.raises(HTTPException) as error:
        asyncio.run(save_upload_limited(upload, target, 5))
    assert error.value.status_code == 413
    assert target.read_bytes() == b"12345"


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
        assert message["type"] == "http.disconnect"
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

    assert sent[0]["status"] == 200


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
        try:
            await receive()
        except _RequestBodyTooLargeError:
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

    start = next(
        message for message in sent if message["type"] == "http.response.start"
    )
    body = next(message for message in sent if message["type"] == "http.response.body")
    assert start["status"] == 413
    assert body["body"] == b'{"detail":"Request body too large"}'
