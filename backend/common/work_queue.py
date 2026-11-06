"""Bounded asynchronous admission queues for resource-intensive work."""

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager


class QueueFullError(RuntimeError):
    """Neutral common-layer signal that no active or waiting slot is available."""


class WorkQueue:
    """Limit active workers and the number of tasks allowed to wait.

    Admission is reserved before the first await in ``slot``. A caller that
    cannot enter the bounded waiting room is rejected immediately. An
    application-specific exception factory can map saturation to HTTP 503
    without making this common utility depend on the application error package.
    """

    def __init__(
        self,
        workers: int,
        max_waiting: int,
        *,
        error_factory: Callable[[], Exception] = QueueFullError,
    ) -> None:
        """Create a queue with active slots, waiting positions, and error factory."""
        if isinstance(workers, bool) or not isinstance(workers, int) or workers <= 0:
            raise ValueError("workers must be a positive integer")
        self._validate_max_waiting(max_waiting)
        if not callable(error_factory):
            raise TypeError("error_factory must be callable")

        self._semaphore = asyncio.Semaphore(workers)
        self._workers = workers
        self._max_waiting = max_waiting
        self._waiting = 0
        self._active = 0
        self._error_factory = error_factory

    @staticmethod
    def _validate_max_waiting(max_waiting: int) -> None:
        if (
            isinstance(max_waiting, bool)
            or not isinstance(max_waiting, int)
            or max_waiting < 0
        ):
            raise ValueError("max_waiting must be a non-negative integer")

    @property
    def waiting(self) -> int:
        """Return the current number of tasks waiting for an active slot."""
        return self._waiting

    def is_full(self) -> bool:
        """Return whether all workers and all waiting positions are occupied."""
        return self._semaphore.locked() and self._waiting >= self._max_waiting

    def set_max_waiting(self, max_waiting: int) -> None:
        """Update the waiting-room size during application startup only."""
        self._validate_max_waiting(max_waiting)
        if self._waiting or self._active:
            raise RuntimeError("cannot reconfigure a queue while it is in use")
        self._max_waiting = max_waiting

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        """Reserve admission, wait for a worker, and release it on exit."""
        # No await is allowed between this check and increment: callers share
        # one event loop and therefore cannot overbook the waiting room here.
        if self.is_full():
            raise self._error_factory()

        self._waiting += 1
        acquired = False
        try:
            await self._semaphore.acquire()
            acquired = True
            self._active += 1
        finally:
            self._waiting -= 1

        try:
            yield
        finally:
            if acquired:
                self._active -= 1
                self._semaphore.release()
