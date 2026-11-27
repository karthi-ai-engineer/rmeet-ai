"""
The world's messages: world/messages/*.yaml, made ready for a given day.

A message either belongs to an event of the fact sheet (it inherits place, author, day, time and thread from it):
    - {event: e101, text: "..."}
or stands on its own (everyday chatter, replies):
    - {id: s001, place: pp-general, by: sven, wd: -12, at: "12:05", text: "...", reply_to: e501}

  load_all(world, clock) -> [{id, event, place, kind, by, at, text, reply_to, original, deleted}, ...] oldest first
  problems(world)        -> what is wrong with the message files ([] = fine)

`original` = the first text of an edited message (the event's `edited: {from, to}`); `deleted` = posted, then deleted.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from world import model
from world.dates import Clock, render

FOLDER = Path(__file__).resolve().parents[1] / "messages"


def raw(folder: Path = FOLDER) -> list[dict]:
    out = []
    for p in sorted(folder.glob("*.yaml")):
        out += yaml.safe_load(p.read_text(encoding="utf-8")) or []
    return out


def _expand(world: dict, items: list[dict]) -> list[dict]:
    events = {e["id"]: e for e in world["events"]}
    out = []
    for m in items:
        e = events.get(m.get("event"), {})
        out.append({
            "id": m.get("id") or m.get("event"),
            "event": m.get("event"),
            "place": m.get("place", e.get("place")),
            "by": m.get("by", e.get("by")),
            "wd": m.get("wd", e.get("wd")),
            "at": m.get("at", e.get("at")),
            "reply_to": m.get("reply_to", e.get("reply_to")),
            "text": m["text"],
            "edited": e.get("edited"),  # {from, to}: the first text had `from` where it now says `to`
            "deleted": bool(e.get("deleted") or m.get("deleted")),
            "_unknown_event": m.get("event") and m.get("event") not in events,
        })
    return out


def problems(world: dict, items: list[dict] | None = None) -> list[str]:
    msgs = _expand(world, raw() if items is None else items)
    out, by_id = [], {}
    for m in msgs:
        what = f"message {m['id']}"
        if m["_unknown_event"]:
            out.append(f"{what}: unknown event")
            continue
        if m["id"] in by_id:
            out.append(f"{what}: duplicate id")
        by_id[m["id"]] = m
        if None in (m["place"], m["by"], m["wd"], m["at"]):
            out.append(f"{what}: place, by, wd and at are needed")
            continue
        kind = model.place_kind(world, m["place"])
        if kind is None:
            out.append(f"{what}: unknown place {m['place']!r}")
        elif m["by"] not in model.members(world, m["place"]):
            out.append(f"{what}: {m['by']} is not a member of {m['place']}")
        if m["reply_to"]:
            root = by_id.get(m["reply_to"])
            if kind == "chat":
                out.append(f"{what}: chats have no reply threads")
            elif root is None or root["place"] != m["place"] or root["reply_to"] or (root["wd"], root["at"]) > (m["wd"], m["at"]):
                out.append(f"{what}: reply_to {m['reply_to']} must be an earlier root post above it in the same place")
    events_written = [m["event"] for m in msgs if m["event"]]
    for e in {x for x in events_written if events_written.count(x) > 1}:
        out.append(f"event {e} has more than one message")
    return out


def load_all(world: dict, clock: Clock, items: list[dict] | None = None) -> list[dict]:
    """Every message with real times for this day, oldest first."""
    msgs = _expand(world, raw() if items is None else items)
    out = []
    for m in msgs:
        text = render(m["text"], clock)
        original = None
        if m["edited"]:
            new, old = render(m["edited"]["to"], clock), render(m["edited"]["from"], clock)
            if new not in text:
                raise ValueError(f"message {m['id']}: edited text {new!r} is not in the message")
            original = text.replace(new, old)
        out.append({"id": m["id"], "event": m["event"], "place": m["place"],
                    "kind": model.place_kind(world, m["place"]), "by": m["by"],
                    "at": clock.at(m["wd"], m["at"]), "text": text, "reply_to": m["reply_to"],
                    "original": original, "deleted": m["deleted"]})
    return sorted(out, key=lambda m: m["at"])
