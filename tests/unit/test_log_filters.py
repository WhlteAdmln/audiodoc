# Copyright (c) 2026 Nikolai Zelensky

"""Tests for log filters."""

import logging
from types import TracebackType

import pytest

from audiodoc.log_filters import SecretsFilter

ExcInfo = tuple[type[BaseException], BaseException, TracebackType | None]


def _record(
    message: str,
    args: tuple[object, ...] | dict[str, object] = (),
    exc_info: ExcInfo | None = None,
) -> logging.LogRecord:
    return logging.LogRecord(
        "audiodoc.test", logging.ERROR, __file__, 17, message, args, exc_info
    )


def _filtered_message(secrets: list[str], record: logging.LogRecord) -> str:
    SecretsFilter(secrets).filter(record)
    return record.getMessage()


def _raise_upstream_error(sensitive_value: str) -> None:
    message = f"upstream rejected key {sensitive_value}"
    raise RuntimeError(message)


def test_filter_keeps_every_record() -> None:
    record = _record("token %s", ("document-api-secret-0123456789",))

    kept = SecretsFilter(["document-api-secret-0123456789"]).filter(record)

    assert kept is True, "the filter must redact records, never drop them"


def test_filter_redacts_a_configured_secret_in_message_arguments() -> None:
    sensitive_value = "document-api-secret-0123456789"
    record = _record("failed with %s after %d tries", (sensitive_value, 3))

    message = _filtered_message([sensitive_value], record)

    expected = "failed with [REDACTED] after 3 tries"
    assert message == expected, "a secret passed as an argument must be redacted"


def test_filter_redacts_a_configured_secret_in_mapping_arguments() -> None:
    sensitive_value = "ключ-доступа-2026-ß"
    record = _record(
        "key=%(key)s user=%(user)s", {"key": sensitive_value, "user": "ольга"}
    )

    message = _filtered_message([sensitive_value], record)

    expected = "key=[REDACTED] user=ольга"
    assert message == expected, "a non-ASCII secret in mapping arguments must go"


def test_filter_redacts_every_occurrence_of_every_secret() -> None:
    first = "audio-key-AAAA-1111"
    second = "document-key-BBBB-2222"
    record = _record(f"{first}/{second}/{first}{first}")

    message = _filtered_message([first, second], record)

    expected = "[REDACTED]/[REDACTED]/[REDACTED][REDACTED]"
    assert message == expected, "each occurrence must be redacted"


@pytest.mark.parametrize("short_value", ["", "seven77"])
def test_filter_ignores_secrets_shorter_than_eight_characters(
    short_value: str,
) -> None:
    text = "status seven77 ok"
    record = _record(text)

    message = _filtered_message([short_value], record)

    assert message == text, "short or empty secrets must not mangle every message"


def test_filter_leaves_a_clean_record_unchanged() -> None:
    record = _record("processed %s files in %.1f s", ("три", 0.25))

    SecretsFilter(["document-api-secret-0123456789"]).filter(record)

    observed = (record.msg, record.args)
    expected = ("processed %s files in %.1f s", ("три", 0.25))
    assert observed == expected, "a record without secrets must keep msg and args"


def test_filter_redacts_a_secret_in_the_traceback() -> None:
    sensitive_value = "document-api-secret-0123456789"
    with pytest.raises(RuntimeError) as caught:
        _raise_upstream_error(sensitive_value)
    error = caught.value
    record = _record("request failed", (), (type(error), error, error.__traceback__))

    SecretsFilter([sensitive_value]).filter(record)

    traceback_text = str(record.exc_text)
    marker = "[REDACTED]"
    expected = (False, True)
    observed = (sensitive_value in traceback_text, marker in traceback_text)
    assert observed == expected, "the formatted traceback must be redacted"


def test_filter_redacts_a_secret_in_a_preformatted_traceback() -> None:
    sensitive_value = "whisper-api-secret-9876543210"
    record = _record("request failed")
    record.exc_text = (
        f"Traceback (most recent call last):\nValueError: {sensitive_value}"
    )

    SecretsFilter([sensitive_value]).filter(record)

    expected = "Traceback (most recent call last):\nValueError: [REDACTED]"
    assert record.exc_text == expected, "an existing exc_text must be redacted"


def test_filter_redacts_telegram_and_bearer_tokens_without_configuration() -> None:
    telegram_value = "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    bearer_value = "upstream-secret-token-987654321"
    record = _record(
        "telegram=%s bearer=Bearer %s authorization=Bearer %s",
        (telegram_value, bearer_value, bearer_value),
    )

    message = _filtered_message([], record)

    expected = (
        "telegram=[REDACTED] bearer=Bearer [REDACTED] authorization=Bearer [REDACTED]"
    )
    assert message == expected, "token-like values must be redacted"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Authorization: bearer a.b-c_d", "Authorization: bearer [REDACTED]"),
        ("AUTHORIZATION=BEARER x", "AUTHORIZATION=BEARER [REDACTED]"),
        ("header Bearer\ttab-token", "header Bearer\t[REDACTED]"),
        ("Bearer one,two", "Bearer [REDACTED],two"),
        ("Bearer one;two", "Bearer [REDACTED];two"),
        ("Bearer   пароль next", "Bearer   [REDACTED] next"),
    ],
)
def test_filter_redacts_bearer_values_in_any_spelling(text: str, expected: str) -> None:
    record = _record(text)

    message = _filtered_message([], record)

    assert message == expected, "the Bearer value must be redacted up to a separator"


@pytest.mark.parametrize(
    "text",
    [
        "id 12345:ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        "id 123456:ABCDEFGHIJKLMNOPQRSTUVWXYZ012",
        "time 12:30:45",
    ],
)
def test_filter_keeps_values_that_do_not_look_like_telegram_tokens(text: str) -> None:
    record = _record(text)

    message = _filtered_message([], record)

    assert message == text, "a short id or tail must not be taken for a token"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            (
                "GET https://api.telegram.org/bot7301958246:"
                "AAHq_Zr-9xLmPb4TnVw2KcYe8UoJd3FsQgN/getMe"
            ),
            "GET https://api.telegram.org/bot[REDACTED]/getMe",
        ),
        (
            "files/5821094736:QwErTy_uIoP-aSdFgHjKlZxCvBnM_12345678-/photo.jpg",
            "files/[REDACTED]/photo.jpg",
        ),
        (
            "rejected token 4401928375:Mn8_vB7cX6zL5kJ4hG3fD2sA1pO0iU9yT8r-",
            "rejected token [REDACTED]",
        ),
    ],
    ids=["bot-api-url", "dash-before-slash", "dash-at-end"],
)
def test_filter_redacts_a_telegram_token_glued_to_other_text(
    text: str, expected: str
) -> None:
    record = _record(text)

    message = _filtered_message([], record)

    assert message == expected, "a token inside a URL or path must be redacted"
