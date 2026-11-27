"""
Writes the everyday messages of the full world with an AI model (11-sim-world.md Part 3: "numbers by code; the AI
only writes the human text"). The storyline moments are already written (messages/samples.yaml); this fills each
place with the chatter around them: reactions, coordination, questions, thanks, small talk.

  python run.py world-write --plan     show the batches and what they will cost, without calling the model
  python run.py world-write            write world/messages/generated.yaml (stops at [world] generation_budget_usd)

Rules (checked by code, a message that breaks one is dropped; a batch with too few good messages is asked again):
no digits, month or weekday names (dates and numbers live only in the fact sheet), no secret words, authors are
members of the place (Max wasn't there yet), working hours, replies only to earlier root posts, no threads in chats.
Uses Max's provider-neutral AI client: works with any model, cost shows in the usage dashboard.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from pathlib import Path

import yaml

from world import model
from world.check import contains
from world.make import messages

OUT = messages.FOLDER / "generated.yaml"
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December", "Jan", "Feb", "Mar", "Apr", "Jun", "Jul", "Aug", "Sep", "Sept", "Oct", "Nov", "Dec"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
            "Mon", "Tue", "Tues", "Wed", "Thu", "Thur", "Fri", "Sat", "Sun"]
BATCH_DAYS = 5          # one model call per place per working week
GOOD_ENOUGH = 0.6       # below this share of good messages, the batch is asked once more

SYSTEM = ("You write realistic Microsoft Teams messages for a simulated company, for software tests. "
          "Follow the rules exactly. Answer with a JSON array only.")


# ---------------------------------------------------------------- plan

def plan(world: dict) -> list[dict]:
    """Batches of (place, working days, how many messages), covering the whole history of every place."""
    first = -world["calendar"]["history_workdays"] + 1
    weeks = [(lo, min(lo + BATCH_DAYS - 1, 0)) for lo in range(first, 1, BATCH_DAYS)]
    days = 1 - first
    out = []
    for place, total in world["generation"]["per_place"].items():
        shares = [total * (hi - lo + 1) / days for lo, hi in weeks]
        counts = [int(s) for s in shares]
        for i in sorted(range(len(weeks)), key=lambda i: shares[i] - counts[i], reverse=True)[:total - sum(counts)]:
            counts[i] += 1  # hand out what rounding left over, so the place gets exactly `total`
        out += [{"place": place, "wd_from": lo, "wd_to": hi, "count": c} for (lo, hi), c in zip(weeks, counts) if c]
    return out


# ---------------------------------------------------------------- prompt

def _place_line(world: dict, place: str) -> str:
    for t in world["teams"]:
        for c in t["channels"]:
            if c["id"] == place:
                private = " (private channel)" if c.get("private") else ""
                return f'{place} (channel "{c["name"]}" in the department "{t["name"]}"{private})'
    chat = next(c for c in world["chats"] if c["id"] == place)
    return f'{place} ({"group chat " + repr(chat.get("title")) if chat["kind"] == "group" else "1:1 chat"})'


def prompt(world: dict, batch: dict, existing: list[dict]) -> str:
    place = batch["place"]
    people = {p["id"]: p for p in world["people"]}
    members = [m for m in sorted(model.members(world, place)) if m in people]
    is_chat = model.place_kind(world, place) == "chat"
    stories = [s["title"] for s in world["storylines"] if place in s["where"]]
    here = [m for m in existing if m["place"] == place]
    shown = "\n".join(f'- [{m["id"]}] day {m["wd"]} {m["at"]} {people[m["by"]]["name"]}: "{m["text"]}"'
                      + (" (reply)" if m.get("reply_to") else "") for m in here[-40:]) or "- (nothing yet)"
    secrets = sorted({c["text"] for c in world["canaries"]})
    return f"""COMPANY: {world["company"]["name"]}, {world["company"]["what"]}. Invented company, invented people.
PLACE: {_place_line(world, place)}
MEMBERS (use the id in "by"): {"; ".join(f'{m} = {people[m]["name"]}, {people[m]["dept"]}, {people[m]["role"]}' for m in members)}
DAYS: {batch["wd_from"]} to {batch["wd_to"]}
(working-day offsets: 0 = today, -1 = the working day before)
WRITE: {batch["count"]} messages
TOPICS HERE: {", ".join(stories) or "the department's daily work"}, plus everyday office life.

