# Copyright (c) 2026 Nikolai Zelensky
"""Measure the capacity of a work queue through its public admission API."""

import asyncio
from dataclasses import dataclass

from audiodoc.common.work_queue import WorkQueue


@dataclass(frozen=True)
class QueueCapacity:
    """Describe how many callers a queue admitted before it refused one."""

    active: int
    waiting: int


async def _hold_slot(queue: WorkQueue, release: asyncio.Event) -> None:
    async with queue.slot():
        await release.wait()


async def _measure(queue: WorkQueue, attempts: int) -> QueueCapacity:
    release = asyncio.Event()
    admitted: list[asyncio.Task[None]] = []
    for _ in range(attempts):
        task = asyncio.create_task(_hold_slot(queue, release))
        await asyncio.sleep(0)
        if task.done():
            task.exception()
            break
        admitted.append(task)
    capacity = QueueCapacity(
        active=len(admitted) - queue.waiting,
        waiting=queue.waiting,
    )
    release.set()
    await asyncio.gather(*admitted)
    return capacity


def measure_capacity(queue: WorkQueue, attempts: int = 64) -> QueueCapacity:
    """Fill a queue until it refuses a caller and report what it admitted."""
    return asyncio.run(_measure(queue, attempts))
