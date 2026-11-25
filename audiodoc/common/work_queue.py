# Copyright (c) 2026 Nikolai Zelensky
"""Bounded asynchronous admission queues for resource-intensive work."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from enum import Enum, auto
from typing import TypeVar

_Result = TypeVar("_Result")


class _InvalidWorkerCountError(ValueError):
    """Raised when the configured worker count is invalid."""

    def __init__(self) -> None:
        """Initialize the validation error."""
        super().__init__("workers must be a positive integer")


class _InvalidMaxWaitingError(ValueError):
    """Raised when the configured waiting queue size is invalid."""

    def __init__(self) -> None:
        """Initialize the validation error."""
        super().__init__("max_waiting must be a non-negative integer")


class _InvalidErrorFactoryError(TypeError):
    """Raised when the queue error factory is not callable."""

    def __init__(self) -> None:
        """Initialize the validation error."""
        super().__init__("error_factory must be callable")


class _QueueReconfigurationError(RuntimeError):
    """Raised when a queue is reconfigured while it is in use."""

    def __init__(self) -> None:
        """Initialize the queue configuration error."""
        super().__init__("cannot reconfigure a queue while it is in use")


class _Lifecycle(Enum):
    """Lifecycle state of a work queue."""

    OPEN = auto()
    DRAINING = auto()
    CLOSED = auto()


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
        if isinstance(workers, bool) or not _is_integer(workers) or workers <= 0:
            raise _InvalidWorkerCountError
        self._validate_max_waiting(max_waiting)
        if not callable(error_factory):
            raise _InvalidErrorFactoryError

        self._semaphore = asyncio.Semaphore(workers)
        self._max_waiting = max_waiting
        self._waiting = 0
        self._active = 0
        self._error_factory = error_factory
        self._state = _Lifecycle.OPEN
        self._drained = asyncio.Event()

    @staticmethod
    def _validate_max_waiting(max_waiting: int) -> None:
        if (
            isinstance(max_waiting, bool)
            or not _is_integer(max_waiting)
            or max_waiting < 0
        ):
            raise _InvalidMaxWaitingError

    @property
    def waiting(self) -> int:
        """Return the current number of tasks waiting for an active slot."""
        return self._waiting

    def is_full(self) -> bool:
        """Return whether all workers and all waiting positions are occupied."""
        return self._semaphore.locked() and self._waiting >= self._max_waiting

    def start(self) -> None:
        """Open the queue for a new application lifespan."""
        if self._waiting or self._active:
            raise _QueueReconfigurationError
        self._state = _Lifecycle.OPEN

    async def shutdown(self) -> None:
        """Reject new work and wait until all admitted work has completed."""
        if self._state is _Lifecycle.OPEN:
            self._state = _Lifecycle.DRAINING
            self._drained = asyncio.Event()
            self._close_if_drained()
        if self._state is _Lifecycle.DRAINING:
            await self._drained.wait()

    def _close_if_drained(self) -> None:
        if (
            self._state is _Lifecycle.DRAINING
            and not self._waiting
            and not self._active
        ):
            self._state = _Lifecycle.CLOSED
            self._drained.set()

    async def _acquire_worker(self) -> None:
        """Wait for a free worker and count it as active."""
        await self._semaphore.acquire()
        self._active += 1

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        """Reserve admission, wait for a worker, and release it on exit."""
        # No await is allowed between this check and increment: callers share
        # one event loop and therefore cannot overbook the waiting room here.
        if self._state is not _Lifecycle.OPEN or self.is_full():
            raise self._error_factory()

        self._waiting += 1
        try:
            await self._acquire_worker()
        finally:
            self._waiting -= 1
            self._close_if_drained()

        try:
            yield
        finally:
            self._active -= 1
            self._semaphore.release()
            self._close_if_drained()


async def await_worker(worker: asyncio.Task[_Result]) -> _Result:
    """Await a thread-backed task and keep waiting for it after a cancellation.

    Cancelling ``asyncio.to_thread`` does not stop the OS thread. The caller keeps
    its queue slot until the worker really exits so concurrency stays bounded.
    """
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        cleanup = asyncio.gather(worker, return_exceptions=True)
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                continue
        raise


async def run_in_slot(
    queue: WorkQueue,
    operation: Callable[[], Awaitable[_Result]],
    *,
    slot_acquired: bool,
) -> _Result:
    """Run the operation in a queue slot unless the caller already holds one."""
    if slot_acquired:
        return await operation()

    async with queue.slot():
        return await operation()


def _is_integer(value: object) -> bool:
    return isinstance(value, int)
