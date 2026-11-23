# Copyright (c) 2026 Nikolai Zelensky
"""Asynchronous, bounded execution of the synchronous Document Engine pipeline."""

import asyncio
from functools import partial

from audiodoc.common.deadline import Deadline
from audiodoc.common.work_queue import WorkQueue, await_worker, run_in_slot
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
    return await await_worker(worker)


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
    return await run_in_slot(
        queue,
        partial(_run_pipeline, data, filename, max_characters),
        slot_acquired=_slot_acquired,
    )
