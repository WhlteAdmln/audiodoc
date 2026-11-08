"""Monotonic processing deadlines shared by document extractors.

A single deadline is passed through the synchronous extraction pipeline so each
expensive page, sheet, slide, OCR frame, or subprocess can respect one total cap.
"""

import math
import time


class _InvalidDeadlineDurationError(ValueError):
    """Raised when a deadline duration is invalid."""

    def __init__(self) -> None:
        """Initialize the validation error."""
        super().__init__("seconds must be a finite positive number")


class DeadlineExceededError(TimeoutError):
    """Neutral common-layer signal that an operation exhausted its deadline."""

    def __init__(self, message: str = "processing deadline exceeded") -> None:
        """Initialize the deadline error with its default message."""
        super().__init__(message)


class Deadline:
    """Track the remaining wall-clock budget for one processing operation."""

    def __init__(self, seconds: float) -> None:
        """Create a deadline relative to the current monotonic clock."""
        duration = float(seconds)
        if not math.isfinite(duration) or duration <= 0:
            raise _InvalidDeadlineDurationError
        self._end = time.monotonic() + duration

    def remaining(self) -> float:
        """Return the remaining time in seconds (possibly zero or negative)."""
        return self._end - time.monotonic()

    def check(self) -> None:
        """Raise when the total processing budget expires."""
        if self.remaining() <= 0:
            raise DeadlineExceededError
