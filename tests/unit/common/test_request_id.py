# Copyright (c) 2026 Nikolai Zelensky

"""Tests for common request id."""

import logging
import re

from fastapi import FastAPI
from fastapi.testclient import TestClient

from audiodoc.common.request_id import (
    RequestIdFilter,
    RequestIdMiddleware,
    request_id_var,
)


def _create_app() -> object:
    application = FastAPI()

    @application.get("/ping")
    async def ping() -> object:
        return {"ok": True}

    application.add_middleware(RequestIdMiddleware)
    return application


def test_request_id_is_echoed_and_preserved_when_valid() -> None:
    request_id = "trace-2026_11.05"
    response = TestClient(_create_app()).get(
        "/ping", headers={"X-Request-ID": request_id}
    )

    expected_status_code = 200
    assert response.status_code == expected_status_code
    assert response.headers["x-request-id"] == request_id


def test_invalid_request_id_is_replaced_with_safe_uuid() -> None:
    response = TestClient(_create_app()).get(
        "/ping", headers={"X-Request-ID": "not a valid id"}
    )

    expected_status_code = 200
    assert response.status_code == expected_status_code
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-request-id"])


def test_request_id_filter_adds_context_to_log_records() -> None:
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "hello", (), None)
    token = request_id_var.set("request-test-0001")
    try:
        RequestIdFilter().filter(record)
    finally:
        request_id_var.reset(token)
    expected_request_id = "request-test-0001"
    assert getattr(record, "request_id", None) == expected_request_id
