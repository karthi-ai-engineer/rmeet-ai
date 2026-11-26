"""
AI usage meter. Every AI call in the project goes through here, whichever provider is used.

  meter = Meter()                 one usage folder for the whole project (budgets are per account, not per program)
  meter.check(model, source)      before a call: raises Blocked if paused or over a daily limit
  meter.record(model, kind, ...)  after a call: one JSON line in usage-YYYY-MM-DD-p<pid>.jsonl
  meter.read_events(day)          the logged calls (all days, or one 'YYYY-MM-DD')

Each process writes its own file, because appends from several processes to one file lose lines
on Windows. Readers merge all files of a day.
Limits come from the one limits file (limits.toml + data/limits.toml, see limits.py): ai.daily_budget_usd and
ai.daily_requests (0 = no limit). Pause switch: the file `paused` in the usage folder.
Folder: AI_USAGE_DIR if set, else <repo>/data/ai_usage (the old data/gemini_cost folder is moved there once).
This module must not import max/ or teams_sim/: both use it.
"""

from __future__ import annotations

import json
import logging
import math
import os
import shutil
import threading
import time
from pathlib import Path

from limits import LimitsStore, default_user_file

from . import prices

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DIR = REPO / "data" / "ai_usage"
OLD_DIR = REPO / "data" / "gemini_cost"          # Step 0 name, moved once


class Blocked(Exception):
    """The meter refused an AI call (paused, or a daily limit reached)."""


def day_of(ts: float | None = None) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def _move_old_folder(old: Path, new: Path, user_limits: Path) -> None:
    """One-time move of Step 0's data/gemini_cost (usage logs + daily cap) to the new names."""
    if new.exists() or not old.exists():
        return
    try:
        old.rename(new)
    except OSError:
        # Windows: a file inside may be in use. Move what we can, one file at a time, and say so.
        new.mkdir(parents=True, exist_ok=True)
        stuck = []
        for f in old.iterdir():
            try:
                shutil.move(str(f), str(new / f.name))
            except OSError:
                stuck.append(f.name)
        if stuck:
            logging.getLogger("ai_usage").warning("could not move %s from %s; move them by hand", ", ".join(stuck), old)
    legacy = new / "limits.json"
    if legacy.exists() and not user_limits.exists():
        try:
            saved = json.loads(legacy.read_text(encoding="utf-8"))
            ai = {}
            if "daily_usd" in saved:
                ai["daily_budget_usd"] = float(saved["daily_usd"])
            if "daily_requests" in saved:
                ai["daily_requests"] = int(saved["daily_requests"])
            if ai:
                LimitsStore(user_file=user_limits).update({"ai": ai})
        except (OSError, ValueError, TypeError):
            pass


class Meter:
    def __init__(self, data_dir: Path | str | None = None, limits: LimitsStore | None = None):
        env_dir = os.environ.get("AI_USAGE_DIR")
        self.dir = Path(data_dir or env_dir or DEFAULT_DIR)
        # the ONE limits file (data/limits.toml or LIMITS_FILE), whatever the usage folder is
        self.limits_store = limits or LimitsStore()
        if not (data_dir or env_dir):
            _move_old_folder(OLD_DIR, DEFAULT_DIR, default_user_file())
        self._lock = threading.Lock()

    # ---------------------------------------------------------------- settings
    def limits(self) -> dict:
        """The two daily limits the meter enforces (from the limits file)."""
        ai = self.limits_store.get().ai
        return {"daily_usd": float(ai.daily_budget_usd), "daily_requests": float(ai.daily_requests)}

    def set_limits(self, **values: float) -> dict:
        """Change the daily limits (dashboard). Raises ValueError for bad values."""
        names = {"daily_usd": "daily_budget_usd", "daily_requests": "daily_requests"}
        ai = {}
        for k, v in values.items():
            if k in names:
                v = float(v)
                if not math.isfinite(v):
                    raise ValueError(f"{k} must be a finite number")
                ai[names[k]] = int(v) if k == "daily_requests" else v
        if ai:
            self.limits_store.update({"ai": ai})
        return self.limits()

    def paused(self) -> bool:
        return (self.dir / "paused").exists()

    def set_paused(self, on: bool) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        flag = self.dir / "paused"
        if on:
            flag.write_text("paused from the dashboard", encoding="utf-8")
        else:
            flag.unlink(missing_ok=True)

    # ---------------------------------------------------------------- log
    def read_events(self, day: str | None = None) -> list[dict]:
        files = sorted(self.dir.glob(f"usage-{day}*.jsonl" if day else "usage-*.jsonl"))
        out: list[dict] = []
        for f in files:
            try:
                lines = f.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for line in lines:
                if line.strip():
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        pass  # a half-written line (crash mid-write): skip it
        out.sort(key=lambda e: e.get("ts", 0))
        return out

    def today_totals(self) -> dict:
        ev = self.read_events(day_of())
        return {"requests": len(ev), "cost": sum(e.get("cost") or 0 for e in ev)}

    def record(self, model: str, kind: str, source: str, status: int, ms: int,
               usage: dict | None = None, note: str = "") -> dict:
        """Log one call. usage keys: in, out, think, cached, audio_in (token counts)."""
        u = usage or {}
        e = {"ts": round(time.time(), 3), "model": model, "kind": kind, "source": source,
             "status": status, "ms": ms,
             "in": int(u.get("in") or 0), "out": int(u.get("out") or 0), "think": int(u.get("think") or 0),
             "cached": int(u.get("cached") or 0), "audio_in": int(u.get("audio_in") or 0)}
        if note:
            e["note"] = note[:200]
        if prices.price_for(model) is None and any(e[k] for k in ("in", "out", "think", "cached", "audio_in")):
            e["price_estimated"] = True  # unknown model: counted at the highest known price, so the budget still works
        e["cost"] = prices.cost_usd(e, worst_case=True)
        line = json.dumps(e) + "\n"
        with self._lock:
            self.dir.mkdir(parents=True, exist_ok=True)
            with open(self.dir / f"usage-{day_of(e['ts'])}-p{os.getpid()}.jsonl", "a", encoding="utf-8") as f:
                f.write(line)
        return e

    # ---------------------------------------------------------------- guard
    def check(self, model: str, source: str) -> None:
        if self.paused():
            raise Blocked("AI calls are paused on the usage dashboard")
        lim, t = self.limits(), self.today_totals()
        if lim["daily_requests"] and t["requests"] >= lim["daily_requests"]:
            raise Blocked(f"daily request limit reached ({t['requests']}/{lim['daily_requests']:.0f})")
        if lim["daily_usd"] and t["cost"] >= lim["daily_usd"]:
            raise Blocked(f"daily budget reached (${t['cost']:.4f} of ${lim['daily_usd']:.2f})")
