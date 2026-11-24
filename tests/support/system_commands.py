# Copyright (c) 2026 Nikolai Zelensky
"""Install fake system commands that the installer calls through PATH."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def install_command(bin_dir: Path, name: str, body: str) -> Path:
    """Write an executable POSIX shell script into a fake bin directory.

    Args:
        bin_dir: The directory that is put first on PATH.
        name: The command name.
        body: The shell code that runs after the shebang line.

    Returns:
        The path of the new command.
    """
    bin_dir.mkdir(exist_ok=True)
    command = bin_dir / name
    command.write_text(f"#!/bin/sh\n{body}", encoding="utf-8")
    command.chmod(0o755)
    return command


def install_recording_command(
    bin_dir: Path, name: str, log_path: Path, *, exit_code: int = 0
) -> Path:
    """Install a command that appends its arguments to a log and exits.

    Args:
        bin_dir: The directory that is put first on PATH.
        name: The command name.
        log_path: The file that receives one line of arguments per call.
        exit_code: The status the command exits with.

    Returns:
        The path of the new command.
    """
    body = f"printf '%s\\n' \"$*\" >> '{log_path}'\nexit {exit_code}\n"
    return install_command(bin_dir, name, body)


def path_with(bin_dir: Path) -> str:
    """Return a PATH value that finds the fake commands first."""
    return str(bin_dir) + os.pathsep + os.environ["PATH"]
