"""
Writes the everyday messages of the full world with an AI model (11-sim-world.md Part 3: "numbers by code; the AI
only writes the human text"). The storyline moments are already written (messages/samples.yaml); this fills each
place with the chatter around them: work in progress, questions, coordination, thanks, small talk.

  python run.py world-write --plan     show the batches, without calling the model
  python run.py world-write            write world/messages/generated.yaml (one run stops at [world]
                                       generation_budget_usd; the old file is replaced only when a run completes)

Each batch (one place, one working week) sees only what exists by then: the events and messages up to that week
and the files already uploaded (with a one-line summary). Rules checked by code; a message that breaks one is
dropped, and a batch with too few good messages is asked again (the better answer is kept):
- no digits except inside product and file names; no number words; no month, weekday or weekend words
- no secret words, no private file names outside their channel, no personal matters, no mentions of Max
- no file named before it was uploaded, and none older than the reading window
- no status changes about a storyline ("sent Northwind the update", "we're going with Arvane"): the fact sheet says
  what happened, the chatter only talks about work in progress
- authors are members of the place, working hours, replies only to earlier posts, no threads in chats
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
MONTHS_ANY_CASE = ["January", "February", "March", "April", "June", "July", "August", "September", "October",
                   "November", "December", "Jan", "Feb", "Mar", "Apr", "Jun", "Jul", "Aug", "Sep", "Sept", "Oct",
                   "Nov", "Dec"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "weekend",
            "Mon", "Tue", "Tues", "Wed", "Thu", "Thur", "Fri", "Sat", "Sun"]
NUMBER_WORDS = r"two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty|hundred|thousand|million|percent|dozen"
STORY_NOUNS = (r"northwind|launch(es)?|price lists?|prices?|gpus?|brightcore|arvane|meridian|budgets?|quotes?|quotations?|"
               r"orders?|raptor|suppliers?|decisions?|samples?|deliver(y|ies)|tests?|results|date|timeline")
STATUS_VERBS = (r"sent|send it|decided|approved|confirmed|delivered|moved|postponed|cancel+ed|signed|agreed|"
                r"finali[sz]ed|launched|chose|picked|went out|uploaded|shared|received|arrived|told|informed|"
                r"emailed|passed|completed|is done|are done|going with|gave us|came back|landed|got|finished|"
                r"is in|are in|stick(ing)? with|slipped|let \w+ know")
PRIVATE_HINTS = ["codename", "code name", "GPU budget"]   # hint that private things exist: only in private channels
CONTENT_WORDS = ["budget", "budgets", "cost", "costs", "spec", "specs", "lead time", "lead times", "price", "prices"]
STORY_COPY_MINUTES = 30   # same author this close to a storyline message = a copy of it
STORY_COPY_OVERLAP = 0.5  # or at least half of its words are a storyline message's words
PRODUCTS = ["Raptor X9", "Raptor X7", "Raptor X5", "Slate 14"]
SPELLED_PRODUCT = r"x[- ]?(nine|seven|five)"   # "Raptor X nine": written to dodge the digit rule
BATCH_DAYS = 5          # one model call per place per working week
GOOD_ENOUGH = 0.6       # below this share of good messages, the batch is asked once more
CONTEXT = 30            # earlier messages of the place shown to the model (besides the storyline moments)
WHO_DOES_WHAT = ("Procurement buys parts, compares suppliers' quotes, prices and delivery dates (it doesn't test hardware). "
                 "Quality runs the tests (thermal, noise). Production plans and builds. Product Planning owns the plan, "
                 "dates and prices. Sales talks to customers. Finance handles budgets and spending. Marketing does the "
                 "campaign. IT looks after systems.")

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


# ---------------------------------------------------------------- files: when they exist, what they are

def first_day(f: dict) -> int:
    return min(v["wd"] for v in f["versions"])


def first_upload(f: dict) -> tuple[int, str]:
    """(working day, time) of a file's first version."""
    return min((v["wd"], v["at"]) for v in f["versions"])


def file_words(f: dict) -> str:
    """Everything a file says (from its spec) plus its name: to tell real contents from invented ones."""
    return " ".join([f["name"], *model._strings(f.get("spec", {}))])


def old_only_words(world: dict) -> list[str]:
    """Answers of the 'older than the window' facts (and the names in them): chatter must not bring them back."""
    out = []
    for fact in world["facts"]:
        if model.OLD_MARK in fact["a"]:
            for loc in fact.get("at", []):
                says = str(loc.get("says", ""))
                if says:
                    out.append(says)
                    if all(w[:1].isupper() and w.isalpha() for w in says.split()):  # a name: each part counts
                        out += says.split()
    return out


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 3}


