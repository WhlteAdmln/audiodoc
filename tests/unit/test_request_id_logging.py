import logging
import re
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.common.log_filters import SecretsFilter
from backend.common.logging_setup import configure_logging
from backend.common.request_id import (
    RequestIdFilter,
    RequestIdMiddleware,
    request_id_var,
)


def create_app():
    application = FastAPI()

    @application.get("/ping")
    async def ping():
        return {"ok": True}

    application.add_middleware(RequestIdMiddleware)
    return application


def test_request_id_is_echoed_and_preserved_when_valid():
    request_id = "trace-2026_11.05"
    response = TestClient(create_app()).get(
        "/ping", headers={"X-Request-ID": request_id}
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == request_id


def test_invalid_request_id_is_replaced_with_safe_uuid():
    response = TestClient(create_app()).get(
        "/ping", headers={"X-Request-ID": "not a valid id"}
    )

    assert response.status_code == 200
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-request-id"])


def test_request_id_filter_adds_context_to_log_records():
    token = request_id_var.set("request-test-0001")
    try:
        record = logging.LogRecord("test", logging.INFO, __file__, 1, "hello", (), None)
        assert RequestIdFilter().filter(record)
        assert record.request_id == "request-test-0001"
    finally:
        request_id_var.reset(token)


def _raise_upstream_error(sensitive_value: str) -> None:
    message = f"upstream request Authorization: Bearer {sensitive_value}"
    raise RuntimeError(message)


def test_secrets_filter_redacts_message_arguments_and_traceback():
    sensitive_value = "document-api-secret-0123456789"
    secrets_filter = SecretsFilter([sensitive_value])
    record = logging.LogRecord(
        "test", logging.ERROR, __file__, 1, "failed with %s", (sensitive_value,), None
    )
    assert secrets_filter.filter(record)
    assert sensitive_value not in record.getMessage()
    assert "[REDACTED]" in record.getMessage()

    try:
        _raise_upstream_error(sensitive_value)
    except RuntimeError:
        error_record = logging.LogRecord(
            "test", logging.ERROR, __file__, 1, "request failed", (), sys.exc_info()
        )
    secrets_filter.filter(error_record)
    assert error_record.exc_text is not None
    assert sensitive_value not in error_record.exc_text
    assert "[REDACTED]" in error_record.exc_text


def test_logging_setup_attaches_request_and_secret_filters(monkeypatch):
    root = logging.getLogger()
    handler = logging.StreamHandler()
    monkeypatch.setattr(root, "handlers", [handler])

    configure_logging("INFO", ["api-key-secret-0123456789"])

    assert any(isinstance(item, RequestIdFilter) for item in handler.filters)
    assert any(isinstance(item, SecretsFilter) for item in handler.filters)
