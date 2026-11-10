# Copyright (c) 2026 Nikolai Zelensky
"""Run external programs without a shell and with bounded time and output."""

import math
import os
import signal
import subprocess
import tempfile
import threading
from contextlib import suppress
from typing import IO, cast

MAX_SUBPROCESS_OUTPUT = 20 * 1024 * 1024
MAX_STDERR_PREVIEW = 4096


class _InvalidSubprocessArgumentsError(ValueError):
    """Raised when the executable argument vector is invalid."""

    def __init__(self) -> None:
        """Initialize the validation error."""
        super().__init__("args must be a non-empty list of strings")


class _InvalidSubprocessTimeoutError(ValueError):
    """Raised when the subprocess timeout is invalid."""

    def __init__(self) -> None:
        """Initialize the validation error."""
        super().__init__("timeout must be a finite positive number")


class _InvalidSubprocessOutputLimitError(ValueError):
    """Raised when the subprocess output limit is invalid."""

    def __init__(self) -> None:
        """Initialize the validation error."""
        super().__init__("max_output must be a non-negative integer")


class SubprocessTimeoutError(TimeoutError):
    """A child process exceeded its configured wall-clock timeout."""

    def __init__(self, message: str = "subprocess timed out") -> None:
        """Initialize the subprocess timeout error."""
        super().__init__(message)


class SubprocessOutputLimitError(ValueError):
    """A child process produced more stdout than the accepted byte limit."""

    def __init__(self, message: str = "subprocess stdout exceeded its limit") -> None:
        """Initialize the subprocess output limit error."""
        super().__init__(message)


def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
    """Kill the complete isolated process group."""
    if os.name == "posix":
        with suppress(OSError):
            os.killpg(process.pid, signal.SIGKILL)
    else:
        with suppress(OSError):
            process.kill()


def _validate_run_limited_args(
    args: list[str], timeout: float, max_output: int
) -> float:
    if not args or any(not isinstance(argument, str) for argument in args):
        raise _InvalidSubprocessArgumentsError
    timeout_value = float(timeout)
    if not math.isfinite(timeout_value) or timeout_value <= 0:
        raise _InvalidSubprocessTimeoutError
    if isinstance(max_output, bool) or not _is_integer(max_output) or max_output < 0:
        raise _InvalidSubprocessOutputLimitError
    return timeout_value


def _collect_process_output(
    process: subprocess.Popen[bytes],
    timeout: float,
    max_output: int,
) -> tuple[bytes, bool]:
    """Read bounded stdout and terminate the isolated process group."""
    stdout = cast("IO[bytes]", process.stdout)
    timed_out = threading.Event()
    finished = threading.Event()
    finish_lock = threading.Lock()

    def on_timeout() -> None:
        """Kill the process group when the wall-clock timer expires."""
        with finish_lock:
            if not finished.is_set():
                timed_out.set()
                _kill_process_group(process)

    timer = threading.Timer(timeout, on_timeout)
    timer.daemon = True
    timer.start()

    output = b""
    try:
        output = stdout.read(max_output + 1)
    finally:
        with finish_lock:
            finished.set()
        timer.cancel()
        _kill_process_group(process)
        process.wait()
        stdout.close()

    return output, timed_out.is_set()


def run_limited(
    args: list[str],
    *,
    timeout: float,
    max_output: int = MAX_SUBPROCESS_OUTPUT,
) -> tuple[int, bytes, bytes]:
    """Run an executable with a time cap and a strict stdout byte limit.

    Args:
        args: Argument vector. It is passed directly to ``Popen``; no shell is used.
        timeout: Positive wall-clock timeout in seconds.
        max_output: Maximum accepted stdout size in bytes.

    Returns:
        ``(return_code, stdout, stderr_preview)``. The stderr preview is limited
        to the first 4096 bytes and is intended for server logs only.

    Raises:
        ValueError: If arguments or limits are invalid, or output exceeds its cap.
        TimeoutError: If the child process exceeds ``timeout``.
        OSError: If the executable cannot be started.

    """
    timeout_value = _validate_run_limited_args(args, timeout, max_output)

    with tempfile.TemporaryFile(mode="w+b") as stderr_file:
        process = subprocess.Popen(  # noqa: S603 - internal argv; shell=False.
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=stderr_file,
            shell=False,
            start_new_session=os.name == "posix",
        )
        output, timed_out = _collect_process_output(
            process,
            timeout_value,
            max_output,
        )

        if timed_out:
            raise SubprocessTimeoutError
        if len(output) > max_output:
            raise SubprocessOutputLimitError

        stderr_file.seek(0)
        stderr_preview = stderr_file.read(MAX_STDERR_PREVIEW)
        return int(process.returncode or 0), output, stderr_preview


def _is_integer(value: object) -> bool:
    return isinstance(value, int)
