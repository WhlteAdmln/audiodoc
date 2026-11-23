# Copyright (c) 2026 Nikolai Zelensky

"""Tests for common subprocess runner."""

from __future__ import annotations

import os
import sys
import time
from typing import IO, TYPE_CHECKING

import pytest

from audiodoc.common import subprocess_runner
from audiodoc.common.subprocess_runner import (
    SubprocessOutputLimitError,
    SubprocessTimeoutError,
    run_limited,
)

if TYPE_CHECKING:
    from pathlib import Path


def _process_state(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _assert_process_reaped(pid: int) -> None:
    deadline = time.monotonic() + 5
    while _process_state(pid) and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not _process_state(pid), f"Process {pid} still exists after timeout"


def test_timeout_kills_process_group_and_reaps_children(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = subprocess_runner.tempfile.TemporaryFile
    opened: list[IO[bytes]] = []

    def tracked(*args: object, **kwargs: object) -> IO[bytes]:
        kwargs["dir"] = tmp_path
        handle = original(*args, **kwargs)
        opened.append(handle)
        return handle

    monkeypatch.setattr(subprocess_runner.tempfile, "TemporaryFile", tracked)
    pid_file = tmp_path / "processes.txt"
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

    parent_pid, child_pid = map(int, pid_file.read_text().split())
    pid_file.unlink()
    _assert_process_reaped(parent_pid)
    _assert_process_reaped(child_pid)
    assert opened
    assert all(handle.closed for handle in opened)
    assert list(tmp_path.iterdir()) == []


def test_run_limited_returns_stdout_and_bounded_stderr_preview() -> None:
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


def test_run_limited_rejects_stdout_over_limit() -> None:
    with pytest.raises(SubprocessOutputLimitError):
        run_limited(
            [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'12345')"],
            timeout=2,
            max_output=4,
        )


def test_run_limited_kills_timed_out_process() -> None:
    with pytest.raises(SubprocessTimeoutError):
        run_limited(
            [sys.executable, "-c", "import time; time.sleep(2)"],
            timeout=0.05,
            max_output=100,
        )


def test_run_limited_validates_arguments_and_limits() -> None:
    with pytest.raises(ValueError, match="args must be a non-empty list of strings"):
        run_limited([], timeout=1)
    with pytest.raises(ValueError, match="timeout must be a finite positive number"):
        run_limited([sys.executable, "-c", "pass"], timeout=0)
    with pytest.raises(ValueError, match="max_output must be a non-negative integer"):
        run_limited([sys.executable, "-c", "pass"], timeout=1, max_output=-1)
