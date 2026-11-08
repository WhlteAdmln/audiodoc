"""Tests for shared, monotonic processing deadlines."""

import pytest

from backend.common.deadline import Deadline, DeadlineExceededError
from backend.document_engine import pipeline
from backend.errors.documents import ProcessingTimeoutError


def test_deadline_reports_remaining_time_and_expires(monkeypatch):
    ticks = iter((100.0, 100.25, 101.1))
    monkeypatch.setattr("backend.common.deadline.time.monotonic", lambda: next(ticks))
    deadline = Deadline(1.0)

    assert deadline.remaining() == pytest.approx(0.75)
    with pytest.raises(DeadlineExceededError):
        raise DeadlineExceededError


def test_deadline_requires_a_finite_positive_duration():
    for value in (0, -1, float("inf"), float("nan")):
        with pytest.raises(
            ValueError, match="seconds must be a finite positive number"
        ):
            Deadline(value)


def test_pipeline_maps_deadline_expiration_to_safe_backend_error(monkeypatch):
    monkeypatch.setattr(pipeline, "detect_format", lambda *_args: "txt")

    class ExpiredDeadline:
        def check(self):
            from backend.common.deadline import DeadlineExceededError

            raise DeadlineExceededError

    with pytest.raises(ProcessingTimeoutError):
        pipeline.process_document_sync(b"hello", "note.txt", deadline=ExpiredDeadline())
