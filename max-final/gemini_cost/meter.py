"""
Gemini usage meter. Every Gemini call in the project goes through here.

  meter = Meter()                 one cost folder for the whole project (the cap is per key, not per program)
  meter.check(model, source)      before a call: raises Blocked if paused or over the daily limit
  meter.record(model, kind, ...)  after a call: one JSON line in usage-YYYY-MM-DD-p<pid>.jsonl
  meter.read_events(day)          the logged calls (all days, or one 'YYYY-MM-DD')

Each process writes its own file, because appends from several processes to one file lose lines
on Windows. Readers merge all files of a day.
Limits: limits.json ({"daily_usd": 1.0, "daily_requests": 1000}, 0 = no limit). Pause switch: the file `paused`.
Folder: GEMINI_COST_DIR if set, else <repo>/data/gemini_cost.
This module must not import max/ or teams_sim/: both use it.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from . import prices

DEFAULT_LIMITS = {"daily_usd": 1.0, "daily_requests": 1000}
DEFAULT_DIR = Path(__file__).resolve().parent.parent / "data" / "gemini_cost"


class Blocked(Exception):
    """The meter refused a Gemini call (paused, or a daily limit reached)."""


def day_of(ts: float | None = None) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


class Meter:
    def __init__(self, data_dir: Path | str | None = None):
        self.dir = Path(data_dir or os.environ.get("GEMINI_COST_DIR") or DEFAULT_DIR)
        self._lock = threading.Lock()

    # ---------------------------------------------------------------- settings
    def limits(self) -> dict:
        try:
            saved = json.loads((self.dir / "limits.json").read_text(encoding="utf-8"))
            return {**DEFAULT_LIMITS, **{k: float(v) for k, v in saved.items() if k in DEFAULT_LIMITS}}
        except (OSError, ValueError, TypeError, AttributeError):
            return dict(DEFAULT_LIMITS)

    def set_limits(self, **values: float) -> dict:
        lim = self.limits()
        lim.update({k: float(v) for k, v in values.items() if k in DEFAULT_LIMITS and float(v) >= 0})
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "limits.json").write_text(json.dumps(lim, indent=2), encoding="utf-8")
        return lim

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
        if not prices.price_for(model) and any(e[k] for k in ("in", "out", "think", "cached", "audio_in")):
            e["price_estimated"] = True  # unknown model: counted at the highest known price, so the cap still works
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
            raise Blocked("Gemini is paused on the cost dashboard")
        lim, t = self.limits(), self.today_totals()
        if lim["daily_requests"] and t["requests"] >= lim["daily_requests"]:
            raise Blocked(f"daily request limit reached ({t['requests']}/{lim['daily_requests']:.0f})")
        if lim["daily_usd"] and t["cost"] >= lim["daily_usd"]:
            raise Blocked(f"daily budget reached (${t['cost']:.4f} of ${lim['daily_usd']:.2f})")