def is_old(f: dict) -> bool:
    """Uploaded before the reading window: chatter must not bring it back into view (its facts are 'too old')."""
    return first_day(f) <= -24


def summary(f: dict) -> str:
    """One line about what a file is, from its content spec (so the model doesn't invent its contents)."""
    spec = f.get("spec", {})
    if "sheets" in spec:
        return "spreadsheet; sheets: " + ", ".join(s["name"] for s in spec["sheets"])
    if "slides" in spec:
        return "slides: " + "; ".join(s["title"] for s in spec["slides"])
    if "blocks" in spec:
        heads = [b.get("h1") for b in spec["blocks"] if b.get("h1")]
        return "document: " + (heads[0] if heads else "text")
    if "pdf" in spec:
        return f"PDF ({spec['pdf']}): {spec.get('title') or 'scanned paper document'}"
    if "image" in spec:
        return f"picture ({spec['image']})"
    return "file"


# ---------------------------------------------------------------- prompt

def _place_line(world: dict, place: str) -> str:
    for t in world["teams"]:
        for c in t["channels"]:
            if c["id"] == place:
                private = " (private channel)" if c.get("private") else ""
                return f'{place} (channel "{c["name"]}" in the department "{t["name"]}"{private})'
    chat = next(c for c in world["chats"] if c["id"] == place)
    return f'{place} ({"group chat " + repr(chat.get("title")) if chat["kind"] == "group" else "1:1 chat"})'


def context(existing: list[dict], batch: dict) -> list[dict]:
    """What the model may see: this place's storyline moments up to this week, and its latest earlier chatter.
    Never anything from the future."""
    here = sorted([m for m in existing if m["place"] == batch["place"] and m["wd"] is not None
                   and m["wd"] <= batch["wd_to"]], key=lambda m: (m["wd"], m["at"]))
    story = [m for m in here if not str(m["id"]).startswith("g-")]
    chatter = [m for m in here if str(m["id"]).startswith("g-")][-CONTEXT:]
    return sorted(story + chatter, key=lambda m: (m["wd"], m["at"]))


