"""Run external programs without a shell and with bounded time and output."""

import math
import subprocess
import tempfile
import threading

MAX_SUBPROCESS_OUTPUT = 20 * 1024 * 1024
MAX_STDERR_PREVIEW = 4096


class SubprocessTimeoutError(TimeoutError):
    """A child process exceeded its configured wall-clock timeout."""


class SubprocessOutputLimitError(ValueError):
    """A child process produced more stdout than the accepted byte limit."""


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
    if not args or any(not isinstance(argument, str) for argument in args):
        raise ValueError("args must be a non-empty list of strings")
    timeout_value = float(timeout)
    if not math.isfinite(timeout_value) or timeout_value <= 0:
        raise ValueError("timeout must be a finite positive number")
    if (
        isinstance(max_output, bool)
        or not isinstance(max_output, int)
        or max_output < 0
    ):
        raise ValueError("max_output must be a non-negative integer")

    timed_out = threading.Event()
    with tempfile.TemporaryFile(mode="w+b") as stderr_file:
        process = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=stderr_file,
            shell=False,
        )
        assert process.stdout is not None

        def on_timeout() -> None:
            """Kill the child process when the wall-clock timer expires."""
            if process.poll() is None:
                timed_out.set()
                try:
                    process.kill()
                except OSError:
                    pass

        timer = threading.Timer(timeout_value, on_timeout)
        timer.daemon = True
        timer.start()

        output = b""
        try:
            output = process.stdout.read(max_output + 1)
            if len(output) > max_output and process.poll() is None:
                try:
                    process.kill()
                except OSError:
                    pass
            process.wait()
        finally:
            timer.cancel()
            if process.poll() is None:
                try:
                    process.kill()
                except OSError:
                    pass
            process.wait()
            process.stdout.close()

        if timed_out.is_set():
            raise SubprocessTimeoutError("subprocess timed out")
        if len(output) > max_output:
            raise SubprocessOutputLimitError("subprocess stdout exceeded its limit")

        stderr_file.seek(0)
        stderr_preview = stderr_file.read(MAX_STDERR_PREVIEW)
        return int(process.returncode or 0), output, stderr_preview
