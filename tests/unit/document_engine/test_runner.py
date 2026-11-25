# Copyright (c) 2026 Nikolai Zelensky
"""Tests for the asynchronous Document Engine runner."""

import asyncio
import threading

import pytest

from audiodoc.common.work_queue import WorkQueue
from audiodoc.document_engine import runner


def test_async_runner_executes_sync_pipeline_in_a_worker_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    main_thread = threading.get_ident()
    calls = []

    def fake_process(
        data: object, filename: object, max_characters: object, deadline: object
    ) -> object:
        calls.append((data, filename, max_characters, deadline, threading.get_ident()))
        return {"format": "txt", "text": "ok", "characters": 2, "truncated": False}

    monkeypatch.setattr(runner, "process_document_sync", fake_process)

    result = asyncio.run(
        runner.process_document(
            b"body", "note.txt", queue=WorkQueue(workers=1, max_waiting=4)
        )
    )

    data, filename, max_characters, deadline, thread = calls[0]
    outcome = (
        result,
        (data, filename, max_characters),
        deadline is not None,
        thread != main_thread,
    )
    expected = (
        {"format": "txt", "text": "ok", "characters": 2, "truncated": False},
        (b"body", "note.txt", None),
        True,
        True,
    )
    assert outcome == expected, "the runner did not use a worker thread"
