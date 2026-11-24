# Copyright (c) 2026 Nikolai Zelensky
"""Tests for shared, monotonic processing deadlines."""

import math

import pytest

from audiodoc.common import deadline as deadline_module
from audiodoc.common.deadline import Deadline, DeadlineExceededError
from tests.support.clock import FakeMonotonicClock


@pytest.fixture(name="clock")
def fixture_clock(monkeypatch: pytest.MonkeyPatch) -> FakeMonotonicClock:
    """Replace the clock the deadline module reads with a manual one."""
    clock = FakeMonotonicClock()
    clock.advance(4_183.5)
    monkeypatch.setattr(deadline_module, "time", clock)
    return clock


def test_reports_remaining_time(clock: FakeMonotonicClock) -> None:
    deadline = Deadline(1.75)
    clock.advance(0.5)

    remaining = deadline.remaining()

    expected_remaining = 1.25
    assert remaining == pytest.approx(expected_remaining), "wrong remaining time"


def test_reports_negative_remaining_time_after_expiry(
    clock: FakeMonotonicClock,
) -> None:
    deadline = Deadline(0.3)
    clock.advance(2.8)

    remaining = deadline.remaining()

    expected_remaining = -2.5
    assert remaining == pytest.approx(expected_remaining), "overdue time is lost"


@pytest.mark.parametrize("elapsed", [0.75, 13.0])
def test_check_raises_when_budget_is_spent(
    clock: FakeMonotonicClock, elapsed: float
) -> None:
    deadline = Deadline(0.75)
    clock.advance(elapsed)

    with pytest.raises(DeadlineExceededError) as caught:
        deadline.check()

    expected_message = "processing deadline exceeded"
    assert str(caught.value) == expected_message, "wrong deadline error message"


def test_expired_deadline_is_a_timeout_error(clock: FakeMonotonicClock) -> None:
    deadline = Deadline(0.01)
    clock.advance(1.0)

    with pytest.raises(TimeoutError) as caught:
        deadline.check()

    assert isinstance(caught.value, DeadlineExceededError), "callers catch TimeoutError"


@pytest.mark.parametrize("seconds", [0, -0.0, -1, -1e-9, math.inf, -math.inf, math.nan])
def test_rejects_duration_that_is_not_finite_and_positive(seconds: float) -> None:
    with pytest.raises(ValueError, match="seconds") as caught:
        Deadline(seconds)

    expected_message = "seconds must be a finite positive number"
    assert str(caught.value) == expected_message, "wrong validation message"
