# Copyright (c) 2026 Nikolai Zelensky
"""Spooled upload files that signal when they roll over to disk and close."""

import tempfile
import threading
from pathlib import Path


class TrackedSpooledTemporaryFile(tempfile.SpooledTemporaryFile[bytes]):
    """Roll over to disk after one byte and signal the rollover and the close."""

    def __init__(
        self, directory: Path, rolled: threading.Event, closed: threading.Event
    ) -> None:
        """Create a spooled file that rolls over into the given directory."""
        super().__init__(max_size=1, dir=directory)
        self.rolled = rolled
        self.closed_event = closed

    def write(self, s: bytes) -> int:
        """Write the data and signal once the file lives on disk."""
        written = super().write(s)
        if self._rolled:
            self.rolled.set()
        return written

    def close(self) -> None:
        """Close the file and signal it."""
        try:
            super().close()
        finally:
            self.closed_event.set()
