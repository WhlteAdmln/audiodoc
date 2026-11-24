# Copyright (c) 2026 Nikolai Zelensky
"""A manual monotonic clock for code that measures deadlines."""


class FakeMonotonicClock:
    """Stand in for the ``time`` module and move forward only when told to."""

    def __init__(self) -> None:
        """Start the clock at zero."""
        self.now = 0.0

    def monotonic(self) -> float:
        """Return the current reading."""
        return self.now

    def advance(self, seconds: float) -> None:
        """Move the clock forward."""
        self.now += seconds
