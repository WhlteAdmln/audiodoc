# Copyright (c) 2026 Nikolai Zelensky
"""Fake pytest items for collection hook tests."""

from pathlib import Path


class FakeMarkerItem:
    """Remember the markers that a collection hook adds to a test file."""

    def __init__(self, path: Path) -> None:
        """Store the path of the collected test file."""
        self.path = path
        self.markers: list[str] = []

    def add_marker(self, marker: str) -> None:
        """Record the added marker."""
        self.markers.append(marker)
