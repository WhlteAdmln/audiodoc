# Copyright (c) 2026 Nikolai Zelensky
"""Fake HTTP server that answers the doctor health probe."""

from typing import Self


class FakeHealthServer:
    """Answer every request with a fixed response and record what was asked."""

    def __init__(
        self, *, status: int = 200, body: bytes = b"", refused: bool = False
    ) -> None:
        """Store the response, or refuse connections when ``refused`` is set."""
        self.status = status
        self.body = body
        self.refused = refused
        self.address: tuple[str, int] | None = None
        self.path: str | None = None
        self.closed = False

    def connect(self, host: str, port: int, *, timeout: float) -> Self:
        """Stand in for ``HTTPConnection`` and record the address."""
        del timeout
        self.address = (host, port)
        return self

    def request(self, method: str, url: str) -> None:
        """Record the requested path or refuse the connection."""
        del method
        if self.refused:
            raise ConnectionRefusedError
        self.path = url

    def getresponse(self) -> Self:
        """Return the server itself as the response."""
        return self

    def read(self) -> bytes:
        """Return the response body."""
        return self.body

    def close(self) -> None:
        """Remember that the connection was closed."""
        self.closed = True
