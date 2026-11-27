"""The full world's message writer: plans batches, asks the model, keeps only messages that pass every rule,
stops at its budget. Offline: a fake model plays the answers."""

import asyncio
import copy
import json

import pytest

from world import model
from world.make import messages, write_messages as wm

GEN = {"per_place": {"pp-general": 14, "sync": 7}}


@pytest.fixture
def world():
    w = copy.deepcopy(model.load())
    w["generation"] = GEN
    return w


def test_plan_covers_every_place_and_the_whole_history(world):
    batches = wm.plan(world)
    assert {b["place"] for b in batches} == {"pp-general", "sync"}
    assert sum(b["count"] for b in batches if b["place"] == "pp-general") == 14
    assert min(b["wd_from"] for b in batches) == -world["calendar"]["history_workdays"] + 1
    assert max(b["wd_to"] for b in batches) == 0


GOOD = {"by": "sven", "wd": -12, "at": "10:15", "text": "Anyone up for coffee after the review?"}


def check_one(world, item, place="pp-general", existing=()):
    batch = {"place": place, "wd_from": -15, "wd_to": -10, "count": 3}
    return wm.validate(world, batch, [item], list(existing))


@pytest.mark.parametrize("change, why", [
    ({"text": "We need 300 more units"}, "digit"),
    ({"text": "See you in December"}, "month"),
    ({"text": "Let's meet on Tuesday"}, "weekday"),
    ({"text": "How is BLUEHERON going?"}, "secret"),
    ({"by": "praga"}, "member"),           # Praga isn't in Product Planning
    ({"by": "max"}, "member"),             # Max wasn't there yet
    ({"at": "22:30"}, "working hours"),
    ({"wd": -30}, "days"),
    ({"text": "Price is {launch_date}"}, "placeholder"),
    ({"text": "x" * 500}, "long"),
])
def test_rules(world, change, why):
    good, rejected = check_one(world, {**GOOD, **change})
    assert good == [] and why in rejected[0]


def test_good_message_and_replies(world):
    existing = [{"id": "e501", "place": "pp-general", "wd": -16, "at": "12:10", "reply_to": None}]
    items = [{**GOOD, "key": "n1"}, {**GOOD, "key": "n2", "text": "Sure, count me in.", "reply_to": "n1", "at": "10:20"},
             {**GOOD, "key": "n3", "text": "Great place!", "reply_to": "e501"}]
    batch = {"place": "pp-general", "wd_from": -15, "wd_to": -10, "count": 3}
    good, rejected = wm.validate(world, batch, items, existing)
    assert len(good) == 3 and rejected == []


def test_no_threads_in_chats(world):
    good, rejected = check_one(world, {**GOOD, "by": "prince", "key": "n1", "reply_to": "n0"}, place="sync")
    assert good == [] and "thread" in rejected[0]


def fake_answer(prompt: str) -> str:
    """Plays the model: writes valid messages for whatever place and days the prompt asks for."""
    place = prompt.split("PLACE: ")[1].split("\n")[0].split(" ")[0]
    lo, hi = (int(x) for x in prompt.split("DAYS: ")[1].split("\n")[0].split(" to "))
    who = "sven" if place == "pp-general" else "prince"
    n = int(prompt.split("WRITE: ")[1].split(" ")[0])
    return "```json\n" + json.dumps([{"key": f"n{i}", "by": who, "wd": lo + i % (hi - lo + 1), "at": "11:00",
                                       "text": "Thanks, that helps a lot."} for i in range(n)]) + "\n```"


def test_write_all_saves_checked_messages(world, make_llm, tmp_path, monkeypatch):
    llm, backend = make_llm({"main": ["unused"]})
    async def gen(model_, prompt, system, max_tokens, timeout):
        from max.llm import Result
        return Result(fake_answer(prompt), {"in": 1000, "out": 500})
    backend.generate = gen
    out = tmp_path / "generated.yaml"
    report = asyncio.run(wm.write_all(world, llm, out, budget_usd=3.0, spent=lambda: 0.0))
    written = messages.raw(tmp_path)
    assert len(written) == 21 and report["rejected"] == 0
    assert all(m["id"].startswith("g-") for m in written)
    assert messages.problems(world, messages.raw() + written) == []


def test_stops_at_the_budget(world, make_llm, tmp_path):
    llm, _ = make_llm({"main": ["[]"]})
    report = asyncio.run(wm.write_all(world, llm, tmp_path / "g.yaml", budget_usd=1.0, spent=lambda: 1.0))
    assert report["stopped"] and "budget" in report["stopped"]
