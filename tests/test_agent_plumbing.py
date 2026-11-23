"""
Step 4.0 offline tests for the agent plumbing (no model is called: $0).
  .venv\\Scripts\\python tests\\test_agent_plumbing.py

Covers: fake clock, usage mapping, metered model handle (record / budget block / error), the spike graph's
paths (parallel read calls, approval pause + approve / change / cancel, safety block, step cap), saved runs
resumed by a fresh graph (like a card click in another request), Gemini thought signatures surviving the
checkpointer, and cassettes (record once, replay free, a changed prompt fails loudly).
"""

import asyncio
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "max"))

from langchain_core.messages import AIMessage, ToolMessage, messages_from_dict, messages_to_dict  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver  # noqa: E402

from agent.clock import FakeClock  # noqa: E402
from agent.models import BudgetBlocked, ChatHandle, ModelError, usage_for_meter  # noqa: E402
from agent.spike import MAX_STEPS, SpikeWorld, ask, build_spike_graph, decide, paused  # noqa: E402
from agent.testing import (CassetteHandle, CassetteMiss, ScriptedChatModel, ai_call, ai_text,  # noqa: E402
                           tool_pair_problems)

fails = 0
SIG_KEY = "__gemini_function_call_thought_signatures__"
START = datetime(2026, 11, 23, 9, 0, tzinfo=timezone.utc)          # Mon 23 Nov 2026 09:00
TEAM = ["Karthi M", "Prince Alex", "Daniel"]


def check(name: str, ok, detail="") -> None:
    global fails
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f"  [{detail}]" if detail != "" else ""))


class FakeMeter:
    class Blocked(Exception):
        pass

    def __init__(self, block: bool = False):
        self.block, self.checks, self.records = block, 0, []

    def check(self, model, source=""):
        self.checks += 1
        if self.block:
            raise self.Blocked("daily budget used (test)")

    def record(self, model, kind, source, status, ms, usage=None, note=""):
        self.records.append({"model": model, "kind": kind, "status": status, "usage": usage or {}, "note": note})


def scripted(*replies) -> tuple[ScriptedChatModel, ChatHandle]:
    model = ScriptedChatModel(replies=list(replies))
    return model, ChatHandle(model, "scripted-model", "test")


def fresh() -> SpikeWorld:
    return SpikeWorld(clock=FakeClock(START))


async def state_messages(graph, thread):
    return (await graph.aget_state({"configurable": {"thread_id": thread}})).values["messages"]


def meeting_call(start="2026-11-24 10:00", attendees=TEAM):
    return ai_call(("create_meeting", {"title": "Pilot follow-up", "start": start, "minutes": 30,
                                        "attendees": list(attendees), "agenda": "Vector's Riverside quote"}))


