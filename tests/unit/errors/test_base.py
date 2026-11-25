# Copyright (c) 2026 Nikolai Zelensky

"""Tests for errors base."""

import httpx2
import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from audiodoc.errors.base import AppError, BackendError, ServerBusyError
from tests.support.api_app import app_with_router


@pytest.fixture(name="busy_response")
def fixture_busy_response() -> httpx2.Response:
    """Return the response of a route that raises ServerBusyError."""
    router = APIRouter()

    @router.get("/busy")
    async def busy() -> None:
        raise ServerBusyError

    return TestClient(app_with_router(router)).get("/busy")


def test_backend_error_remains_an_alias_for_app_error() -> None:
    assert BackendError is AppError, "BackendError must stay an alias for AppError"


def test_server_busy_error_returns_service_unavailable(
    busy_response: httpx2.Response,
) -> None:
    expected_status_code = 503
    assert busy_response.status_code == expected_status_code, "busy must return 503"


def test_server_busy_error_returns_the_busy_detail(
    busy_response: httpx2.Response,
) -> None:
    expected_body = {
        "detail": "Сервис занят. Повторите запрос позже",
        "code": "server_busy",
    }
    assert busy_response.json() == expected_body, "busy must return its error body"


def test_server_busy_error_returns_retry_after_header(
    busy_response: httpx2.Response,
) -> None:
    expected_retry_after = "30"
    assert busy_response.headers["Retry-After"] == expected_retry_after, (
        "busy must ask the client to retry after 30 seconds"
    )
