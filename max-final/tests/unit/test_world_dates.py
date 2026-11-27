"""World dates slide: the history always ends "today", counted in working days (no posts on weekends)."""

from datetime import date, datetime

import pytest

from world.dates import Clock, render

FRI = date(2026, 11, 27)   # a Friday
SAT = date(2026, 11, 28)
MON = date(2026, 11, 30)


def test_working_day_offsets_skip_weekends():
    c = Clock(FRI)
    assert c.day(0) == FRI
    assert c.day(-1) == date(2026, 11, 26)          # Thu
    assert c.day(-5) == date(2026, 11, 20)          # last Fri
    assert c.day(+1) == date(2026, 11, 30)          # next Mon
    assert Clock(MON).day(-1) == date(2026, 11, 27)  # Fri before


def test_on_a_weekend_today_is_the_last_working_day():
    assert Clock(SAT).day(0) == FRI


def test_tokyo_time_becomes_utc():
    at = Clock(FRI).at(-1, "14:32")                  # Thu 14:32 in Tokyo = 05:32 UTC
    assert at == datetime(2026, 11, 26, 5, 32).isoformat() + ".000Z"


def test_render_dates_and_months():
    c = Clock(FRI)
    text = "Due {date:-1}, launch {date:+33}; prices for {month@0:-1} vs {month@0:0} ({mon@0:-2})."
    assert render(text, c) == "Due Thu 26 Nov, launch Wed 13 Jan; prices for October vs November (Sep)."


def test_months_count_from_the_messages_own_day():
    """A notice posted on Fri 30 Oct saying 'next month' means November, even when the world is loaded in December."""
    c = Clock(date(2026, 12, 14))                    # 30 Oct is 31 working days back
    assert c.day(-31) == date(2026, 10, 30)
    assert render("{month@-31:+1}", c) == "November"
    assert render("{month@0:+1}", c) == "January"


def test_month_counted_from_today_is_refused():
    with pytest.raises(ValueError):
        render("{month:-1}", Clock(FRI))


def test_render_full_date_and_iso():
    c = Clock(FRI)
    assert render("{fulldate:-1}|{iso:-1}", c) == "Thursday 26 November 2026|2026-11-26"


def test_unknown_placeholder_is_an_error():
    with pytest.raises(ValueError):
        render("{nonsense:1}", Clock(FRI))


def test_plain_braces_are_left_alone():
    assert render("JSON {\"a\": 1} and {}", Clock(FRI)) == "JSON {\"a\": 1} and {}"


def test_calendar_age_of_a_working_day():
    c = Clock(FRI)
    assert c.age_days(-5) == 7
    assert c.age_days(0) == 0