async def main() -> None:
    # ------------------------------------------------------------------ clock
    clk = FakeClock(START)
    clk.advance(hours=25)
    check("fake clock moves only when told", clk.now() == datetime(2026, 11, 24, 10, 0, tzinfo=timezone.utc))
    try:
        FakeClock(datetime(2026, 11, 23, 9, 0))
        check("fake clock refuses times without a time zone", False)
    except ValueError:
        check("fake clock refuses times without a time zone", True)

    # ------------------------------------------------------------------ usage + meter
    msg = AIMessage(content="x", usage_metadata={"input_tokens": 1200, "output_tokens": 27, "total_tokens": 1227,
                                                 "output_token_details": {"reasoning": 7},
                                                 "input_token_details": {"cache_read": 1000}})
    u = usage_for_meter(msg)
    check("usage mapped to the meter's fields (thinking split out)",
          u == {"promptTokenCount": 1200, "candidatesTokenCount": 20, "thoughtsTokenCount": 7,
                "cachedContentTokenCount": 1000, "totalTokenCount": 1227}, u)

    meter = FakeMeter()
    model, _ = scripted(ai_text("hi"))
    h = ChatHandle(model, "gemini-test", "gemini", meter, "test")
    await h.ainvoke([AIMessage(content="ping")])
    check("metered call: checked before, recorded once after with status 200",
          meter.checks == 1 and len(meter.records) == 1 and meter.records[0]["status"] == 200)

    meter = FakeMeter(block=True)
    model, _ = scripted(ai_text("should not be called"))
    try:
        await ChatHandle(model, "gemini-test", "gemini", meter, "test").ainvoke([AIMessage(content="ping")])
        check("budget block stops the call", False)
    except BudgetBlocked:
        check("budget block stops the call before the model is used", len(model.calls) == 0 and not meter.records)

    def boom(_msgs):
        raise RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded")
    meter = FakeMeter()
    model, _ = scripted(boom)
    try:
        await ChatHandle(model, "gemini-test", "gemini", meter, "test").ainvoke([AIMessage(content="ping")])
        check("model error is reported", False)
    except ModelError as e:
        check("model error: raised once as ModelError(429), logged, no retry",
              e.status == 429 and len(model.calls) == 1 and meter.records[0]["status"] == 429, e.status)

    # ------------------------------------------------------------------ happy path: parallel reads + approve
    world = fresh()
    model, handle = scripted(
        ai_call(("search_memory", {"query": "Riverside pilot"}),
                ("find_free_times", {"date": "2026-11-24", "attendees": TEAM, "minutes": 30})),
        meeting_call(),
        ai_text("Booked: Pilot follow-up, Tue 24 Nov 10:00."))
    graph = build_spike_graph(handle, world, InMemorySaver())
    out = await ask(graph, "t1", "Set up 30 minutes tomorrow with Prince and Daniel about the pilot")
    req = paused(out)
    check("two read tools in one model turn both ran, then the model saw both results",
          sum(isinstance(m, ToolMessage) for m in model.calls[1]) == 2)
    check("meeting call pauses for approval with the full preview",
          req and "2026-11-24 10:00" in req["preview"] and "Daniel" in req["preview"], req and req["preview"])
    check("nothing is created before approval", world.events == {})
    check("the model was offered exactly the 3 spike tools",
          model.tool_names[0] == ["search_memory", "find_free_times", "create_meeting"], model.tool_names[0])
    out = await decide(graph, "t1", "approve")
    check("approve: event created once, run finished, reply posted",
          len(world.events) == 1 and paused(out) is None and world.replies[-1].startswith("Booked"), world.replies)
    check("history rule held (every tool call answered once)", tool_pair_problems(await state_messages(graph, "t1")) == [])
    check("model calls for the whole request", len(model.calls) == 3, len(model.calls))

    # ------------------------------------------------------------------ change
    world = fresh()

    def after_change(msgs):
        last = msgs[-1]
        assert isinstance(last, ToolMessage) and "asked for a change: make it 14:00" in last.content, last
        return meeting_call(start="2026-11-24 14:00")
    model, handle = scripted(meeting_call(), after_change, ai_text("Booked for 14:00."))
    graph = build_spike_graph(handle, world, InMemorySaver())
    await ask(graph, "t2", "Meeting tomorrow 10:00 with Prince and Daniel")
    out = await decide(graph, "t2", "change", edit="make it 14:00")
    req = paused(out)
    check("change: the model gets the edit as the call's result and proposes again",
          req and "14:00" in req["preview"] and world.events == {}, req and req["preview"])
    await decide(graph, "t2", "approve")
    ev = list(world.events.values())
    check("change then approve: one event, at the new time", len(ev) == 1 and ev[0]["start"].endswith("14:00"))
    check("history rule held after a change", tool_pair_problems(await state_messages(graph, "t2")) == [])

    # ------------------------------------------------------------------ cancel
    world = fresh()
    model, handle = scripted(meeting_call())
    graph = build_spike_graph(handle, world, InMemorySaver())
    await ask(graph, "t3", "Meeting tomorrow 10:00")
    await decide(graph, "t3", "cancel")
    check("cancel: nothing created, no extra model call, polite reply",
          world.events == {} and len(model.calls) == 1 and "didn't do it" in world.replies[-1], world.replies)

    # ------------------------------------------------------------------ safety gate
    world = fresh()

    def explains_block(msgs):
        last = msgs[-1]
        assert isinstance(last, ToolMessage) and last.content.startswith("blocked:"), last
        return ai_text("I can only invite people in the company, so I didn't invite jane@gmail.com.")
    model, handle = scripted(meeting_call(attendees=["Prince Alex", "jane@gmail.com"]), explains_block)
    graph = build_spike_graph(handle, world, InMemorySaver())
    out = await ask(graph, "t4", "Invite jane@gmail.com and Prince to the pilot meeting")
    check("outside attendee: blocked in code, no approval card, nothing created",
          paused(out) is None and world.events == {} and "company" in world.replies[-1], world.replies[-1])

    # ------------------------------------------------------------------ step cap
    world = fresh()
    model, handle = scripted(*[ai_call(("search_memory", {"query": f"pilot {i}"})) for i in range(10)])
    graph = build_spike_graph(handle, world, InMemorySaver())
    await ask(graph, "t5", "keep searching")
    msgs = await state_messages(graph, "t5")
    check(f"a model that never stops is cut off after {MAX_STEPS} passes, calls closed",
          len(model.calls) == MAX_STEPS and tool_pair_problems(msgs) == [] and "couldn't finish" in world.replies[-1],
          len(model.calls))

    # ------------------------------------------------------------------ saved runs + signatures
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "checkpoints.db")
        world = fresh()
        call = meeting_call()
        call.additional_kwargs[SIG_KEY] = {call.tool_calls[0]["id"]: "c2lnbmF0dXJlLWJ5dGVz"}
        model, handle = scripted(call, ai_text("Booked."))
        async with AsyncSqliteSaver.from_conn_string(db) as saver:
            await ask(build_spike_graph(handle, world, saver), "t6", "Meeting tomorrow 10:00")
        # a new graph + new database connection, like a card click arriving as a separate request
        async with AsyncSqliteSaver.from_conn_string(db) as saver:
            graph = build_spike_graph(handle, world, saver)
            out = await decide(graph, "t6", "approve")
            msgs = await state_messages(graph, "t6")
        sig_ok = any(isinstance(m, AIMessage) and m.additional_kwargs.get(SIG_KEY) for m in msgs)
        check("saved run resumed by a fresh graph and database connection", len(world.events) == 1 and paused(out) is None)
        check("Gemini thought signatures survive the saved run (SQLite, strict msgpack)", sig_ok)
        check("the model's next call got the signature back unchanged",
              any(isinstance(m, AIMessage) and m.additional_kwargs.get(SIG_KEY) for m in model.calls[-1]))

    # ------------------------------------------------------------------ cassettes
    rt = messages_from_dict(messages_to_dict([call]))[0]
    check("cassette serialisation keeps tool calls and signatures",
          rt.tool_calls == call.tool_calls and rt.additional_kwargs.get(SIG_KEY) == call.additional_kwargs[SIG_KEY])
    with tempfile.TemporaryDirectory() as tmp:
        tape = Path(tmp) / "spike.json"
        world = fresh()
        model, inner = scripted(
            ai_call(("search_memory", {"query": "pilot"}),
                    ("find_free_times", {"date": "2026-11-24", "attendees": TEAM, "minutes": 30})),
            meeting_call(), ai_text("Booked."))
        rec = CassetteHandle(tape, inner=inner, record=True)
        graph = build_spike_graph(rec, world, InMemorySaver())
        await ask(graph, "c1", "Set up 30 minutes tomorrow about the pilot")
        await decide(graph, "c1", "approve")
        check("record mode: 3 real calls saved to the cassette", rec.recorded == 3 and tape.exists(), rec.recorded)

        world = fresh()
        play = CassetteHandle(tape)                       # no inner model at all
        graph = build_spike_graph(play, world, InMemorySaver())
        await ask(graph, "c2", "Set up 30 minutes tomorrow about the pilot")
        await decide(graph, "c2", "approve")
        check("replay: same run with zero model calls", play.replayed == 3 and len(world.events) == 1, play.replayed)

        graph = build_spike_graph(CassetteHandle(tape), fresh(), InMemorySaver())
        try:
            await ask(graph, "c3", "Set up 45 minutes tomorrow about the pilot")   # prompt changed
            check("a changed prompt fails loudly instead of calling the model", False)
        except CassetteMiss:
            check("a changed prompt fails loudly instead of calling the model", True)

    print("\nAGENT PLUMBING: ALL PASS" if not fails else f"\nAGENT PLUMBING: {fails} FAILED")


asyncio.run(main())
sys.exit(1 if fails else 0)
