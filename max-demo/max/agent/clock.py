"""
One clock for everything time-based (job runner, approval expiry, "tomorrow"), so tests can move time.
All times are timezone-aware UTC.
"""

from datetime import datetime, timedelta, timezone


class Clock:
    """The real clock."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FakeClock(Clock):
    """A clock that only moves when a test moves it."""

    def __init__(self, start: datetime):
        self._now = _utc(start)

    def now(self) -> datetime:
        return self._now

    def advance(self, **delta) -> datetime:
        """advance(hours=25), advance(minutes=15), ..."""
        self._now += timedelta(**delta)
        return self._now

    def set(self, when: datetime) -> datetime:
        self._now = _utc(when)
        return self._now


class OffsetClock(Clock):
    """The real clock, optionally shifted. Max's test hooks (MAX_TEST_HOOKS=1, simulator only) move it so
    end-to-end tests can reach 'the day before the due date' without waiting."""

    def __init__(self):
        self.offset = timedelta(0)

    def now(self) -> datetime:
        return datetime.now(timezone.utc) + self.offset

    def set(self, when: datetime) -> datetime:
        self.offset = _utc(when) - datetime.now(timezone.utc)
        return self.now()

    def reset(self) -> None:
        self.offset = timedelta(0)


def _utc(when: datetime) -> datetime:
    if when.tzinfo is None:
        raise ValueError("use a timezone-aware datetime (e.g. tzinfo=timezone.utc)")
    return when.astimezone(timezone.utc)


SYSTEM = Clock()
