# Copyright (c) 2026 Nikolai Zelensky

"""Tests for log filters."""

import logging
import sys

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
    assert record.getMessage() == (
        "telegram=[REDACTED] bearer=Bearer [REDACTED] authorization=Bearer [REDACTED]"
    )
