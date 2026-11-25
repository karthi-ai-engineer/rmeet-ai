"""
Agent lab: watch Max's agent graph work, step by step, and click Approve / Change / Cancel on its card.

  .venv\\Scripts\\python devtools\\agent_lab\\server.py   ->  http://localhost:8500

It runs the Phase 4 step 4.0 spike graph (max/agent/spike.py) on a tiny pretend world (no Microsoft calls).
  Replay (default): recorded Gemini answers from tests/cassettes/spike_gemini.json -> $0, no model calls.
                    Only the recorded requests and clicks have answers; anything else says "no recording".
  Live:             real model calls (Gemini on this PC), metered as source "lab" on the usage dashboard.
"""

import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "max"))

import uvicorn  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402
from langgraph.types import Command  # noqa: E402

from agent.clock import FakeClock  # noqa: E402
from agent.models import make_chat_handle  # noqa: E402
from agent.spike import SpikeWorld, _text_of, build_spike_graph  # noqa: E402
from agent.testing import CassetteHandle, CassetteMiss  # noqa: E402

PORT = 8500
PAGE = Path(__file__).resolve().parent / "index.html"
TAPE = ROOT / "tests" / "cassettes" / "spike_gemini.json"
START = datetime(2026, 11, 23, 9, 0, tzinfo=timezone.utc)   # same fake "now" as the recording
SCENARIOS = [
    {"id": "A", "title": "Book a meeting, approve it",
     "text": "Set up a 30-minute meeting tomorrow with Prince Alex and Daniel about the Riverside pilot. "
             "Check what we know about the pilot for the agenda.",
     "recorded": "Approve"},
    {"id": "B", "title": "Same, but ask for a change",
     "text": "Set up a 30-minute meeting tomorrow with Prince Alex and Daniel about the Riverside pilot. "
             "Check what we know about the pilot for the agenda.",
     "recorded": "Change: \"Make it 14:00 instead\", then Approve"},
    {"id": "C", "title": "Invite someone outside the company",
     "text": "Book 30 minutes tomorrow at 10:00 with Prince Alex and jane.doe@gmail.com about the pilot.",
     "recorded": "(no card expected)"},
]

app = FastAPI()


class Counting:
    """Wraps the model handle to count model calls for the page."""

    def __init__(self, inner):
        self.inner, self.model_id, self.calls = inner, inner.model_id, 0

    async def ainvoke(self, messages, tools=None, kind="agent"):
        self.calls += 1
        return await self.inner.ainvoke(messages, tools, kind)


@dataclass
class Session:
    id: str
    mode: str
    world: SpikeWorld
    graph: object
    handle: Counting
    cassette: CassetteHandle | None
    started: float = field(default_factory=time.time)
    events: list = field(default_factory=list)
    paused: str | None = None
    done: bool = False


SESSIONS: dict[str, Session] = {}


def _calls(ai: AIMessage) -> list:
    return [{"name": c["name"], "args": c["args"]} for c in ai.tool_calls]


def describe(node: str, delta: dict | None, world: SpikeWorld) -> dict:
    """One graph step -> a timeline entry for the page."""
    ev = {"node": node, "t": time.strftime("%H:%M:%S")}
    msgs = (delta or {}).get("messages") or []
    if node == "agent":
        ai = next((m for m in msgs if isinstance(m, AIMessage)), None)
        ev["text"] = _text_of(ai.content) if ai else ""
        ev["calls"] = _calls(ai) if ai else []
    elif node in ("tools", "prepare_approval", "execute", "await_approval"):
        ev["results"] = [{"name": m.name, "content": str(m.content)} for m in msgs if isinstance(m, ToolMessage)]
        if node == "prepare_approval" and (delta or {}).get("pending"):
            ev["card"] = delta["pending"]["preview"]
        if node == "await_approval" and (delta or {}).get("decision"):
            ev["decision"] = delta["decision"]
    elif node == "respond":
        ev["reply"] = world.replies[-1] if world.replies else ""
    return ev


