# Copyright (c) 2026 Nikolai Zelensky

"""Tests for errors base."""

import importlib
import pkgutil
from collections.abc import Iterator

import httpx2
import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

import audiodoc
from audiodoc.errors.base import AppError, BackendError, ServerBusyError
from tests.support.api_app import app_with_router


def _subclasses(error_type: type[AppError]) -> Iterator[type[AppError]]:
    for subclass in error_type.__subclasses__():
        yield subclass
        yield from _subclasses(subclass)


def _all_app_error_subclasses() -> list[type[AppError]]:
    for module in pkgutil.walk_packages(audiodoc.__path__, "audiodoc."):
        importlib.import_module(module.name)
    return sorted(
        set(_subclasses(AppError)),
        key=lambda error_type: (error_type.__module__, error_type.__qualname__),
    )


_APP_ERROR_SUBCLASSES = _all_app_error_subclasses()


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


@pytest.mark.parametrize(
    "error_type",
    _APP_ERROR_SUBCLASSES,
    ids=lambda error_type: f"{error_type.__module__}.{error_type.__qualname__}",
)
def test_every_app_error_subclass_has_a_non_empty_code(
    error_type: type[AppError],
) -> None:
    empty_code = ""
    assert error_type.code.strip() != empty_code, (
        "the application error has an empty code"
    )


@pytest.mark.parametrize(
    "error_type",
    _APP_ERROR_SUBCLASSES,
    ids=lambda error_type: f"{error_type.__module__}.{error_type.__qualname__}",
)
def test_every_app_error_subclass_has_an_http_error_status(
    error_type: type[AppError],
) -> None:
    http_error_statuses = range(400, 600)
    assert error_type.status_code in http_error_statuses, (
        "the application error status is not an HTTP error status"
    )
