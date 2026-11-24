# Copyright (c) 2026 Nikolai Zelensky
"""Fake listening sockets for port diagnostics."""

import os
from typing import Self


class FakeSocket:
    """Remember the bound address and optionally refuse the bind."""

    def __init__(self, *, bind_errno: int | None = None) -> None:
        """Store the error number that a bind raises, if any."""
        self.bind_errno = bind_errno
        self.address: tuple[str, int] | None = None

    def __enter__(self) -> Self:
        """Return the socket itself."""
        return self

    def __exit__(self, *_args: object) -> None:
        """Leave exceptions to the caller."""
        return

    def bind(self, address: tuple[str, int]) -> None:
        """Record the address and raise when the bind must fail."""
        self.address = address
        if self.bind_errno is not None:
            raise OSError(self.bind_errno, os.strerror(self.bind_errno))