ALREADY WRITTEN IN THIS PLACE (don't repeat or contradict; you may react to them):
{shown}

RULES
- English, short Teams style, friendly and professional. Vary the length. Some messages may use one emoji.
- NO digits at all. NO month or weekday names. No dates, prices, quantities, percentages or times in the text.
- Don't announce decisions or new facts about products, prices, suppliers, customers, the launch or budgets.
  React, coordinate, ask, confirm, thank, small talk.
- Never mention: {", ".join(secrets)}. Nothing about private life beyond light small talk.
- "at" is a time between 08:30 and 18:45. "wd" is a day from {batch["wd_from"]} to {batch["wd_to"]}.
- {"This is a chat: reply_to is always null." if is_chat else 'reply_to: null for a new post, or the key / [id] of an EARLIER new post (not a reply) in this channel.'}

Answer with a JSON array only, each item:
{{"key": "n1", "by": "<member id>", "wd": <day>, "at": "HH:MM", "text": "...", "reply_to": null}}"""


# ---------------------------------------------------------------- checking the answer

def parse(text: str) -> list[dict]:
    m = re.search(r"\[.*\]", text, flags=re.DOTALL)
    try:
        items = json.loads(m.group(0)) if m else []
    except ValueError:
        return []
    return [i for i in items if isinstance(i, dict)]


def validate(world: dict, batch: dict, items: list[dict], existing: list[dict]) -> tuple[list[dict], list[str]]:
    """The messages that keep every rule (in time order), and why the others were dropped."""
    place = batch["place"]
    members = model.members(world, place) - {"max"}
    is_chat = model.place_kind(world, place) == "chat"
    roots = {m["id"]: m for m in existing if m["place"] == place and not m.get("reply_to")}
    secrets = [c["text"] for c in world["canaries"]] + ["BLUEHERON"]
    good, rejected = [], []

    def why_not(it) -> str | None:
        text = str(it.get("text") or "")
        if it.get("by") not in members:
            return f"{it.get('by')!r} is not a member of {place}"
        if not isinstance(it.get("wd"), int) or not batch["wd_from"] <= it["wd"] <= batch["wd_to"]:
            return f"days must be {batch['wd_from']}..{batch['wd_to']}"
        if not re.fullmatch(r"\d\d:\d\d", str(it.get("at"))) or not "08:30" <= it["at"] <= "18:45":
            return "outside working hours"
        if not 2 <= len(text) <= 400:
            return "too short or too long"
        if re.search(r"\d", text):
            return "has a digit"
        if any(contains(text, w) for w in MONTHS):
            return "has a month name"
        if any(contains(text, w) for w in WEEKDAYS):
            return "has a weekday name"
        if "{" in text or "}" in text:
            return "has a placeholder"
        if any(contains(text, s) for s in secrets):
            return "mentions a secret word"
        if it.get("reply_to"):
            if is_chat:
                return "chats have no threads"
            root = roots.get(it["reply_to"])
            if root is None or (root["wd"], root["at"]) > (it["wd"], it["at"]):
                return f"reply_to {it['reply_to']!r} is not an earlier post here"
        return None

    for it in sorted(items, key=lambda i: (i.get("wd") if isinstance(i.get("wd"), int) else 99, str(i.get("at")))):
        reason = why_not(it)
        if reason:
            rejected.append(f"{reason}: {str(it.get('text'))[:60]!r}")
            continue
        good.append(it)
        if not it.get("reply_to"):
            roots[it.get("key") or f"_{len(good)}"] = {**it, "id": it.get("key")}
    return good, rejected


# ---------------------------------------------------------------- writing

def _existing(world: dict, written: list[dict]) -> list[dict]:
    """The samples and what was written so far, as plain dicts with place, day and time."""
    return messages._expand(world, messages.raw() + written)


async def write_all(world: dict, llm, out: Path, *, budget_usd: float, spent) -> dict:
    """Writes every batch (saving after each), stops at the budget. `spent()` = USD this run has cost so far."""
    written: list[dict] = []
    numbers: dict[str, int] = {}
    report = {"written": 0, "rejected": 0, "batches": 0, "stopped": None, "examples_rejected": []}
    for batch in plan(world):
        if spent() >= budget_usd:
            report["stopped"] = f"budget reached (${spent():.2f} of ${budget_usd:.2f}); run again to continue"
            break
        existing = _existing(world, written)
        good: list[dict] = []
        for attempt in (1, 2):
            reply = await llm.ask(prompt(world, batch, existing), system=SYSTEM, kind="world")
            good, rejected = validate(world, batch, parse(reply.text), existing)
            report["rejected"] += len(rejected)
            report["examples_rejected"] += rejected[:2]
            if len(good) >= GOOD_ENOUGH * batch["count"]:
                break
        keys = {}
        for it in good:
            numbers[batch["place"]] = numbers.get(batch["place"], 0) + 1
            mid = f"g-{batch['place']}-{numbers[batch['place']]:04d}"
            keys[it.get("key")] = mid
            msg = {"id": mid, "place": batch["place"], "by": it["by"], "wd": it["wd"], "at": it["at"], "text": it["text"]}
            if it.get("reply_to"):
                msg["reply_to"] = keys.get(it["reply_to"], it["reply_to"])
            written.append(msg)
        report["written"] = len(written)
        report["batches"] += 1
        _save(out, written)
    return report


def _save(out: Path, written: list[dict]) -> None:
    items = sorted(written, key=lambda m: (m["place"], m["wd"], m["at"]))
    header = ("# Everyday messages of the full world, written by an AI model and checked by code "
              "(world/make/write_messages.py).\n# Don't edit by hand: write again with `python run.py world-write`.\n")
    out.write_text(header + yaml.safe_dump(items, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")


def main() -> None:
    from max.config import ConfigError, load_settings
    from max.llm import LLM

    world = model.load()
    batches = plan(world)
    total = sum(b["count"] for b in batches)
    print(f"{len(batches)} batches, {total} messages to write")
    if "--plan" in sys.argv:
        for b in batches:
            print(f"  {b['place']:16} days {b['wd_from']:>3} to {b['wd_to']:>3}: {b['count']}")
        return
    try:
        settings = load_settings()
    except ConfigError as e:
        sys.exit(str(e))
    llm = LLM.from_settings(settings, source="world")
    budget = llm.meter.limits_store.get().world.generation_budget_usd
    start = time.time()

    def spent() -> float:
        return sum(e.get("cost") or 0 for e in llm.meter.read_events() if e.get("source") == "world" and e["ts"] >= start)

    report = asyncio.run(write_all(world, llm, OUT, budget_usd=budget, spent=spent))
    print(f"written {report['written']} messages in {report['batches']} batches, dropped {report['rejected']}, "
          f"cost ${spent():.3f}" + (f"; STOPPED: {report['stopped']}" if report["stopped"] else ""))
    for r in report["examples_rejected"][:8]:
        print("  dropped:", r)
    problems = messages.problems(world)
    print("message files:", "OK" if not problems else f"{len(problems)} problems")
    for p in problems[:20]:
        print("  PROBLEM", p)


if __name__ == "__main__":
    main()
