# Copyright (c) 2026 Nikolai Zelensky
"""A stand-in for the ``tempfile`` module that tracks the files it opens."""

import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import IO


class TrackingTempfile:
    """Create anonymous temporary files in one directory and remember the handles."""

    def __init__(self, directory: Path) -> None:
        """Store the directory that receives the temporary files."""
        self.directory = directory
        self.opened: list[IO[bytes]] = []

    def open(self, mode: str = "w+b") -> IO[bytes]:
        """Open a binary temporary file whose name is removed at once."""
        descriptor, name = tempfile.mkstemp(dir=self.directory)
        Path(name).unlink()
        handle = os.fdopen(descriptor, mode)
        self.opened.append(handle)
        return handle

    @property
    def module(self) -> SimpleNamespace:
        """Return an object that replaces the ``tempfile`` module."""
        return SimpleNamespace(TemporaryFile=self.open)

    @property
    def all_closed(self) -> bool:
        """Return whether files were opened and every one of them is closed."""
        return bool(self.opened) and all(handle.closed for handle in self.opened)
