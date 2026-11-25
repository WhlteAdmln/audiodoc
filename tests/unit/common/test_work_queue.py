# Copyright (c) 2026 Nikolai Zelensky
"""Tests for bounded work admission and queue saturation."""

import asyncio

import pytest

from audiodoc.common.work_queue import QueueFullError, WorkQueue, run_in_slot
from audiodoc.errors.base import ServerBusyError
from tests.support.work_queues import QueueCapacity, measure_capacity


async def _hold(queue: WorkQueue, release: asyncio.Event) -> None:
    async with queue.slot():
        await release.wait()


async def _enter(queue: WorkQueue) -> None:
    async with queue.slot():
        return


async def _entry_error(queue: WorkQueue) -> type[BaseException]:
    outcome = await asyncio.gather(_enter(queue), return_exceptions=True)
    return type(outcome[0])


async def _rejection_while_full(queue: WorkQueue) -> type[BaseException]:
    release = asyncio.Event()
    holder = asyncio.create_task(_hold(queue, release))
    await asyncio.sleep(0)
    rejected = await _entry_error(queue)
    release.set()
    await holder
    return rejected


async def _full_after_crash(queue: WorkQueue) -> bool:
    with pytest.raises(LookupError):
        async with queue.slot():
            raise LookupError
    return queue.is_full()


async def _waiting_after_cancel(queue: WorkQueue) -> int:
    release = asyncio.Event()
    holder = asyncio.create_task(_hold(queue, release))
    await asyncio.sleep(0)
    waiter = asyncio.create_task(_hold(queue, release))
    await asyncio.sleep(0)
    waiter.cancel()
    await asyncio.gather(waiter, return_exceptions=True)
    waiting = queue.waiting
    release.set()
    await holder
    return waiting


async def _rejection_after_shutdown(queue: WorkQueue) -> type[BaseException]:
    await queue.shutdown()
    return await _entry_error(queue)


async def _hold_and_record(
    queue: WorkQueue, release: asyncio.Event, events: list[str]
) -> None:
    await _hold(queue, release)
    events.append("work finished")


async def _shut_down_and_record(queue: WorkQueue, events: list[str]) -> None:
    await queue.shutdown()
    events.append("shutdown finished")


async def _completion_order(queue: WorkQueue, shutdowns: int) -> list[str]:
    events: list[str] = []
    release = asyncio.Event()
    holder = asyncio.create_task(_hold_and_record(queue, release, events))
    await asyncio.sleep(0)
    closers = [
        asyncio.create_task(_shut_down_and_record(queue, events))
        for _ in range(shutdowns)
    ]
    await asyncio.sleep(0)
    release.set()
    await asyncio.gather(holder, *closers)
    return events


async def _restart_while_busy(queue: WorkQueue) -> str:
    release = asyncio.Event()
    holder = asyncio.create_task(_hold(queue, release))
    await asyncio.sleep(0)
    message = ""
    try:
        queue.start()
    except RuntimeError as error:
        message = str(error)
    release.set()
    await holder
    return message


@pytest.mark.parametrize(("workers", "max_waiting"), [(2, 4), (1, 0), (3, 1)])
def test_admits_exactly_its_workers_and_waiting_room(
    workers: int, max_waiting: int
) -> None:
    queue = WorkQueue(workers=workers, max_waiting=max_waiting)

    capacity = measure_capacity(queue)

    expected_capacity = QueueCapacity(active=workers, waiting=max_waiting)
    assert capacity == expected_capacity, "queue admitted a wrong number of callers"


def test_rejects_with_neutral_error_when_full() -> None:
    queue = WorkQueue(workers=1, max_waiting=0)

    rejected = asyncio.run(_rejection_while_full(queue))

    assert rejected is QueueFullError, "a full queue must reject the caller"


def test_rejects_with_injected_application_error_when_full() -> None:
    queue = WorkQueue(workers=1, max_waiting=0, error_factory=ServerBusyError)

    rejected = asyncio.run(_rejection_while_full(queue))

    assert rejected is ServerBusyError, "the injected error factory is ignored"


