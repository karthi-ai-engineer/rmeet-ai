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
                                       "text": next(FAKE_TEXTS)}
                                      for i in range(n)]) + "\n```"


WORDS = ["a lot", "today", "the team", "us", "me", "Sven", "Kenji", "the review", "with slides", "for sure"]
FAKE_TEXTS = (f"Thanks, that helps {a} {b}" for a in WORDS for b in WORDS for _ in [0])  # never the same twice


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
    assert messages.problems(world, messages.raw(skip=("generated.yaml",)) + written) == []


def test_stops_at_the_budget(world, make_llm, tmp_path):
    llm, _ = make_llm({"main": ["[]"]})
    report = asyncio.run(wm.write_all(world, llm, tmp_path / "g.yaml", budget_usd=1.0, spent=lambda: 1.0))
    assert report["stopped"] and "budget" in report["stopped"]


def test_reply_to_a_reply_joins_the_same_thread(world):
    """Teams channels have one level of replies: answering a reply means replying in that thread."""
    items = [{**GOOD, "key": "n1", "at": "10:00"},
             {**GOOD, "key": "n2", "at": "10:05", "text": "Me too.", "reply_to": "n1"},
             {**GOOD, "key": "n3", "at": "10:10", "text": "Same here.", "reply_to": "n2"}]
    batch = {"place": "pp-general", "wd_from": -15, "wd_to": -10, "count": 3}
    good, rejected = wm.validate(world, batch, items, [])
    assert rejected == [] and [g.get("reply_to") for g in good] == [None, "n1", "n1"]


def test_personal_matters_stay_in_their_one_message(world):
    good, rejected = check_one(world, {**GOOD, "text": "How was the recital?"})
    assert good == [] and "personal" in rejected[0]


@pytest.mark.parametrize("text", [
    "I sent Northwind the update this morning.",
    "The GPU decision is approved.",
    "Brightcore confirmed their delivery.",
    "We moved the launch again.",
])
def test_no_status_changes_about_the_storylines(world, text):
    """The planted facts say what happened; filler may talk about the work, never change its status."""
    good, rejected = check_one(world, {**GOOD, "text": text})
    assert good == [] and "status" in rejected[0]


def test_work_talk_is_fine(world):
    good, _ = check_one(world, {**GOOD, "text": "Rachitaa, can you look at the Northwind proposal slides before the sync?"})
    assert len(good) == 1


def test_prompt_lists_the_places_files(world):
    batch = {"place": "pr-suppliers", "wd_from": -15, "wd_to": -10, "count": 5}
    assert "Parts prices.xlsx" in wm.prompt(world, batch, [])


def test_digits_allowed_only_inside_known_names(world):
    ok, _ = check_one(world, {**GOOD, "text": "Can you check the Raptor X9 cooling notes in Launch plan Raptor X9.pptx?"})
    assert len(ok) == 1
    bad, why = check_one(world, {**GOOD, "text": "The Raptor X9 needs 2 more fans"})
    assert bad == [] and "digit" in why[0]


@pytest.mark.parametrize("text", ["The Raptor X nine looks great", "Raptor Xseven claims", "the X-five refresh"])
def test_spelled_out_product_names_are_refused(world, text):
    good, why = check_one(world, {**GOOD, "text": text})
    assert good == [] and "product name" in why[0]


# ---------------------------------------------------------------- review of the full world (27 Nov 2026)

@pytest.mark.parametrize("text, why", [
    ("I'm looking at Thermal test results.pptx now", "before it was uploaded"),   # uploaded at -9, message at -12
    ("Cleaning up Raptor X7 retrospective.pptx", "older than the reading window"),
    ("Board update.pptx needs work", "private file"),                             # private, lives in pp-budget
    ("We need three hundred more units", "number word"),
    ("Ready for the weekend?", "weekend"),
    ("Let's wrap this up by the end of the week", "weekend"),
    ("Max, can you summarise?", "mentions Max"),
    ("I told Northwind about the new timing", "status"),
    ("The suppliers confirmed their quotes.", "status"),
    ("We are going with Arvane for the GPUs.", "status"),
])
def test_review_rules(world, text, why):
    good, rejected = check_one(world, {**GOOD, "text": text})
    assert good == [] and why in rejected[0]


@pytest.mark.parametrize("text", ["Agreed, I'll update the slides.", "Thanks for the update! Sent you the notes.",
                                  "We may need another look at the slides."])
def test_ordinary_work_talk_is_not_refused(world, text):
    good, rejected = check_one(world, {**GOOD, "text": text})
    assert len(good) == 1, rejected


