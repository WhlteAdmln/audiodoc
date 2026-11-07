"""Asynchronous, bounded execution of the synchronous Document Engine pipeline."""

import asyncio

from backend.common.deadline import Deadline
from backend.common.work_queue import WorkQueue
from backend.document_engine.limits import (
    DOCUMENT_PROCESSING_TIMEOUT,
    MAX_CONCURRENT_DOCUMENTS,
)
from backend.document_engine.pipeline import process_document_sync
from backend.document_engine.result import DocumentResult
from backend.errors.base import ServerBusyError

# The default matches Settings.MAX_WAITING_DOCUMENTS. backend.main applies the
# environment-backed value before registering API routers.
document_queue = WorkQueue(
    MAX_CONCURRENT_DOCUMENTS,
    4,
    error_factory=ServerBusyError,
)


async def _run_pipeline(
    data: bytes,
    filename: str,
    max_characters: int | None,
) -> DocumentResult:
    """Run one pipeline in a thread and hold the slot until that thread exits."""
    deadline = Deadline(DOCUMENT_PROCESSING_TIMEOUT)
    worker = asyncio.create_task(
        asyncio.to_thread(
            process_document_sync,
            data,
            filename,
            max_characters,
            deadline,
        )
    )
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        # Cancelling asyncio.to_thread does not stop the OS thread. Keep this
        # queue slot until the worker really exits so concurrency stays bounded.
        while not worker.done():
            try:
                await asyncio.shield(worker)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        raise


async def process_document(
    data: bytes,
    filename: str,
    max_characters: int | None = None,
    *,
    _slot_acquired: bool = False,
) -> DocumentResult:
    """Process a document in a worker thread with bounded admission and deadline.

    ``_slot_acquired`` is reserved for the HTTP layer, which acquires admission
    before reading the multipart upload. Direct callers use the queue here.
    """
    if _slot_acquired:
        return await _run_pipeline(data, filename, max_characters)

    async with document_queue.slot():
        return await _run_pipeline(data, filename, max_characters)
