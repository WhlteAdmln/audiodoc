# Copyright (c) 2026 Nikolai Zelensky
"""Document bytes that record when the pipeline inspects their size."""

from typing import Self


class RecordingPayload(bytes):
    """Append ``inspected input`` to an event list when the size is read."""

    events: list[str]

    def __new__(cls, data: bytes, events: list[str]) -> Self:
        """Wrap the bytes and remember the shared event list."""
        payload = super().__new__(cls, data)
        payload.events = events
        return payload

    def __len__(self) -> int:
        """Record one inspection per run of consecutive size reads."""
        event = "inspected input"
        if not self.events or self.events[-1] != event:
            self.events.append(event)
        return super().__len__()
