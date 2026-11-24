# Copyright (c) 2026 Nikolai Zelensky
"""Tests for bounded work admission and queue saturation."""

import asyncio

import pytest

from audiodoc.common.work_queue import QueueFullError, WorkQueue
from audiodoc.errors.base import ServerBusyError


def test_work_queue_limits_active_and_waiting_tasks() -> None:
    async def scenario() -> None:
        queue = WorkQueue(workers=2, max_waiting=4)
        release = asyncio.Event()
        active = 0
        max_active = 0

        async def worker() -> None:
            nonlocal active, max_active
            async with queue.slot():
                active += 1
                max_active = max(max_active, active)
                try:
                    await release.wait()
                finally:
                    active -= 1

        tasks = [asyncio.create_task(worker()) for _ in range(7)]
        for _ in tasks:
            await asyncio.sleep(0)

        expected_active = 2
        assert active == expected_active
        expected_max_active = 2
        assert max_active == expected_max_active
        expected_waiting = 4
        assert queue.waiting == expected_waiting
        assert queue.is_full() is True

        release.set()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        assert sum(isinstance(item, QueueFullError) for item in results) == 1
        expected_max_active = 2
        assert max_active == expected_max_active
        assert queue.waiting == 0
        assert queue.is_full() is False

    asyncio.run(scenario())


def test_work_queue_uses_injected_application_busy_error() -> None:
    async def scenario() -> None:
        queue = WorkQueue(workers=1, max_waiting=0, error_factory=ServerBusyError)
        release = asyncio.Event()

        async def hold_slot() -> None:
            async with queue.slot():
                await release.wait()

        active = asyncio.create_task(hold_slot())
        await asyncio.sleep(0)
        assert queue.is_full()
        with pytest.raises(ServerBusyError):
            async with queue.slot():
                pass
        release.set()
        await active

    asyncio.run(scenario())


def test_work_queue_validates_capacity() -> None:
    with pytest.raises(ValueError, match="workers must be a positive integer"):
        WorkQueue(0, 1)
    with pytest.raises(ValueError, match="max_waiting must be a non-negative integer"):
        WorkQueue(1, -1)
