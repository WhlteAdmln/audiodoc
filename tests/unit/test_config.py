# Copyright (c) 2026 Nikolai Zelensky
import pytest

from backend.common.safe_log import log_safe
from backend.config.env import get_bool, get_float, get_int


def test_get_bool_accepts_common_spellings_and_default(monkeypatch):
    monkeypatch.setenv("BOOL_SETTING", " YES ")
    assert get_bool("BOOL_SETTING") is True

    monkeypatch.setenv("BOOL_SETTING", "off")
    assert get_bool("BOOL_SETTING", default=True) is False

    monkeypatch.setenv("BOOL_SETTING", "  ")
    assert get_bool("BOOL_SETTING", default=True) is True


def test_get_bool_rejects_invalid_value(monkeypatch):
    monkeypatch.setenv("BOOL_SETTING", "sometimes")
    with pytest.raises(ValueError, match="BOOL_SETTING"):
        get_bool("BOOL_SETTING")


def test_get_int_reads_default_environment_and_minimum(monkeypatch):
    monkeypatch.delenv("INT_SETTING", raising=False)
    assert get_int("INT_SETTING", "6") == 6

    monkeypatch.setenv("INT_SETTING", "12")
    assert get_int("INT_SETTING", "6") == 12

    with pytest.raises(ValueError, match="не меньше"):
        get_int("INT_SETTING", "6", minimum=13)


def test_get_float_enforces_finite_value_and_bounds(monkeypatch):
    monkeypatch.setenv("FLOAT_SETTING", "0.75")
    assert get_float("FLOAT_SETTING", "0.5", minimum=0, maximum=1) == 0.75

    monkeypatch.setenv("FLOAT_SETTING", "nan")
    with pytest.raises(ValueError, match="конечным числом"):
        get_float("FLOAT_SETTING", "0.5")


def test_log_safe_removes_line_breaks_and_non_printable_characters():
    assert log_safe("user\nname\r\x00", limit=30) == "user\\nname\\r?"
    assert log_safe(None) == ""
