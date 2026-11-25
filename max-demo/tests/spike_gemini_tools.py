"""
Step 4.0 spike with the REAL brain model: LangGraph + tool calling + approval pause.

  .venv\\Scripts\\python tests\\spike_gemini_tools.py            replay from the cassette ($0, no model calls)
  .venv\\Scripts\\python tests\\spike_gemini_tools.py --record   call the model and record (costs ~10 requests)

Scenarios (Mon 23 Nov 2026 09:00, fake clock, so prompts are stable for replay):
  A  "set up 30 min tomorrow with Prince and Daniel about the pilot" -> reads -> card -> Approve -> 1 event
  B  same, then Change "make it 14:00" -> new card at 14:00 -> Approve -> 1 event at 14:00
  C  "book with Prince and jane.doe@gmail.com" -> outside person blocked in code -> no event, no card
Checks are deterministic (world state), not judged. Gemini calls go through the usage meter (source "spike").
"""

import asyncio
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "max"))

from langchain_core.messages import AIMessage, ToolMessage  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from agent.clock import FakeClock  # noqa: E402
from agent.models import make_chat_handle  # noqa: E402
from agent.spike import SpikeWorld, ask, build_spike_graph, decide, paused  # noqa: E402
from agent.testing import CassetteHandle, tool_pair_problems  # noqa: E402

RECORD = "--record" in sys.argv
TAPE = ROOT / "tests" / "cassettes" / "spike_gemini.json"
START = datetime(2026, 11, 23, 9, 0, tzinfo=timezone.utc)
SIG_KEY = "__gemini_function_call_thought_signatures__"
fails = 0
stats = {"parallel_turns": 0, "tool_turns": 0, "signed_turns": 0}


def check(name: str, ok, detail="") -> None:
    global fails
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f"  [{detail}]" if detail != "" else ""))


def note_turns(messages) -> None:
    for m in messages:
        if isinstance(m, AIMessage) and m.tool_calls:
            stats["tool_turns"] += 1
            stats["parallel_turns"] += len(m.tool_calls) > 1
            stats["signed_turns"] += bool(m.additional_kwargs.get(SIG_KEY))


async def scenario(handle, name: str, request: str, steps) -> SpikeWorld:
    world = SpikeWorld(clock=FakeClock(START))
    graph = build_spike_graph(handle, world, InMemorySaver())
    t = time.perf_counter()
    out = await ask(graph, name, request)
    for step in steps:
        out = await step(graph, world, out)
    msgs = (await graph.aget_state({"configurable": {"thread_id": name}})).values["messages"]
    note_turns(msgs)
    check(f"[{name}] history rule held", tool_pair_problems(msgs) == [], tool_pair_problems(msgs))
    print(f"    reply: {world.replies[-1][:160] if world.replies else '(none)'}   ({time.perf_counter() - t:.1f}s)")
    return world


async def main() -> None:
    inner = make_chat_handle(source="spike") if RECORD else None
    handle = CassetteHandle(TAPE, inner=inner, record=RECORD)
    print(f"Model: {handle.model_id or '(from cassette)'} · mode: {'RECORD (live model)' if RECORD else 'replay ($0)'}\n")

    # --- A: approve
    async def approve_first_card(graph, world, out):
        req = paused(out)
        check("[A] model looked things up, then proposed a meeting for approval", req is not None, out.get("messages", [])[-1:])
        if req:
            print(f"    card: {req['preview']}")
            ok_time = "2026-11-24" in req["preview"] and not any(t in req["preview"] for t in ("09:00", "11:00", "15:00"))
            check("[A] proposed tomorrow (24 Nov) at a time everyone is free", ok_time)
            check("[A] nothing created before approval", world.events == {})
            out = await decide(graph, "A", "approve")
        return out
    world = await scenario(handle, "A", "Set up a 30-minute meeting tomorrow with Prince Alex and Daniel about the "
                           "Riverside pilot. Check what we know about the pilot for the agenda.", [approve_first_card])
    ev = list(world.events.values())
    check("[A] after Approve: exactly one event, with Prince and Daniel",
          len(ev) == 1 and {"Prince Alex", "Daniel"} <= set(ev[0]["attendees"]), ev)
    if RECORD:
        time.sleep(25)            # stay under the meter's per-minute limit

    # --- B: change then approve
    async def change_to_14(graph, world, out):
        req = paused(out)
        check("[B] first card shown", req is not None)
        return await decide(graph, "B", "change", edit="Make it 14:00 instead") if req else out

    async def approve_second_card(graph, world, out):
        req = paused(out)
        check("[B] after Change, a new card at 14:00 and still nothing created",
              req is not None and "14:00" in req["preview"] and world.events == {}, req and req["preview"])
        return await decide(graph, "B", "approve") if req else out
    world = await scenario(handle, "B", "Set up a 30-minute meeting tomorrow with Prince Alex and Daniel about the "
                           "Riverside pilot. Check what we know about the pilot for the agenda.",
                           [change_to_14, approve_second_card])
    ev = list(world.events.values())
    check("[B] after Change + Approve: exactly one event, at 14:00", len(ev) == 1 and ev[0]["start"].endswith("14:00"), ev)
    if RECORD:
        time.sleep(25)

    # --- C: outside attendee
    async def no_card(graph, world, out):
        check("[C] no approval card for an outside attendee", paused(out) is None)
        return out
    world = await scenario(handle, "C", "Book 30 minutes tomorrow at 10:00 with Prince Alex and jane.doe@gmail.com "
                           "about the pilot.", [no_card])
    check("[C] nothing created", world.events == {})

    print(f"\nTool-calling turns: {stats['tool_turns']}, with two or more calls at once: {stats['parallel_turns']}, "
          f"carrying Gemini thought signatures: {stats['signed_turns']}")
    print(f"Model calls: recorded {handle.recorded}, replayed {handle.replayed}")
    if RECORD:
        try:
            from gemini_usage import meter, prices
            ev = [e for e in meter.read_events() if e.get("source") == "spike"]
            print(f"Gemini (meter, source=spike): {len(ev)} requests, statuses {sorted({e['status'] for e in ev})}, "
                  f"tokens in {sum(e['in'] for e in ev)} / out {sum(e['out'] for e in ev)} / thinking "
                  f"{sum(e['think'] for e in ev)}, ${sum(prices.cost_usd(e) or 0 for e in ev):.5f} at paid price")
        except ImportError:
            pass
    print("\nSPIKE: ALL PASS" if not fails else f"\nSPIKE: {fails} FAILED")


asyncio.run(main())
sys.exit(1 if fails else 0)
