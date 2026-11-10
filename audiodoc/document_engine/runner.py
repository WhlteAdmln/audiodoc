# Copyright (c) 2026 Nikolai Zelensky
"""Asynchronous, bounded execution of the synchronous Document Engine pipeline."""

import asyncio

from audiodoc.common.deadline import Deadline
from audiodoc.common.work_queue import WorkQueue
from audiodoc.document_engine.limits import DOCUMENT_PROCESSING_TIMEOUT
from audiodoc.document_engine.pipeline import process_document_sync
from audiodoc.document_engine.result import DocumentResult


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
        cleanup = asyncio.gather(worker, return_exceptions=True)
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                continue
        raise


async def process_document(
    data: bytes,
    filename: str,
    max_characters: int | None = None,
    *,
    queue: WorkQueue,
    _slot_acquired: bool = False,
) -> DocumentResult:
    """Process a document in a worker thread with bounded admission and deadline.

    ``_slot_acquired`` is reserved for the HTTP layer, which acquires admission
    before reading the multipart upload. Direct callers use the queue here.
    ``queue`` is owned by the application or direct caller.
    """
    if _slot_acquired:
        return await _run_pipeline(data, filename, max_characters)

    async with queue.slot():
        return await _run_pipeline(data, filename, max_characters)
