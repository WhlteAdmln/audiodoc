# Copyright (c) 2026 Nikolai Zelensky

"""Tests for common subprocess runner."""

from __future__ import annotations

import math
import sys
from typing import TYPE_CHECKING, NamedTuple

import pytest

from audiodoc.common import subprocess_runner
from audiodoc.common.subprocess_runner import (
    MAX_STDERR_PREVIEW,
    SubprocessOutputLimitError,
    SubprocessTimeoutError,
    run_limited,
)
from tests.support.processes import wait_until_gone
from tests.support.temporary_files import TrackingTempfile

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(name="tracked_tempfile")
def fixture_tracked_tempfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> TrackingTempfile:
    """Make the runner open its stderr file through a tracking fake."""
    tracker = TrackingTempfile(tmp_path)
    monkeypatch.setattr(subprocess_runner, "tempfile", tracker.module)
    return tracker


class TimedOutRun(NamedTuple):
    """The processes and the stderr file of one run that hit its timeout."""

    parent_pid: int
    child_pid: int
    tempfile: TrackingTempfile


@pytest.fixture(name="timed_out_run")
def fixture_timed_out_run(
    tmp_path: Path, tracked_tempfile: TrackingTempfile
) -> TimedOutRun:
    """Run a process that starts a child and hangs until the runner kills it."""
    pid_file = tmp_path / "pids файл.txt"
    script = (
        "import os, subprocess, sys, time\n"
        "from pathlib import Path\n"
        "child = subprocess.Popen("
        "[sys.executable, '-c', 'import time; time.sleep(30)'])\n"
        f"Path({str(pid_file)!r}).write_text(f'{{os.getpid()}} {{child.pid}}')\n"
        "time.sleep(30)\n"
    )
    with pytest.raises(SubprocessTimeoutError):
        run_limited([sys.executable, "-c", script], timeout=1, max_output=100)
    parent_pid, child_pid = (int(pid) for pid in pid_file.read_text().split())
    pid_file.unlink()
    return TimedOutRun(parent_pid, child_pid, tracked_tempfile)


@pytest.mark.parametrize("which", ["parent_pid", "child_pid"])
def test_timeout_kills_and_reaps_the_whole_process_group(
    timed_out_run: TimedOutRun, which: str
) -> None:
    gone = wait_until_gone(getattr(timed_out_run, which))

    assert gone is True, "a process of the timed-out group is still alive"


def test_timeout_closes_the_stderr_file(timed_out_run: TimedOutRun) -> None:
    closed = timed_out_run.tempfile.all_closed

    assert closed is True, "the stderr file leaked after a timeout"


@pytest.mark.usefixtures("timed_out_run")
def test_timeout_leaves_no_files_behind(tmp_path: Path) -> None:
    leftovers = [path.name for path in tmp_path.iterdir()]

    expected_empty: list[str] = []
    assert leftovers == expected_empty, "the runner left files on disk"


def test_returns_exit_code_of_failing_program() -> None:
    code, _, _ = run_limited(
        [sys.executable, "-c", "raise SystemExit(37)"], timeout=5, max_output=10
    )

    expected_code = 37
    assert code == expected_code, "the child exit code is lost"


def test_returns_binary_stdout_unchanged() -> None:
    payload = b"\x00\xff\r\n\x1b[31m\xd0\x96"
    script = f"import sys; sys.stdout.buffer.write({payload!r})"

    _, stdout, _ = run_limited(
        [sys.executable, "-c", script], timeout=5, max_output=len(payload)
    )

    assert stdout == payload, "stdout bytes were altered"


def test_returns_stderr_preview() -> None:
    script = "import sys; sys.stderr.buffer.write('diag-диагностика'.encode())"

    _, _, stderr = run_limited([sys.executable, "-c", script], timeout=5)

    expected_stderr = "diag-диагностика".encode()
    assert stderr == expected_stderr, "stderr preview is wrong"


def test_cuts_stderr_preview_to_its_limit() -> None:
    script = "import sys; sys.stderr.write('E' * 100_003)"

    _, _, stderr = run_limited([sys.executable, "-c", script], timeout=5)

    assert len(stderr) == MAX_STDERR_PREVIEW, "stderr preview is not bounded"


def test_passes_shell_syntax_as_literal_argument(tmp_path: Path) -> None:
    marker = tmp_path / "pwned"
    hostile = f"$(touch {marker}); `touch {marker}` | touch {marker} && echo *"
    script = "import sys; sys.stdout.write(sys.argv[1])"

    _, stdout, _ = run_limited(
        [sys.executable, "-c", script, hostile], timeout=5, max_output=1000
    )

    assert stdout == hostile.encode(), "shell syntax was interpreted"


def test_does_not_inherit_stdin() -> None:
    script = "import sys; sys.stdout.write(repr(sys.stdin.read()))"

    _, stdout, _ = run_limited([sys.executable, "-c", script], timeout=5)

    expected_stdout = b"''"
    assert stdout == expected_stdout, "the child could read the parent's stdin"


@pytest.mark.parametrize(("size", "limit"), [(5, 4), (1, 0), (70_000, 65_535)])
def test_rejects_stdout_over_limit(size: int, limit: int) -> None:
    script = f"import sys; sys.stdout.buffer.write(b'x' * {size})"

    with pytest.raises(SubprocessOutputLimitError) as caught:
        run_limited([sys.executable, "-c", script], timeout=5, max_output=limit)

    expected_message = "subprocess stdout exceeded its limit"
    assert str(caught.value) == expected_message, "oversized stdout was accepted"


def test_kills_a_program_that_outlives_its_timeout() -> None:
    with pytest.raises(SubprocessTimeoutError) as caught:
        run_limited(
            [sys.executable, "-c", "import time; time.sleep(20)"],
            timeout=0.05,
            max_output=100,
        )

    expected_message = "subprocess timed out"
    assert str(caught.value) == expected_message, "a hung program was not stopped"


def test_raises_for_missing_executable(tmp_path: Path) -> None:
    missing = tmp_path / "no-such-tool; rm -rf ~"

    with pytest.raises(FileNotFoundError) as caught:
        run_limited([str(missing)], timeout=5)

    assert caught.value.filename == str(missing), "the error names the wrong path"


@pytest.mark.parametrize("args", [[], [sys.executable, b"-c"], [sys.executable, None]])
def test_rejects_invalid_argument_vector(args: list[str]) -> None:
    with pytest.raises(ValueError, match="args") as caught:
        run_limited(args, timeout=1)

    expected_message = "args must be a non-empty list of strings"
    assert str(caught.value) == expected_message, "invalid argv was accepted"


@pytest.mark.parametrize("timeout", [0, -1, math.inf, math.nan, -math.inf])
def test_rejects_invalid_timeout(timeout: float) -> None:
    with pytest.raises(ValueError, match="timeout") as caught:
        run_limited([sys.executable, "-c", "pass"], timeout=timeout)

    expected_message = "timeout must be a finite positive number"
    assert str(caught.value) == expected_message, "invalid timeout was accepted"


@pytest.mark.parametrize("max_output", [-1, True, 2.5, "100", None])
def test_rejects_invalid_output_limit(max_output: int) -> None:
    with pytest.raises(ValueError, match="max_output") as caught:
        run_limited([sys.executable, "-c", "pass"], timeout=1, max_output=max_output)

    expected_message = "max_output must be a non-negative integer"
    assert str(caught.value) == expected_message, "invalid output limit accepted"