def test_frees_the_slot_when_work_raises() -> None:
    queue = WorkQueue(workers=1, max_waiting=0)

    full = asyncio.run(_full_after_crash(queue))

    assert full is False, "a crashed worker kept its slot"


def test_frees_the_waiting_position_of_a_cancelled_caller() -> None:
    queue = WorkQueue(workers=1, max_waiting=3)

    waiting = asyncio.run(_waiting_after_cancel(queue))

    expected_waiting = 0
    assert waiting == expected_waiting, "a cancelled caller still counts as waiting"


def test_rejects_new_work_after_shutdown() -> None:
    queue = WorkQueue(workers=5, max_waiting=5, error_factory=ServerBusyError)

    rejected = asyncio.run(_rejection_after_shutdown(queue))

    assert rejected is ServerBusyError, "a shut down queue accepted work"


@pytest.mark.parametrize("shutdowns", [1, 3])
def test_shutdown_waits_until_admitted_work_finishes(shutdowns: int) -> None:
    queue = WorkQueue(workers=3, max_waiting=7)

    order = asyncio.run(_completion_order(queue, shutdowns))

    expected_order = ["work finished"] + ["shutdown finished"] * shutdowns
    assert order == expected_order, "shutdown returned before admitted work finished"


def test_refuses_restart_while_work_is_admitted() -> None:
    queue = WorkQueue(workers=2, max_waiting=1)

    message = asyncio.run(_restart_while_busy(queue))

    expected_message = "cannot reconfigure a queue while it is in use"
    assert message == expected_message, "a busy queue was restarted"


def test_restart_reopens_a_shut_down_queue() -> None:
    queue = WorkQueue(workers=1, max_waiting=2)
    asyncio.run(queue.shutdown())
    queue.start()

    capacity = measure_capacity(queue)

    expected_capacity = QueueCapacity(active=1, waiting=2)
    assert capacity == expected_capacity, "a restarted queue stays closed"


def test_run_in_slot_runs_without_a_new_slot_when_caller_holds_one() -> None:
    queue = WorkQueue(workers=1, max_waiting=0)

    async def operation() -> str:
        return "ready-7f"

    async def scenario() -> str:
        async with queue.slot():
            return await run_in_slot(queue, operation, slot_acquired=True)

    result = asyncio.run(scenario())

    expected_result = "ready-7f"
    assert result == expected_result, "the held slot blocked the operation"


def test_run_in_slot_takes_a_slot_when_caller_holds_none() -> None:
    queue = WorkQueue(workers=1, max_waiting=0, error_factory=ServerBusyError)
    asyncio.run(queue.shutdown())

    async def operation() -> str:
        return "unreachable"

    with pytest.raises(ServerBusyError) as caught:
        asyncio.run(run_in_slot(queue, operation, slot_acquired=False))

    expected_code = "server_busy"
    assert caught.value.code == expected_code, "the operation bypassed admission"


@pytest.mark.parametrize("workers", [0, -3, True, 1.5, "2", None])
def test_rejects_invalid_worker_count(workers: object) -> None:
    with pytest.raises(ValueError, match="workers") as caught:
        WorkQueue(workers, 1)

    expected_message = "workers must be a positive integer"
    assert str(caught.value) == expected_message, "invalid worker count accepted"


@pytest.mark.parametrize("max_waiting", [-1, False, 0.5, "4", None])
def test_rejects_invalid_waiting_room(max_waiting: object) -> None:
    with pytest.raises(ValueError, match="max_waiting") as caught:
        WorkQueue(1, max_waiting)

    expected_message = "max_waiting must be a non-negative integer"
    assert str(caught.value) == expected_message, "invalid waiting room accepted"


@pytest.mark.parametrize("error_factory", [None, "QueueFullError", 503])
def test_rejects_error_factory_that_is_not_callable(error_factory: object) -> None:
    with pytest.raises(TypeError) as caught:
        WorkQueue(1, 1, error_factory=error_factory)

    expected_message = "error_factory must be callable"
    assert str(caught.value) == expected_message, "non-callable factory accepted"
