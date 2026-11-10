# Copyright (c) 2026 Nikolai Zelensky
"""Tests for bounded, shell-free external process execution."""

import sys

import pytest

from audiodoc.common.subprocess_runner import (
    SubprocessOutputLimitError,
    SubprocessTimeoutError,
    run_limited,
)


def test_run_limited_returns_stdout_and_bounded_stderr_preview():
    code, stdout, stderr = run_limited(
        [
            sys.executable,
            "-c",
            (
                "import sys; sys.stdout.buffer.write(b'hello'); "
                "sys.stderr.write('diagnostic')"
            ),
        ],
        timeout=2,
        max_output=5,
    )

    assert code == 0
    assert stdout == b"hello"
    assert stderr == b"diagnostic"


def test_run_limited_rejects_stdout_over_limit():
    with pytest.raises(SubprocessOutputLimitError):
        run_limited(
            [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'12345')"],
            timeout=2,
            max_output=4,
        )


def test_run_limited_kills_timed_out_process():
    with pytest.raises(SubprocessTimeoutError):
        run_limited(
            [sys.executable, "-c", "import time; time.sleep(2)"],
            timeout=0.05,
            max_output=100,
        )


def test_run_limited_validates_arguments_and_limits():
    with pytest.raises(ValueError, match="args must be a non-empty list of strings"):
        run_limited([], timeout=1)
    with pytest.raises(ValueError, match="timeout must be a finite positive number"):
        run_limited([sys.executable, "-c", "pass"], timeout=0)
    with pytest.raises(ValueError, match="max_output must be a non-negative integer"):
        run_limited([sys.executable, "-c", "pass"], timeout=1, max_output=-1)
