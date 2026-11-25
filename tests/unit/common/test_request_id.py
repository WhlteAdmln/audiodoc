# Copyright (c) 2026 Nikolai Zelensky

"""Tests for common request id."""

import asyncio
import logging
import re

import pytest
from starlette.types import Receive, Scope, Send

from audiodoc.common.request_id import (
    RequestIdFilter,
    RequestIdMiddleware,
    request_id_var,
)
from tests.support.asgi import (
    BodyReadingApp,
    RecordingSend,
    ScriptedReceive,
    http_scope,
)

HEADER = b"x-request-id"
UUID_HEX = re.compile(rb"[0-9a-f]{32}")


def _respond(
    supplied: bytes | None, downstream_headers: list[tuple[bytes, bytes]] | None = None
) -> RecordingSend:
    headers = [] if supplied is None else [(HEADER, supplied)]
    send = RecordingSend()
    middleware = RequestIdMiddleware(BodyReadingApp(headers=downstream_headers or []))
    asyncio.run(middleware(http_scope(headers), ScriptedReceive([]), send))
    return send


@pytest.mark.parametrize(
    "supplied",
    [b"trace-2026_11.05", b"abcdefgh", b"Z" * 64, b"0.0.0.0-_"],
    ids=["mixed", "shortest", "longest", "dots"],
)
def test_echoes_a_valid_request_id(supplied: bytes) -> None:
    send = _respond(supplied)

    assert send.header_values(HEADER) == [supplied], "a valid id was not echoed"


@pytest.mark.parametrize(
    "supplied",
    [
        b"",
        b"abc1234",
        b"Z" * 65,
        b"not a valid id",
        b"evil\r\nSet-Cookie: session=stolen",
        b"../../etc/passwd",
        "запрос-12345678".encode(),
        b"\xff\xfe\x00\x01\x02\x03\x04\x05",
        b"<script>alert(1)</script>",
        b"id%0d%0aX-Injected:1",
    ],
    ids=[
        "empty",
        "too-short",
        "too-long",
        "spaces",
        "crlf",
        "path",
        "cyrillic",
        "binary",
        "markup",
        "encoded-crlf",
    ],
)
def test_replaces_an_unsafe_request_id_with_a_uuid(supplied: bytes) -> None:
    send = _respond(supplied)

    shapes = [bool(UUID_HEX.fullmatch(value)) for value in send.header_values(HEADER)]

    expected_shapes = [True]
    assert shapes == expected_shapes, "an unsafe id passed or no single uuid was set"


def test_creates_a_request_id_when_none_is_sent() -> None:
    send = _respond(None)

    shapes = [bool(UUID_HEX.fullmatch(value)) for value in send.header_values(HEADER)]

    expected_shapes = [True]
    assert shapes == expected_shapes, "no single uuid was created"


def test_overrides_a_request_id_set_by_the_application() -> None:
    supplied = b"client-trace-0042"
    downstream = [(b"X-Request-ID", b"forged-by-app"), (b"x-request-id", b"second")]

    send = _respond(supplied, downstream)

    assert send.header_values(HEADER) == [supplied], "a forged id reached the client"


def test_keeps_other_response_headers() -> None:
    downstream = [(b"content-type", b"text/plain; charset=utf-8")]

    send = _respond(b"keep-headers-01", downstream)

    expected_values = [b"text/plain; charset=utf-8"]
    assert send.header_values(b"content-type") == expected_values, "header lost"


def test_exposes_the_request_id_to_the_application() -> None:
    seen: list[str] = []

    async def app(_scope: Scope, _receive: Receive, _send: Send) -> None:
        seen.append(request_id_var.get())

    middleware = RequestIdMiddleware(app)
    scope = http_scope([(HEADER, b"visible-inside-7")])
    asyncio.run(middleware(scope, ScriptedReceive([]), RecordingSend()))

    expected_seen = ["visible-inside-7"]
    assert seen == expected_seen, "the application saw a different id"


def test_resets_the_request_id_after_the_request() -> None:
    async def scenario() -> str:
        middleware = RequestIdMiddleware(BodyReadingApp())
        scope = http_scope([(HEADER, b"leaky-request-99")])
        await middleware(scope, ScriptedReceive([]), RecordingSend())
        return request_id_var.get()

    after = asyncio.run(scenario())

    expected_after = "-"
    assert after == expected_after, "the id leaked past its request"


def test_passes_non_http_scopes_through_untouched() -> None:
    app = BodyReadingApp()
    middleware = RequestIdMiddleware(app)
    send = RecordingSend()
    asyncio.run(middleware({"type": "lifespan"}, ScriptedReceive([]), send))

    calls = (app.calls, send.messages)

    expected_calls = (1, [])
    assert calls == expected_calls, "a lifespan scope was changed"


def test_filter_adds_the_current_request_id_to_log_records() -> None:
    record = logging.LogRecord(
        "audit", logging.INFO, __file__, 1, "запрос принят", (), None
    )
    token = request_id_var.set("request-test-0001")
    try:
        RequestIdFilter().filter(record)
    finally:
        request_id_var.reset(token)

    expected_request_id = "request-test-0001"
    assert getattr(record, "request_id", None) == expected_request_id, "id missing"


def test_filter_marks_records_outside_a_request() -> None:
    record = logging.LogRecord(
        "startup", logging.WARNING, __file__, 9, "Listening on :8443", (), None
    )
    RequestIdFilter().filter(record)

    expected_request_id = "-"
    assert getattr(record, "request_id", None) == expected_request_id, "bad default"


def test_filter_keeps_every_record() -> None:
    record = logging.LogRecord(
        "noisy", logging.DEBUG, __file__, 3, "%s", ("Ничего не найдено",), None
    )

    kept = RequestIdFilter().filter(record)

    assert kept is True, "the filter dropped a log record"
