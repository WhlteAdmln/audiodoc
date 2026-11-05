import asyncio
import io

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException

from backend.api.middleware import BodySizeLimitMiddleware
from backend.common.limited_upload import read_upload_limited, save_upload_limited


def test_body_size_middleware_rejects_content_length_before_route():
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


def test_body_size_middleware_counts_streamed_body_without_content_length():
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


def test_read_upload_limited_accepts_file_at_limit():
    upload = UploadFile(file=io.BytesIO(b"12345"), filename="a.txt")
    assert asyncio.run(read_upload_limited(upload, 5)) == b"12345"


def test_read_upload_limited_rejects_file_over_limit():
    upload = UploadFile(file=io.BytesIO(b"123456"), filename="a.txt")
    with pytest.raises(HTTPException) as error:
        asyncio.run(read_upload_limited(upload, 5))
    assert error.value.status_code == 413


def test_save_upload_limited_rejects_file_over_limit(tmp_path, monkeypatch):
    import backend.common.limited_upload as upload_limits

    monkeypatch.setattr(upload_limits, "CHUNK_SIZE", 5)
    upload = UploadFile(file=io.BytesIO(b"123456"), filename="voice.ogg")
    target = tmp_path / "voice.ogg"
    with pytest.raises(HTTPException) as error:
        asyncio.run(save_upload_limited(upload, target, 5))
    assert error.value.status_code == 413
    assert target.read_bytes() == b"12345"
