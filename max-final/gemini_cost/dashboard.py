"""
Live Gemini cost dashboard: http://localhost:8600 (this PC only).
Shows calls, tokens, cost, forecast, daily limits and a pause switch.
Run: python run.py dashboard
"""

from __future__ import annotations

import calendar
import os
import time
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse

from . import prices
from .meter import Meter, day_of

PAGE = Path(__file__).resolve().parent / "dashboard.html"
KIND_LABEL = {"brain": "Thinking (answers)", "agent": "Thinking (agent + tools)", "notes": "Meeting notes",
              "check": "Health check", "stt": "Hearing (speech-to-text)", "tts": "Voice (text-to-speech)"}


def _totals(ev: list[dict]) -> dict:
    return {"requests": len(ev), "errors": sum(1 for e in ev if e.get("status") != 200),
            "in": sum(e.get("in", 0) for e in ev), "out": sum(e.get("out", 0) + e.get("think", 0) for e in ev),
            "audio": sum(e.get("audio_in", 0) for e in ev), "cost": sum(e.get("cost") or 0 for e in ev),
            "unpriced": sum(1 for e in ev if e.get("price_estimated"))}  # cost estimated at the highest price


def summary(meter: Meter, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    lt = time.localtime(now)
    today = day_of(now)
    events = [e for e in meter.read_events() if day_of(e.get("ts", 0)).startswith(today[:7])]
    day_ev = [e for e in events if day_of(e.get("ts", 0)) == today]

    groups: dict[tuple, list] = defaultdict(list)
    for e in day_ev:
        groups[(e.get("source", "?"), e.get("kind", "?"), e.get("model", "?"))].append(e)
    by_feature = sorted(({"source": s, "kind": KIND_LABEL.get(k, k), "model": m, **_totals(g),
                          "avgMs": int(sum(x.get("ms", 0) for x in g) / len(g))}
                         for (s, k, m), g in groups.items()), key=lambda r: -r["cost"])

    last_hour = [e for e in day_ev if e.get("ts", 0) >= now - 3600]
    per_hour = _totals(last_hour)["cost"]
    minutes = [{"requests": 0, "cost": 0.0} for _ in range(60)]
    for e in last_hour:
        i = 59 - int((now - e["ts"]) // 60)
        if 0 <= i < 60:
            minutes[i]["requests"] += 1
            minutes[i]["cost"] += e.get("cost") or 0
    hours_left = 24 - lt.tm_hour - lt.tm_min / 60
    days_in_month = calendar.monthrange(lt.tm_year, lt.tm_mon)[1]
    day_frac = lt.tm_mday - 1 + (lt.tm_hour + lt.tm_min / 60) / 24  # days elapsed this month
    month_cost = _totals(events)["cost"]
    recent = [{k: e.get(k) for k in ("ts", "source", "kind", "model", "status", "ms", "in", "out", "think",
                                     "audio_in", "cost", "note")} for e in day_ev[-30:]][::-1]
    for r in recent:
        r["kind"] = KIND_LABEL.get(r["kind"], r["kind"])
    return {
        "now": now, "today": _totals(day_ev), "month": _totals(events), "lastHour": _totals(last_hour),
        "forecast": {"todayEnd": _totals(day_ev)["cost"] + per_hour * hours_left, "dayAtPace": per_hour * 24,
                     "monthAtPace": per_hour * 24 * days_in_month,
                     "monthEnd": month_cost / day_frac * days_in_month if day_frac > 0.05 else None},
        "byFeature": by_feature, "minutes": minutes, "recent": recent,
        "limits": meter.limits(), "paused": meter.paused(), "prices": prices.PRICES,
    }


def create_app(meter: Meter | None = None) -> FastAPI:
    meter = meter or Meter()
    app = FastAPI(title="Gemini cost", docs_url=None, redoc_url=None, openapi_url=None)

    def guard(x_dashboard: str | None) -> None:
        # Changes need a custom header: a page from another site can't send it (no CORS here).
        if x_dashboard != "1":
            raise HTTPException(403, "forbidden")

    @app.get("/", response_class=HTMLResponse)
    def page() -> str:
        return PAGE.read_text(encoding="utf-8")

    @app.get("/api/usage")
    def usage() -> dict:
        return summary(meter)

    @app.post("/api/pause")
    async def pause(request: Request, x_dashboard: str | None = Header(None)) -> dict:
        guard(x_dashboard)
        body = await request.json()
        meter.set_paused(bool(body.get("paused")))
        return {"ok": True}

    @app.post("/api/limits")
    async def limits(request: Request, x_dashboard: str | None = Header(None)) -> dict:
        guard(x_dashboard)
        body = await request.json()
        try:
            values = {k: float(v) for k, v in body.items() if v not in (None, "")}
        except (TypeError, ValueError):
            raise HTTPException(400, "limits must be numbers")
        return {"ok": True, "limits": meter.set_limits(**values)}

    return app


def main() -> None:
    import uvicorn

    port = int(os.environ.get("GEMINI_COST_PORT", "8600"))
    print(f"Gemini cost dashboard on http://localhost:{port}", flush=True)
    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