def test_duplicate_keys_are_refused(world):
    items = [{**GOOD, "key": "n1"}, {**GOOD, "key": "n1", "at": "10:30", "text": "Another one."}]
    batch = {"place": "pp-general", "wd_from": -15, "wd_to": -10, "count": 2}
    good, rejected = wm.validate(world, batch, items, [])
    assert len(good) == 1 and "duplicate key" in rejected[0]


def test_the_model_sees_nothing_from_the_future(world):
    existing = messages._expand(world, messages.raw(skip=("generated.yaml",)))
    shown = wm.prompt(world, {"place": "pr-general", "wd_from": -31, "wd_to": -27, "count": 5}, existing)
    assert "floor 6" not in shown                                   # the office move is announced at -8
    assert "Price list draft.xlsx" not in shown                    # uploaded at -3
    later = wm.prompt(world, {"place": "pr-general", "wd_from": -6, "wd_to": -2, "count": 5}, existing)
    assert "floor 6" in later and "Price list draft.xlsx" in later


def test_a_stopped_run_leaves_the_old_file(world, make_llm, tmp_path):
    out = tmp_path / "generated.yaml"
    out.write_text("# old\n[]\n", encoding="utf-8")
    llm, _ = make_llm({"main": ["[]"]})
    report = asyncio.run(wm.write_all(world, llm, out, budget_usd=1.0, spent=lambda: 1.0))
    assert report["stopped"] and out.read_text(encoding="utf-8") == "# old\n[]\n"


def test_near_repeats_are_refused(world):
    existing = [{"id": "g-pp-general-0001", "place": "pp-general", "by": "sven", "wd": -13, "at": "09:00",
                 "text": "Good morning. Comparing the new GPU output!", "reply_to": None}]
    good, rejected = check_one(world, {**GOOD, "text": "good morning, comparing the new gpu output"}, existing=existing)
    assert good == [] and "repeat" in rejected[0]


def test_prompt_says_who_does_what(world):
    shown = wm.prompt(world, {"place": "sync", "wd_from": -6, "wd_to": -2, "count": 5}, [])
    assert "Quality runs the tests" in shown and "contractions" in shown


def test_not_in_data_topics_are_refused(world):
    """'What's the Raptor X9's battery life?' must stay unanswerable (F112)."""
    good, rejected = check_one(world, {**GOOD, "text": "The battery tests look good"})
    assert good == [] and "not in the data" in rejected[0]


# ---------------------------------------------------------------- re-review (27 Nov 2026)

E401 = {"id": "e401", "place": "sa-accounts", "by": "rachitaa", "wd": -17, "at": "11:00", "reply_to": None,
        "text": "Big one: Northwind Systems wants 300 Raptor X9 units for their gaming lounge chain. Order NW-26-0418."}


def accounts(world, item, existing=(E401,)):
    batch = {"place": "sa-accounts", "wd_from": -20, "wd_to": -15, "count": 3}
    return wm.validate(world, batch, [{"by": "omar", "wd": -16, "at": "10:00", **item}], list(existing))


def test_storyline_moments_are_never_copied(world):
    good, why = accounts(world, {"by": "rachitaa", "wd": -17, "at": "11:05", "text": "Quick note on the lounge chain."})
    assert good == [] and "storyline" in why[0]                                  # same author, same moment
    good, why = accounts(world, {"text": "Northwind Systems wants Raptor X9 units for their gaming lounge chain"})
    assert good == [] and "storyline" in why[0]                                  # same words


def test_file_named_before_its_upload_time_on_the_same_day(world):
    batch = {"place": "pr-general", "wd_from": -20, "wd_to": -15, "count": 1}
    early = {"by": "lena", "wd": -18, "at": "08:50", "text": "I've put the numbers into Procurement KPIs.pptx"}
    good, why = wm.validate(world, batch, [early], [])                          # the deck is uploaded at 16:15
    assert good == [] and "before it was uploaded" in why[0]


def test_invented_file_contents_are_refused(world):
    batch = {"place": "pp-models", "wd_from": -6, "wd_to": -2, "count": 1}
    msg = {"by": "prince", "wd": -5, "at": "10:00", "text": "Check the budget figures in Launch plan Raptor X9.pptx"}
    good, why = wm.validate(world, batch, [msg], [])
    assert good == [] and "content" in why[0]


@pytest.mark.parametrize("text, why", [
    ("Northwind got the update yesterday", "status"),
    ("We'll stick with Arvane", "status"),
    ("The launch slipped a couple of weeks", "status"),
    ("Codename talk later", "private"),
    ("The GPU budget looks tight", "private"),
    ("Lisa at Arvane is helpful", "older than the window"),
])
def test_more_gaps(world, text, why):
    good, rejected = check_one(world, {**GOOD, "text": text})
    assert good == [] and why in rejected[0]
