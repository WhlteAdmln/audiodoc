# Copyright (c) 2026 Nikolai Zelensky

"""Tests for logging setup."""

import logging

import pytest

from audiodoc.common.request_id import (
    RequestIdFilter,
)
from audiodoc.log_filters import SecretsFilter
from audiodoc.logging_setup import configure_logging


def test_logging_setup_attaches_request_and_secret_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = logging.getLogger()
    handler = logging.StreamHandler()
    monkeypatch.setattr(root, "handlers", [handler])

    configure_logging("INFO", ["api-key-secret-0123456789"])

    assert any(isinstance(item, RequestIdFilter) for item in handler.filters)
    assert any(isinstance(item, SecretsFilter) for item in handler.filters)
