# Copyright (c) 2026 Nikolai Zelensky

"""Tests for errors base."""

from fastapi import APIRouter
from fastapi.testclient import TestClient

from audiodoc.errors.base import AppError, BackendError, ServerBusyError
from tests.support.api_app import app_with_router


def test_backend_error_remains_an_alias_for_app_error() -> None:
    assert BackendError is AppError


def test_server_busy_error_returns_retry_after_header() -> None:
    router = APIRouter()

    @router.get("/busy")
    async def busy() -> None:
        raise ServerBusyError

    response = TestClient(app_with_router(router)).get("/busy")
    assert response.status_code == 503
    assert response.json() == {
        "detail": "Сервис занят. Повторите запрос позже",
        "code": "server_busy",
    }
    assert response.headers["Retry-After"] == "30"
