# Copyright (c) 2026 Nikolai Zelensky
"""Observe operating system processes from tests."""

import os
import time


def process_exists(pid: int) -> bool:
    """Return whether a process with this identifier still exists."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def wait_until_gone(pid: int, timeout: float = 5.0) -> bool:
    """Poll until the process disappears; return whether it did in time."""
    deadline = time.monotonic() + timeout
    while process_exists(pid):
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.02)
    return True
