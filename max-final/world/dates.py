"""
Sliding dates. The world is written with working-day offsets from "today" (0 = today, -1 = the working day before,
+3 = three working days ahead), so its history always ends today and never falls on a weekend. Times are Tokyo
times (the team's time zone).

  clock = Clock(date.today())
  clock.day(-12)              the date 12 working days ago
  clock.at(-12, "14:32")      that moment as a UTC timestamp (ISO, like the simulated Teams stores it)
  render(text, clock)         fills placeholders in message and file text:
      {date:-1}  Thu 26 Nov            {fulldate:-1}  Thursday 26 November 2026
      {iso:-1}   2026-11-26
      {month@-10:-1}  October: one calendar month before the month of working day -10   {mon@-10:0}  Nov
  Months always count from a working day (the event's own date), never from today: "next month" in a message
  posted on 30 Oct must mean November whatever day the world is loaded.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

TOKYO = ZoneInfo("Asia/Tokyo")
PLACEHOLDER = re.compile(r"\{(date|fulldate|iso):([+-]?\d+)\}|\{(month|mon)@([+-]?\d+):([+-]?\d+)\}")
SUSPICIOUS = re.compile(r"\{[a-z]+(@[+-]?\d+)?:[+-]?\d+\}")  # looks like a placeholder but isn't one we know


class Clock:
    def __init__(self, today: date):
        self.today = today
        self.zero = today
        while self.zero.weekday() >= 5:  # weekend: "today" in the world is the last working day
            self.zero -= timedelta(days=1)

    def day(self, offset: int) -> date:
        d, step = self.zero, (1 if offset > 0 else -1)
        for _ in range(abs(offset)):
            d += timedelta(days=step)
            while d.weekday() >= 5:
                d += timedelta(days=step)
        return d

    def at(self, offset: int, hhmm: str) -> str:
        """UTC ISO timestamp (milliseconds, Z) of a Tokyo time on a working day."""
        h, m = (int(x) for x in hhmm.split(":"))
        local = datetime.combine(self.day(offset), time(h, m), TOKYO)
        return local.astimezone(timezone.utc).replace(tzinfo=None).isoformat(timespec="milliseconds") + "Z"

    def month(self, offset: int, from_wd: int = 0) -> date:
        """The first day of the calendar month `offset` months from the month of working day `from_wd`."""
        base = self.day(from_wd)
        y, m = divmod(base.year * 12 + base.month - 1 + offset, 12)
        return date(y, m + 1, 1)

    def age_days(self, offset: int) -> int:
        """How many calendar days ago that working day is (for the 30-day window)."""
        return (self.zero - self.day(offset)).days


def render(text: str, clock: Clock) -> str:
    def one(m: re.Match) -> str:
        if m.group(3):  # {month@W:N}
            d = clock.month(int(m.group(5)), from_wd=int(m.group(4)))
            return d.strftime("%B" if m.group(3) == "month" else "%b")
        kind, n = m.group(1), int(m.group(2))
        d = clock.day(n)
        if kind == "date":
            return f"{d.strftime('%a')} {d.day} {d.strftime('%b')}"
        if kind == "fulldate":
            return f"{d.strftime('%A')} {d.day} {d.strftime('%B %Y')}"
        return d.isoformat()

    out = PLACEHOLDER.sub(one, text)
    bad = SUSPICIOUS.search(out)
    if bad:
        raise ValueError(f"unknown placeholder {bad.group(0)!r}")
    return out
