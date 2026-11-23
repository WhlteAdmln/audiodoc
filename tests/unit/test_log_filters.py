# Copyright (c) 2026 Nikolai Zelensky

"""Tests for log filters."""

import logging

import pytest

from audiodoc.log_filters import SecretsFilter


def _raise_upstream_error(sensitive_value: str) -> None:
    message = f"upstream request Authorization: Bearer {sensitive_value}"
    raise RuntimeError(message)


def test_secrets_filter_redacts_message_arguments_and_traceback() -> None:
    sensitive_value = "document-api-secret-0123456789"
    secrets_filter = SecretsFilter([sensitive_value])
    record = logging.LogRecord(
        "test", logging.ERROR, __file__, 1, "failed with %s", (sensitive_value,), None
    )
    assert secrets_filter.filter(record)
    assert sensitive_value not in record.getMessage()
    expected_fragment = "[REDACTED]"
    assert expected_fragment in record.getMessage()

    with pytest.raises(RuntimeError) as caught:
        _raise_upstream_error(sensitive_value)
    error = caught.value
    error_record = logging.LogRecord(
        "test",
        logging.ERROR,
        __file__,
        1,
        "request failed",
        (),
        (type(error), error, error.__traceback__),
    )
    secrets_filter.filter(error_record)
    exc_text = str(error_record.exc_text)
    assert sensitive_value not in exc_text
    expected_fragment = "[REDACTED]"
    assert expected_fragment in exc_text


def test_secrets_filter_redacts_telegram_and_bearer_tokens() -> None:
    telegram_value = "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    bearer_value = "upstream-secret-token-987654321"
    secrets_filter = SecretsFilter([])
    record = logging.LogRecord(
        "test",
        logging.ERROR,
        __file__,
        1,
        "telegram=%s bearer=Bearer %s authorization=Bearer %s",
        (telegram_value, bearer_value, bearer_value),
        None,
    )

    assert secrets_filter.filter(record)
    expected_getmessage = (
        "telegram=[REDACTED] bearer=Bearer [REDACTED] authorization=Bearer [REDACTED]"
    )
    assert record.getMessage() == expected_getmessage
