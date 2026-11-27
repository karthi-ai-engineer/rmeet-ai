"""
The fact sheet (world/facts.yaml): loading it and checking it is consistent before anything is made from it.

  world = load()
  problems(world)      -> list of readable problems ([] = consistent)
  members(world, place) / place_kind(world, place) / data_value(world, "$budget.gpu_budget_first_batch")

The window rule: facts Max must answer live at most 19 working days back (at most 29 calendar days on any weekday);
"older than the window" facts at least 24 back (at least 32 calendar days). Checked for all 7 weekdays.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import yaml

from world.dates import Clock

ROOT = Path(__file__).resolve().parent
FACTS = ROOT / "facts.yaml"
OLD_MARK = "older than the reading window"


def load(path: Path = FACTS) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- places and people

def place_kind(world: dict, place: str) -> str | None:
    if any(c["id"] == place for t in world["teams"] for c in t["channels"]):
        return "channel"
    if any(c["id"] == place for c in world["chats"]):
        return "chat"
    return None


def members(world: dict, place: str) -> set[str]:
    for t in world["teams"]:
        for c in t["channels"]:
            if c["id"] == place:
                return set(c["private"]) if c.get("private") else set(t["members"])
    for c in world["chats"]:
        if c["id"] == place:
            return set(c["members"])
    return set()


def data_value(world: dict, ref: str):
    """'$budget.gpu_budget_first_batch' -> the number in `data` (KeyError if there is none)."""
    node = world["data"]
    for part in ref.lstrip("$").split("."):
        node = node[part]
    return node


def _strings(node):
    """Every string inside a spec (for canary and data checks)."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from _strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v)


# ---------------------------------------------------------------- consistency

def _ages(wd: int) -> list[int]:
    """Calendar age of a working-day offset for every weekday 'today' could be."""
    start = date(2026, 11, 23)  # a Monday
    return [Clock(start + timedelta(days=i)).age_days(wd) for i in range(7)]


def _empty_values(node, path=""):
    """Keys without a value: usually a comma inside {...} that YAML read as a new key (quote such text)."""
    if isinstance(node, dict):
        for k, v in node.items():
            if v is None:
                yield f"{path}/{k}"
            yield from _empty_values(v, f"{path}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _empty_values(v, f"{path}[{i}]")


def problems(world: dict) -> list[str]:
    out: list[str] = [f"empty value at {p} (a comma inside {{...}}? put the text in quotes)" for p in _empty_values(world)]
    people = {p["id"] for p in world["people"]} | {"max"}
    window = world["calendar"]["window_days"]

    def need_place(where: str, who: str, what: str):
        if place_kind(world, where) is None:
            out.append(f"{what}: unknown place {where!r}")
        elif who not in members(world, where):
            out.append(f"{what}: {who} is not a member of {where}")
        if who not in people:
            out.append(f"{what}: unknown person {who!r}")

    for kind in ("people", "events", "facts", "files"):
        ids = [x["id"] for x in world[kind]]
        for dup in {i for i in ids if ids.count(i) > 1}:
            out.append(f"{kind}: duplicate id {dup}")

    events = {e["id"]: e for e in world["events"]}
    for e in world["events"]:
        need_place(e["place"], e["by"], f"event {e['id']}")
        root = e.get("reply_to")
        if root:
            r = events.get(root)
            if r is None or r["place"] != e["place"] or r.get("reply_to") or (r["wd"], r["at"]) > (e["wd"], e["at"]):
                out.append(f"event {e['id']}: reply_to {root} must be an earlier root post in the same place")
        if place_kind(world, e["place"]) == "chat" and root:
            out.append(f"event {e['id']}: chats have no reply threads")

    files = {f["id"]: f for f in world["files"]}
    for f in world["files"]:
        for v in f["versions"]:
            need_place(f["place"], v["by"], f"file {f['id']} v{v['v']}")
        for s in _strings(f.get("spec", {})):
            if s.startswith("$"):
                try:
                    data_value(world, s)
                except (KeyError, TypeError):
                    out.append(f"file {f['id']}: unknown data reference {s}")

    for fact in world["facts"]:
        old = OLD_MARK in fact["a"]
        for loc in fact.get("at", []):
            if "message" in loc:
                continue  # a plain message (not an event): its place and day are checked with the messages
            if "event" in loc:
                e = events.get(loc["event"])
                if e is None:
                    out.append(f"fact {fact['id']}: unknown event {loc['event']}")
                    continue
                wd, what = e["wd"], f"event {e['id']}"
            else:
                f = files.get(loc.get("file"))
                if f is None:
                    out.append(f"fact {fact['id']}: unknown file {loc.get('file')!r}")
                    continue
                ver = next((v for v in f["versions"] if v["v"] == loc.get("v", 1)), None)
                if ver is None:
                    out.append(f"fact {fact['id']}: file {f['id']} has no version {loc.get('v')}")
                    continue
                wd, what = ver["wd"], f"file {f['id']}"
            ages = _ages(wd)
            if old and min(ages) <= window:
                out.append(f"fact {fact['id']}: {what} is not old enough for 'older than the window' (age {min(ages)} days)")
            if not old and max(ages) >= window:
                out.append(f"fact {fact['id']}: {what} is outside the reading window (up to {max(ages)} days old)")
        for p in fact.get("only", []):
            if p not in people:
                out.append(f"fact {fact['id']}: unknown person {p}")

    for c in world["canaries"]:
        for e in world["events"]:
            if e["place"] not in c["only_in"] and any(c["text"] in s for s in _strings([e["gist"], e["must"]])):
                out.append(f"canary {c['text']!r} in event {e['id']} outside {c['only_in']}")
        for f in world["files"]:
            if f["place"] not in c["only_in"] and any(c["text"] in s for s in _strings([f["name"], f.get("spec", {})])):
                out.append(f"canary {c['text']!r} in file {f['id']} outside {c['only_in']}")
    return out
