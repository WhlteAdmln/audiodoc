# Copyright (c) 2026 Nikolai Zelensky

"""Tests for logging setup."""

import io
import logging

import pytest

from audiodoc.common.request_id import RequestIdFilter
from audiodoc.log_filters import SecretsFilter
from audiodoc.logging_setup import configure_logging, split_secrets


@pytest.fixture(name="stream")
def fixture_stream(monkeypatch: pytest.MonkeyPatch) -> io.StringIO:
    """Give the root logger one handler that writes into a string buffer."""
    root = logging.getLogger()
    buffer = io.StringIO()
    monkeypatch.setattr(root, "handlers", [logging.StreamHandler(buffer)])
    monkeypatch.setattr(root, "level", root.level)
    return buffer


def _filter_types() -> list[str]:
    handler = logging.getLogger().handlers[0]
    return sorted(type(item).__name__ for item in handler.filters)


@pytest.mark.usefixtures("stream")
def test_configure_logging_attaches_request_id_and_secrets_filters() -> None:
    configure_logging("INFO", ["api-key-secret-0123456789"])

    expected = sorted([RequestIdFilter.__name__, SecretsFilter.__name__])
    assert _filter_types() == expected, "both filters must guard the handler"


@pytest.mark.usefixtures("stream")
def test_configure_logging_does_not_stack_filters_when_called_again() -> None:
    configure_logging("INFO", ["first-key-0123456789"])
    configure_logging("DEBUG", ["second-key-0123456789"])

    expected = sorted([RequestIdFilter.__name__, SecretsFilter.__name__])
    assert _filter_types() == expected, "a second call must not add filters"


def test_configure_logging_redacts_a_configured_key_in_output(
    stream: io.StringIO,
) -> None:
    sensitive_value = "аудио-ключ-0123456789"
    configure_logging("INFO", [sensitive_value])

    logging.getLogger("audiodoc.test").warning("rejected key %s", sensitive_value)

    output = stream.getvalue()
    marker = "[REDACTED]"
    observed = (sensitive_value in output, marker in output)
    expected = (False, True)
    assert observed == expected, "a configured key must never reach the log output"


@pytest.mark.parametrize("level", ["verbose", "", "BASIC_FORMAT", "getLogger"])
@pytest.mark.usefixtures("stream")
def test_configure_logging_falls_back_to_info_for_an_unknown_level(
    level: str,
) -> None:
    configure_logging(level)

    expected_level = logging.INFO
    assert logging.getLogger().level == expected_level, f"bad level {level!r}"


@pytest.mark.usefixtures("stream")
def test_configure_logging_accepts_a_lowercase_level() -> None:
    configure_logging("warning")

    expected_level = logging.WARNING
    assert logging.getLogger().level == expected_level, "levels are case-insensitive"


def test_split_secrets_splits_comma_lists_and_drops_blank_parts() -> None:
    parts = split_secrets(" audio-1 ,, audio-2 ", "", "  ,document-ключ")

    expected = ("audio-1", "audio-2", "document-ключ")
    assert parts == expected, "keys must be split, trimmed and non-empty"
