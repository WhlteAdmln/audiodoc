# Copyright (c) 2026 Nikolai Zelensky
"""Fake listening sockets for port diagnostics."""

from typing import Self


class FakeSocket:
    """Remember the bound address and optionally refuse the bind."""

    def __init__(self, *, unavailable: bool = False) -> None:
        """Store whether the port is already in use."""
        self.unavailable = unavailable
        self.address: tuple[str, int] | None = None

    def __enter__(self) -> Self:
        """Return the socket itself."""
        return self

    def __exit__(self, *_args: object) -> None:
        """Leave exceptions to the caller."""
        return

    def bind(self, address: tuple[str, int]) -> None:
        """Record the address and raise when the port is in use."""
        self.address = address
        if self.unavailable:
            raise OSError
