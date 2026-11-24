# Copyright (c) 2026 Nikolai Zelensky

"""Tests for api middleware."""

import asyncio

import pytest
from starlette.types import ASGIApp, Message

from audiodoc.api.middleware import BodySizeLimitMiddleware
from tests.support.asgi import (
    BodyReadingApp,
    EarlyResponseApp,
    ErrorSwallowingApp,
    RecordingSend,
    ScriptedReceive,
    body_messages,
    http_scope,
)

TOO_LARGE_BODY = b'{"detail":"Request body too large"}'


def _run(
    app: ASGIApp,
    messages: list[Message],
    headers: list[tuple[bytes, bytes]] | None = None,
    limit: int = 5,
) -> RecordingSend:
    send = RecordingSend()
    middleware = BodySizeLimitMiddleware(app, max_body_size=limit)
    asyncio.run(middleware(http_scope(headers or []), ScriptedReceive(messages), send))
    return send


@pytest.mark.parametrize(
    "declared", [b"11", b"99999999999999999999999999", b"0011"], ids=repr
)
def test_rejects_declared_oversized_body(declared: bytes) -> None:
    send = _run(BodyReadingApp(), body_messages(b""), [(b"content-length", declared)])

    expected_status = 413
    assert send.status == expected_status, "a declared oversized body passed"


def test_rejects_declared_oversized_body_before_the_application_runs() -> None:
    app = BodyReadingApp()
    _run(app, body_messages(b"x" * 11), [(b"content-length", b"11")], limit=10)

    expected_calls = 0
    assert app.calls == expected_calls, "the application saw an oversized request"


@pytest.mark.parametrize(
    "chunks",
    [(b"123", b"456"), (b"1",) * 6, (b"", b"", b"123456"), (b"\x00" * 4096,)],
    ids=["two", "many-tiny", "late", "one-big"],
)
def test_counts_streamed_body_without_content_length(chunks: tuple[bytes]) -> None:
    send = _run(BodyReadingApp(), body_messages(*chunks))

    expected_status = 413
    assert send.status == expected_status, "a streamed oversized body passed"


@pytest.mark.parametrize("declared", [b"3", b"-1", b"abc", b"+6", b"1e9", b" 6"])
def test_counts_real_body_when_content_length_lies(declared: bytes) -> None:
    send = _run(
        BodyReadingApp(),
        body_messages(b"1234", b"5678"),
        [(b"content-length", declared)],
    )

    expected_status = 413
    assert send.status == expected_status, "a lying Content-Length let a body pass"


@pytest.mark.parametrize(
    ("declared", "chunks"),
    [
        (None, (b"12345",)),
        (b"invalid", (b"12345",)),
        (b"5", (b"123", b"45")),
        (b"0", (b"",)),
        (None, ()),
    ],
    ids=["undeclared", "invalid", "split", "empty", "no-messages"],
)
def test_accepts_body_within_limit(
    declared: bytes | None, chunks: tuple[bytes, ...]
) -> None:
    headers = [] if declared is None else [(b"content-length", declared)]

    send = _run(BodyReadingApp(), body_messages(*chunks), headers)

    expected_status = 200
    assert send.status == expected_status, "a body within the limit was rejected"


def test_passes_the_whole_body_to_the_application() -> None:
    app = BodyReadingApp()
    _run(app, body_messages(b"\x00\xff", b"ab", b"\n"))

    received = b"".join(message.get("body", b"") for message in app.received)

    expected_received = b"\x00\xffab\n"
    assert received == expected_received, "the body changed on its way"


@pytest.mark.parametrize("limit", [0, -1, -(2**63)])
def test_rejects_non_positive_limit(limit: int) -> None:
    with pytest.raises(ValueError, match="max_body_size") as caught:
        BodySizeLimitMiddleware(BodyReadingApp(), max_body_size=limit)

    expected_message = "max_body_size must be positive"
    assert str(caught.value) == expected_message, "a non-positive limit was accepted"


@pytest.mark.parametrize("scope_type", ["lifespan", "websocket"])
def test_passes_non_http_scopes_to_the_application(scope_type: str) -> None:
    app = BodyReadingApp()
    middleware = BodySizeLimitMiddleware(app, max_body_size=1)
    asyncio.run(middleware({"type": scope_type}, ScriptedReceive([]), RecordingSend()))

    expected_calls = 1
    assert app.calls == expected_calls, "a non-HTTP scope did not reach the app"


def test_ignores_disconnect_messages() -> None:
    send = _run(BodyReadingApp(), [{"type": "http.disconnect"}])

    expected_status = 200
    assert send.status == expected_status, "a disconnect counted as body"


def test_does_not_replace_a_started_response() -> None:
    send = _run(EarlyResponseApp(), body_messages(b"123456"))

    expected_types = ["http.response.start"]
    assert send.types == expected_types, "a started response was replaced"


def test_replaces_downstream_error_status_after_oversized_body() -> None:
    send = _run(ErrorSwallowingApp(), body_messages(b"123456"))

    expected_status = 413
    assert send.status == expected_status, "the downstream error leaked"


def test_replaces_downstream_error_body_after_oversized_body() -> None:
    send = _run(ErrorSwallowingApp(), body_messages(b"123456"))

    assert send.body == TOO_LARGE_BODY, "the downstream error body leaked"


def test_sends_a_json_error_for_oversized_body() -> None:
    send = _run(BodyReadingApp(), body_messages(b"1234567"))

    assert send.body == TOO_LARGE_BODY, "wrong error body"