async def advance(s: Session, inp) -> None:
    cfg = {"configurable": {"thread_id": s.id}}
    s.paused = None
    try:
        async for chunk in s.graph.astream(inp, cfg, stream_mode="updates"):
            for node, delta in chunk.items():
                if node == "__interrupt__":
                    s.paused = delta[0].value["preview"]
                    s.events.append({"node": "await_approval", "t": time.strftime("%H:%M:%S"), "waiting": True})
                else:
                    s.events.append(describe(node, delta, s.world))
        if s.paused is None:
            s.done = True
    except CassetteMiss:
        s.events.append({"node": "error", "t": time.strftime("%H:%M:%S"),
                         "error": "No recording for this step. In Replay only the recorded requests and clicks "
                                  "have answers. Switch to Live to try something new (uses Gemini)."})
        s.done = True
    except Exception as e:  # show it, don't crash the lab
        s.events.append({"node": "error", "t": time.strftime("%H:%M:%S"), "error": f"{type(e).__name__}: {e}"})
        s.done = True


def view(s: Session) -> dict:
    stats = {"modelCalls": s.handle.calls, "replayed": s.cassette.replayed if s.cassette else 0,
             "live": 0, "costUsd": 0.0}
    if s.mode == "live":
        try:
            from gemini_usage import meter, prices
            ev = [e for e in meter.read_events() if e.get("source") == "lab" and e.get("ts", 0) >= s.started]
            stats["live"] = len(ev)
            stats["costUsd"] = sum(prices.cost_usd(e) or 0 for e in ev)
        except ImportError:
            stats["live"] = s.handle.calls
    return {"session": s.id, "mode": s.mode, "model": s.handle.model_id, "events": s.events, "paused": s.paused,
            "done": s.done, "calendar": list(s.world.events.values()), "replies": s.world.replies, "stats": stats}


@app.get("/", response_class=HTMLResponse)
async def page():
    return PAGE.read_text(encoding="utf-8")


@app.get("/api/scenarios")
async def scenarios():
    return {"scenarios": SCENARIOS, "recordingExists": TAPE.exists()}


@app.post("/api/run")
async def run(req: Request):
    body = await req.json()
    text = (body.get("text") or "").strip()
    mode = "live" if body.get("mode") == "live" else "replay"
    if not text:
        return JSONResponse({"error": "Type a request first."}, 400)
    if mode == "live":
        try:
            inner = make_chat_handle(source="lab")
        except Exception as e:
            return JSONResponse({"error": f"Live model not available: {e}"}, 400)
        cassette = None
    else:
        cassette = inner = CassetteHandle(TAPE)
    world = SpikeWorld(clock=FakeClock(START))
    handle = Counting(inner)
    s = Session(uuid.uuid4().hex[:10], mode, world, build_spike_graph(handle, world, InMemorySaver()), handle, cassette)
    SESSIONS[s.id] = s
    s.events.append({"node": "request", "t": time.strftime("%H:%M:%S"), "text": text})
    await advance(s, {"messages": [HumanMessage(text)], "pending": None, "decision": None, "steps": 0})
    return view(s)


@app.post("/api/decide")
async def decide(req: Request):
    body = await req.json()
    s = SESSIONS.get(body.get("session", ""))
    if not s or not s.paused:
        return JSONResponse({"error": "Nothing is waiting for approval."}, 400)
    action = body.get("action")
    if action not in ("approve", "change", "cancel"):
        return JSONResponse({"error": "Unknown action."}, 400)
    edit = (body.get("edit") or "").strip()
    if action == "change" and not edit:
        return JSONResponse({"error": "Type what to change first."}, 400)
    s.events.append({"node": "click", "t": time.strftime("%H:%M:%S"), "action": action, "edit": edit})
    await advance(s, Command(resume={"action": action, "by": "Karthi M", "edit": edit}))
    return view(s)


if __name__ == "__main__":
    print(f"Agent lab: http://localhost:{PORT}  (Replay = recorded answers, $0; Live = real model, metered)")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
