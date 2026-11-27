"""The world checks: the real world passes on any day; the checker catches moved facts, leaks, old edited text."""

import copy
from datetime import date

import pytest

from world import check, model
from world.dates import Clock
from world.make import files, messages


@pytest.fixture(scope="module")
def world():
    return model.load()


@pytest.fixture(scope="module")
def made(world, tmp_path_factory):
    clock = Clock(date(2026, 11, 27))
    return clock, files.make_all(world, clock, tmp_path_factory.mktemp("w")), messages.load_all(world, clock)


@pytest.mark.parametrize("today", [date(2026, 11, 30), date(2027, 3, 6)])   # a Monday, a Saturday in another month
def test_real_world_passes_on_any_day(world, today, tmp_path):
    clock = Clock(today)
    report = check.check(world, clock, files.make_all(world, clock, tmp_path), messages.load_all(world, clock))
    assert report["problems"] == []
    assert len(report["ok"]) == len(world["facts"])


def test_message_files_are_consistent(world):
    assert messages.problems(world) == []


def test_catches_a_moved_fact(world, made):
    clock, m, msgs = made
    w = copy.deepcopy(world)
    fact = next(f for f in w["facts"] if f["id"] == "F031")
    fact["at"][0]["cell"] = "C3"                       # points at last month's price instead
    assert any("F031" in p for p in check.check(w, clock, m, msgs)["problems"])


def test_catches_a_leaked_canary(world, made):
    clock, m, msgs = made
    leak = [*msgs, {"id": "x", "event": None, "place": "pp-general", "text": "BLUEHERON is going well"}]
    assert any("leaks" in p for p in check.check(world, clock, m, leak)["problems"])


def test_catches_old_edited_text_and_missing_phrases(world, made):
    clock, m, msgs = made
    bad = [dict(x, text=x["text"].replace("0142", "0124")) if x["event"] == "e603" else x for x in msgs]
    problems = check.check(world, clock, m, bad)["problems"]
    assert any("old (edited) text" in p for p in problems) and any("e603 must say" in p for p in problems)


def test_edited_and_deleted_messages_are_marked(made):
    _, _, msgs = made
    edited = next(x for x in msgs if x["event"] == "e603")
    assert edited["original"] == "Northwind contact for deliveries: Hannah Weiss, +81 3-5555-0124."
    assert next(x for x in msgs if x["event"] == "e604")["deleted"] is True


def test_message_rules(world):
    assert "not a member" in " ".join(messages.problems(world, [{"id": "a", "place": "pp-pricing", "by": "praga", "wd": -1, "at": "10:00", "text": "x"}]))
    assert "no reply threads" in " ".join(messages.problems(world, [
        {"id": "a", "place": "sync", "by": "praga", "wd": -2, "at": "10:00", "text": "x"},
        {"id": "b", "place": "sync", "by": "prince", "wd": -1, "at": "10:00", "text": "y", "reply_to": "a"}]))
    assert "earlier root post" in " ".join(messages.problems(world, [
        {"id": "a", "place": "pp-models", "by": "prince", "wd": -1, "at": "10:00", "text": "x"},
        {"id": "b", "place": "pp-models", "by": "sven", "wd": -2, "at": "10:00", "text": "y", "reply_to": "a"}]))


# ---------------------------------------------------------------- review fixes (27 Nov 2026)

def test_whole_numbers_and_words_only():
    assert check.contains("wants 300 units", "300") and check.contains("Raptor X9.", "Raptor X9")
    assert not check.contains("wants 2,300 units", "300") and not check.contains("3000 units", "300")
    assert not check.contains("18% discount", "8%") and not check.contains("16 weeks", "6 weeks")
    assert check.contains("8% discount", "8%") and check.contains("blueheron", "BLUEHERON")


def swap(msgs, event, old, new):
    return [dict(x, text=x["text"].replace(old, new)) if x["event"] == event else x for x in msgs]


def test_catches_look_alike_values(world, made):
    clock, m, msgs = made
    problems = check.check(world, clock, m, swap(msgs, "e401", "300 Raptor", "2,300 Raptor"))["problems"]
    assert any("F004" in p for p in problems)


def test_catches_an_unmarked_delete(world, made):
    clock, m, msgs = made
    bad = [dict(x, deleted=False) if x["event"] == "e604" else x for x in msgs]
    assert any("deleted should be True" in p for p in check.check(world, clock, m, bad)["problems"])


def test_old_and_deleted_text_must_appear_nowhere_else(world, made):
    clock, m, msgs = made
    extra = [*msgs, {"id": "x", "event": None, "place": "sa-general", "text": "Call Hannah on +81 3-5555-0124", "deleted": False}]
    assert any("old or deleted" in p for p in check.check(world, clock, m, extra)["problems"])
    extra = [*msgs, {"id": "y", "event": None, "place": "pr-general", "text": "Brightcore wanted 52,000 per card", "deleted": False}]
    assert any("old or deleted" in p for p in check.check(world, clock, m, extra)["problems"])


def test_canary_in_the_first_text_of_an_edited_message(world, made):
    clock, m, msgs = made
    bad = [dict(x, original="BLUEHERON") if x["event"] == "e603" else x for x in msgs]
    assert any("leaks" in p for p in check.check(world, clock, m, bad)["problems"])


def test_not_in_data_topics_must_be_absent(world, made):
    clock, m, msgs = made
    extra = [*msgs, {"id": "z", "event": None, "place": "pp-general", "text": "The battery lasts all day", "deleted": False}]
    assert any("F112" in p for p in check.check(world, clock, m, extra)["problems"])


MONTH_EDGES = [date(2026, 11, 30), date(2026, 12, 1), date(2026, 12, 4), date(2026, 12, 14),
               date(2026, 12, 15), date(2027, 1, 4), date(2027, 1, 5)]


@pytest.mark.parametrize("today", MONTH_EDGES)
def test_month_names_agree_with_the_messages_own_dates(world, today, tmp_path):
    """Around month starts: 'this month' in a message, the price sheet's newest month and Meridian's 'next month'
    must all fit the date each message / file was posted (found by the reviewer, 27 Nov 2026)."""
    from openpyxl import load_workbook

    clock = Clock(today)
    made = files.make_all(world, clock, tmp_path, samples_only=True)
    msgs = {x["id"]: x for x in messages.load_all(world, clock)}
    v2 = next(x for x in made if x["file"] == "parts-prices" and x["v"] == 2)
    newest = load_workbook(v2["path"])["Memory"]["D1"].value
    upload = clock.day(-10)
    assert newest == upload.strftime("%b")                                        # "this month" = upload month
    assert upload.strftime("%B") in msgs["e204"]["text"]
    notice = next(x for x in made if x["file"] == "meridian-notice")              # posted at -19, before the sheet's
    month_names = [date(2026, m, 1).strftime("%B") for m in range(1, 13)]        # months: it must not name one
    assert not any(check.contains(check.file_text(notice), m) for m in month_names)
    assert not any(check.contains(msgs["e201"]["text"], m) for m in month_names)
    assert check.check(world, clock, made, list(msgs.values()))["problems"] == []
