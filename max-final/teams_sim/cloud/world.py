"""
Loads Thirdwave's world (world/) into the simulated Teams: people, departments, channels, chats, 45 days of
history and the channel files, with dates sliding so the history ends today (Tokyo).

  fill(conn)     called by store.connect() / store.reset() inside their transaction

TEAMS_SIM_TODAY=2026-11-27 pins the day (tests, reproducing a problem). Files are made once per day and fact-sheet
version into WORLD_CACHE_DIR (default data/world_cache/); the same day always gives the same files.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from teams_sim.cloud import store
from world import model
from world.dates import TOKYO, Clock
from world.make import files, messages

ROOT = Path(__file__).resolve().parents[2]


def today() -> date:
    pinned = os.environ.get("TEAMS_SIM_TODAY")
    return date.fromisoformat(pinned) if pinned else datetime.now(TOKYO).date()


def already_happened(items: list[dict], now: datetime | None) -> list[dict]:
    """Only what has happened by `now` (UTC): this morning's 09:10 message isn't there at 08:00. None = everything."""
    if now is None:
        return items
    cutoff = now.astimezone(timezone.utc).replace(tzinfo=None).isoformat(timespec="milliseconds") + "Z"
    return [m for m in items if m["at"] <= cutoff]


def _now() -> datetime | None:
    """The real time; a pinned day (TEAMS_SIM_TODAY) shows its whole history."""
    return None if os.environ.get("TEAMS_SIM_TODAY") else datetime.now(timezone.utc)


def version() -> str:
    """Changes whenever anything in world/ changes (fact sheet, messages, any of its code): then the simulated
    Teams is rebuilt and its files are made again."""
    h = hashlib.sha256()
    folder = model.FACTS.parent
    for p in sorted([*folder.rglob("*.yaml"), *folder.rglob("*.py")]):
        h.update(p.relative_to(folder).as_posix().encode() + p.read_bytes())
    return h.hexdigest()[:10]


KEEP_CACHE_DAYS = 14


def _clean_old(base: Path, today_: date) -> None:
    """Remove made files of days long gone (a database made on such a day is rebuilt on reset anyway)."""
    for d in base.glob("????-??-??-*"):
        try:
            if (today_ - date.fromisoformat(d.name[:10])).days > KEEP_CACHE_DAYS:
                shutil.rmtree(d, ignore_errors=True)
        except ValueError:
            pass


def made_files(world: dict, clock: Clock) -> list[dict]:
    base = Path(os.environ.get("WORLD_CACHE_DIR") or ROOT / "data" / "world_cache")
    folder = base / f"{clock.today.isoformat()}-{version()}"
    index = folder / "made.json"
    if index.exists():
        made = json.loads(index.read_text(encoding="utf-8"))
        for m in made:
            m["path"] = folder / m["path"]
        if all(m["path"].exists() for m in made):
            return made
    if not os.environ.get("TEAMS_SIM_TODAY"):  # a pinned day (tests) never removes the live simulator's files
        _clean_old(base, clock.today)
    made = files.make_all(world, clock, folder)
    index.write_text(json.dumps([{**m, "path": str(m["path"].relative_to(folder))} for m in made], indent=1),
                     encoding="utf-8")
    return made


def fill(conn) -> None:
    world = model.load()
    clock = Clock(today())
    store.set_meta(conn, "world_version", version())
    playable = [p for p in world["people"] if p.get("playable")]
    for pos, p in enumerate(world["people"]):
        store.add_person(conn, p["id"], p["name"], p["role"], playable=bool(p.get("playable")), pos=pos)
    store.add_person(conn, "max", "Max", "AI teammate", playable=False, is_bot=True, pos=99)
    for pos, t in enumerate(world["teams"]):
        store.add_team(conn, t["id"], t["name"], pos, [*t["members"], "max"])  # Max is installed in every department
        for cpos, c in enumerate(t["channels"]):
            store.add_channel(conn, c["id"], t["id"], c["name"], cpos, c.get("private"))
    for p in playable:  # everyone's 1:1 chat with Max starts empty: Max arrives today
        store.add_chat(conn, f"max-{p['id']}", "max", None, [p["id"], "max"])
    for c in world["chats"]:
        store.add_chat(conn, c["id"], c["kind"], c.get("title"), c["members"])

    ids: dict[str, str] = {}
    for m in already_happened(messages.load_all(world, clock), _now()):
        edited_at = None
        if m["original"]:  # edited a few minutes after posting; only the new text is kept (like Teams shows it)
            edited_at = (datetime.fromisoformat(m["at"].rstrip("Z")) + timedelta(minutes=3)).isoformat(
                timespec="milliseconds") + "Z"
        ids[m["id"]] = store.add_history(conn, kind=m["kind"], where=m["place"], author=m["by"], text=m["text"],
                                         created_at=m["at"], thread_id=ids.get(m["reply_to"]) if m["reply_to"] else None,
                                         edited_at=edited_at, deleted=m["deleted"])

    for f in already_happened(made_files(world, clock), _now()):
        store.add_file_version(conn, f["file"], f["place"], f["name"], f["v"], str(f["path"]), f["by"], f["at"],
                               Path(f["path"]).stat().st_size)
