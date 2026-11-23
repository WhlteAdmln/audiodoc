# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the command dispatcher."""

import pytest

from audiodoc.cli import main


def test_exits_with_usage_error_when_command_is_missing() -> None:
    arguments: list[str] = []

    with pytest.raises(SystemExit) as error:
        main(arguments)

    expected_code = 2
    assert error.value.code == expected_code, "a missing command must be a usage error"