def prompt(world: dict, batch: dict, existing: list[dict]) -> str:
    place = batch["place"]
    people = {p["id"]: p for p in world["people"]}
    members = [m for m in sorted(model.members(world, place)) if m in people]
    is_chat = model.place_kind(world, place) == "chat"
    stories = [s["title"] for s in world["storylines"] if place in s["where"]]
    shown = "\n".join(f'- [{m["id"]}] day {m["wd"]} {m["at"]} {people[m["by"]]["name"]}: "{m["text"]}"'
                      + (" (reply)" if m.get("reply_to") else "") for m in context(existing, batch)) or "- (nothing yet)"
    secrets = sorted({c["text"] for c in world["canaries"]}) + personal_words(world)
    files_here = [f for f in world["files"] if f["place"] == place and first_day(f) <= batch["wd_to"] and not is_old(f)]
    files_line = "\n".join(f'- {f["name"]} (uploaded day {first_day(f)}): {summary(f)}' for f in files_here) or "- none yet"
    first_names = sorted({people[m]["name"].split()[0] for m in members})
    return f"""COMPANY: {world["company"]["name"]}, {world["company"]["what"]}. Invented company, invented people.
PLACE: {_place_line(world, place)}
MEMBERS (use the id in "by"; each person only does their own job):
{chr(10).join(f'- {m} = {people[m]["name"]}, {people[m]["dept"]}, {people[m]["role"]}' for m in members)}
DAYS: {batch["wd_from"]} to {batch["wd_to"]}
(working-day offsets: 0 = today, -1 = the working day before)
WRITE: {batch["count"]} messages
TOPICS HERE: {", ".join(stories) or "the department's daily work"}, plus everyday office life.
FILES THAT EXIST IN THIS PLACE BY THEN (refer to them by name only, never describe or change their content):
{files_line}
WHO DOES WHAT: {WHO_DOES_WHAT}
PRODUCTS: Raptor X9 (the new gaming desktop being launched), Raptor X7 (the model it replaces). Mention other
products rarely. CUSTOMER: Northwind Systems (big order in Sales). All people above are colleagues, not suppliers.

WHAT HAPPENED HERE SO FAR (don't repeat or contradict; you may react to it; nothing later is known yet):
{shown}

RULES
- Sound like real colleagues at a PC maker talking about their actual work: concrete and specific. Mention
  colleagues by first name ({", ".join(first_names)}), the files above, meetings, reviews, slides. English, short
  Teams style, friendly and professional, varied length, rare emoji. Use contractions like real chat
  ("I'm", "we're", "don't", "let's"), not "I am". Don't start every message with a greeting.
- No empty corporate phrases ("great energy", "push through", "ensure consistency across streams", "circle back",
  "synergy"). At most one "good morning" per day in this place.
- Never say something was sent, decided, approved, confirmed, delivered, moved, signed, chosen, uploaded, received,
  passed, completed or cancelled: talk about work in progress (asking, checking, preparing, reviewing).
- Write product names and file names exactly as given (their digits are fine: "Raptor X9").
  NO other digits and no number words. NO month, weekday or weekend words. No dates, prices, quantities or times.
- Never mention: {", ".join(secrets + [w for f in world["facts"] for w in f.get("absent", [])])}, or Max. Nothing about private life beyond light small talk.
- "at" is a time between 08:30 and 18:45. "wd" is a day from {batch["wd_from"]} to {batch["wd_to"]}.
- {"This is a chat: reply_to is always null." if is_chat else 'reply_to: null for a new post, or the key / [id] of an EARLIER new post (not a reply) in this channel.'}
- Every "key" is unique (n1, n2, ...).

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


def _without(names: list[str], text: str) -> str:
    """The text with known names (products, files) taken out: their digits are allowed."""
    for n in sorted(names, key=len, reverse=True):
        text = re.sub(re.escape(n), " ", text, flags=re.IGNORECASE)
    return text


def _word(alternatives: str, text: str) -> bool:
    """One of the |-separated words, as a whole word (any letter case)."""
    return re.search(r"(?<![a-z])(" + alternatives + r")(?![a-z])", text, re.IGNORECASE) is not None


def personal_words(world: dict) -> list[str]:
    """Words of the personal messages (work-only memory test): they stay in their one message."""
    events = {e["id"]: e for e in world["events"]}
    words = [p for eid in world.get("personal", []) for p in events[eid]["must"]]
    return words + [w for p in words for w in p.split() if len(w) > 5]  # "piano recital" -> also "recital"


def _plain(text: str) -> str:
    """For spotting repeats: lower case, letters and spaces only."""
    return " ".join(re.sub(r"[^a-z ]", " ", text.lower()).split())


def _mentions(name: str, text: str) -> bool:
    stem = name.rsplit(".", 1)[0]
    return contains(text, name) or contains(text, stem)


def validate(world: dict, batch: dict, items: list[dict], existing: list[dict]) -> tuple[list[dict], list[str]]:
    """The messages that keep every rule (in time order), and why the others were dropped."""
    place = batch["place"]
    members = model.members(world, place) - {"max"}
    is_chat = model.place_kind(world, place) == "chat"
    roots = {m["id"]: m for m in existing if m["place"] == place and not m.get("reply_to")}
    thread_of = {m["id"]: m["reply_to"] for m in existing if m["place"] == place and m.get("reply_to")}
    secrets = [c["text"] for c in world["canaries"]] + ["BLUEHERON"]
    personal = personal_words(world)
    absent = [w for f in world["facts"] for w in f.get("absent", [])]
    names = PRODUCTS + [f["name"] for f in world["files"]] + [f["name"].rsplit(".", 1)[0] for f in world["files"]]
    keys_seen: set[str] = set()
    said = {_plain(m["text"]) for m in existing if m["place"] == place and m.get("text")}
    story = [m for m in existing if m["place"] == place and m.get("text") and not str(m["id"]).startswith("g-")]
    private_place = any(c["id"] == place and c.get("private") for t in world["teams"] for c in t["channels"])
    old_words = old_only_words(world)

    def why_not(it) -> str | None:
        text = str(it.get("text") or "")
        if it.get("key") in keys_seen:
            return "duplicate key"
        if _plain(text) in said:
            return "repeats an earlier message in this place"
        for s in story:  # the storyline moments are already posted: never again in other words
            close = s["by"] == it.get("by") and s["wd"] == it.get("wd") and \
                abs(_minutes(s["at"]) - _minutes(str(it.get("at")))) <= STORY_COPY_MINUTES
            mine, theirs = _content_words(text), _content_words(s["text"])
            if close or (len(mine) >= 4 and len(mine & theirs) / len(mine) >= STORY_COPY_OVERLAP):
                return f"copies a storyline message ({s['id']})"
        if it.get("by") not in members:
            return f"{it.get('by')!r} is not a member of {place}"
        if not isinstance(it.get("wd"), int) or not batch["wd_from"] <= it["wd"] <= batch["wd_to"]:
            return f"days must be {batch['wd_from']}..{batch['wd_to']}"
        if not re.fullmatch(r"\d\d:\d\d", str(it.get("at"))) or not "08:30" <= it["at"] <= "18:45":
            return "outside working hours"
        if not 2 <= len(text) <= 400:
            return "too short or too long"
        if _word(SPELLED_PRODUCT, text):
            return "spells out a product name (write it exactly, e.g. Raptor X9)"
        rest = _without(names, text)
        if re.search(r"\d", rest):
            return "has a digit"
        if _word(NUMBER_WORDS, rest):
            return "has a number word"
        if re.search(r"(?<![A-Za-z])May(?![a-z])", text) or any(contains(text, w) for w in MONTHS_ANY_CASE):
            return "has a month name"
        if any(contains(text, w) for w in WEEKDAYS) or re.search(r"end of (the )?week", text, re.I):
            return "has a weekday or weekend word"
        if "{" in text or "}" in text:
            return "has a placeholder"
        if any(contains(text, s) for s in secrets):
            return "mentions a secret word"
        if any(contains(text, w) for w in personal):
            return "repeats a personal matter"
        if any(contains(text, w) for w in absent):
            return "mentions a topic that must stay not in the data"
        if contains(text, "Max"):
            return "mentions Max (Max wasn't there yet)"
        if not private_place and any(contains(text, h) for h in PRIVATE_HINTS):
            return "hints at private matters outside the private channel"
        if any(contains(text, w) for w in old_words):
            return "brings back something older than the window"
        for f in world["files"]:
            if _mentions(f["name"], text):
                if f.get("private") and f["place"] != place:
                    return f"names a private file outside its channel ({f['name']})"
                if first_upload(f) > (it["wd"], str(it["at"])):
                    return f"names {f['name']} before it was uploaded (day {first_day(f)})"
                if is_old(f):
                    return f"names {f['name']}, which is older than the reading window"
                invented = [w for w in CONTENT_WORDS if contains(text, w) and not contains(file_words(f), w)]
                if invented:
                    return f"invents content for {f['name']} ({invented[0]})"
        if _word(STORY_NOUNS, text) and _word(STATUS_VERBS, text):
            return "states a status change about a storyline (the fact sheet says what happened)"
        if it.get("reply_to"):
            if is_chat:
                return "chats have no threads"
            it["reply_to"] = thread_of.get(it["reply_to"], it["reply_to"])  # a reply to a reply: same thread
            root = roots.get(it["reply_to"])
            if root is None or (root["wd"], root["at"]) > (it["wd"], it["at"]):
                return f"reply_to {it['reply_to']!r} is not an earlier post here"
        return None

    good, rejected = [], []
    for it in sorted(items, key=lambda i: (i.get("wd") if isinstance(i.get("wd"), int) else 99, str(i.get("at")))):
        reason = why_not(it)
        if reason:
            rejected.append(f"{reason}: {str(it.get('text'))[:60]!r}")
            continue
        good.append(it)
        said.add(_plain(str(it.get("text") or "")))
        if it.get("key"):
            keys_seen.add(it["key"])
        if not it.get("reply_to"):
            roots[it.get("key") or f"_{len(good)}"] = {**it, "id": it.get("key")}
        elif it.get("key"):
            thread_of[it["key"]] = it["reply_to"]
    return good, rejected


# ---------------------------------------------------------------- writing

def _existing(world: dict, written: list[dict], out: Path) -> list[dict]:
    """The other message files and what this run wrote so far (never the old copy of the file being rewritten)."""
    return messages._expand(world, messages.raw(messages.FOLDER, skip=(out.name,)) + written)


async def write_all(world: dict, llm, out: Path, *, budget_usd: float, spent) -> dict:
    """Writes every batch into a temporary file and replaces `out` only when the run completes (a stopped run
    leaves the old file as it was). `spent()` = USD this run has cost so far."""
    written: list[dict] = []
    numbers: dict[str, int] = {}
    partial = out.with_suffix(".partial")  # not *.yaml: never loaded as messages
    report = {"written": 0, "rejected": 0, "batches": 0, "stopped": None, "examples_rejected": []}
    for batch in plan(world):
        if spent() >= budget_usd:
            report["stopped"] = (f"budget reached (${spent():.2f} of ${budget_usd:.2f}); {out.name} was not changed. "
                                 "Raise [world] generation_budget_usd and run again.")
            return report
        existing = _existing(world, written, out)
        good: list[dict] = []
        for attempt in (1, 2):
            reply = await llm.ask(prompt(world, batch, existing), system=SYSTEM, kind="world")
            ok, rejected = validate(world, batch, parse(reply.text), existing)
            report["rejected"] += len(rejected)
            report["examples_rejected"] += rejected[:2]
            if len(ok) > len(good):
                good = ok  # keep the better answer
            if len(good) >= GOOD_ENOUGH * batch["count"] or spent() >= budget_usd:
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
        _save(partial, written)
    if written:
        partial.replace(out)
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
