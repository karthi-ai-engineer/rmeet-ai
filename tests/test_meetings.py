"""
Step 4.5 offline tests: free/busy, booking a Teams meeting with approval, slot taken meanwhile, cancel, jobs.
Real graph + Approvals + database; fake Microsoft Graph; scripted model. No model calls, $0.
  .venv\\Scripts\\python tests\\test_meetings.py
"""

import asyncio
import json
import os
import shutil
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "max"))
os.environ["MAX_MAILBOX"] = "max@kestrelhomegoods.com"

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from agent.actions import action_tools  # noqa: E402
from agent.clock import FakeClock  # noqa: E402
from agent.graph import Deps, build_max_graph, new_request, resume_run, start_run  # noqa: E402
from agent.models import ChatHandle  # noqa: E402
from agent.testing import ScriptedChatModel, ai_call, ai_text  # noqa: E402
from agent.tools import memory_tools, task_tools  # noqa: E402
from approvals import Approvals  # noqa: E402
from store import Store  # noqa: E402

fails = 0
T, D = "T1", "kestrelhomegoods.com"


def check(name: str, ok, detail="") -> None:
    global fails
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f"  [{detail}]" if detail != "" else ""))


def utc(*a) -> datetime:
    return datetime(*a, tzinfo=timezone.utc)


class FakeGraph:
    DIRECTORY = [{"id": "aad-k", "displayName": "Karthi M", "mail": f"karthi@{D}"},
                 {"id": "aad-p", "displayName": "Prince Alex", "mail": f"prince@{D}"},
                 {"id": "aad-d", "displayName": "Daniel", "mail": f"daniel@{D}"}]

    def __init__(self):
        self.busy = {f"daniel@{D}": [(utc(2026, 11, 24, 9, 0), utc(2026, 11, 24, 10, 30), "Warehouse walk")],
                     f"prince@{D}": [(utc(2026, 11, 24, 14, 0), utc(2026, 11, 24, 16, 0), "Month-end close")],
                     f"karthi@{D}": [(utc(2026, 11, 24, 16, 0), utc(2026, 11, 24, 16, 30), "1:1 with Elena")]}
        self.events, self.creates, self.deleted = {}, 0, []

    async def get(self, path, params=None):
        if path == "/users":
            flt = (params or {})["$filter"].lower()
            if "eq '" in flt:
                want = flt.split("eq '", 1)[1].rstrip("')")
                return {"value": [u for u in self.DIRECTORY if u["mail"] == want]}
            want = flt.split("'", 2)[1]
            return {"value": [u for u in self.DIRECTORY if u["displayName"].lower().startswith(want)]}
        if path.endswith("/calendarView"):
            return {"value": [e for e in self.events.values()]}
        raise AssertionError(path)

    async def post(self, path, body):
        if path.endswith("/calendar/getSchedule"):
            s = datetime.fromisoformat(body["startTime"]["dateTime"]).replace(tzinfo=timezone.utc)
            e = datetime.fromisoformat(body["endTime"]["dateTime"]).replace(tzinfo=timezone.utc)
            fmt = lambda d: {"dateTime": d.strftime("%Y-%m-%dT%H:%M:%S.0000000"), "timeZone": "UTC"}  # noqa: E731
            return {"value": [{"scheduleId": a, "scheduleItems": [
                {"status": "busy", "subject": t, "start": fmt(b0), "end": fmt(b1)}
                for b0, b1, t in self.busy.get(a.lower(), []) if b0 < e and b1 > s]} for a in body["schedules"]]}
        if path.endswith("/events"):
            same = next((x for x in self.events.values() if x["transactionId"] == body["transactionId"]), None)
            if same:
                return same
            self.creates += 1
            eid = f"ev{self.creates}"
            ev = {"id": eid, "subject": body["subject"], "start": body["start"], "end": body["end"],
                  "attendees": body["attendees"], "transactionId": body["transactionId"], "isOrganizer": True,
                  "onlineMeeting": {"joinUrl": f"https://teams.microsoft.com/l/meetup-join/{eid}"}}
            self.events[eid] = ev
            return ev
        raise AssertionError(path)

    async def delete(self, path):
        eid = path.rsplit("/", 1)[1]
        self.events.pop(eid, None)
        self.deleted.append(eid)


class Cards:
    def __init__(self):
        self.posted, self.updated = [], []

    async def post(self, team, card, root):
        self.posted.append(card)
        return f"card{len(self.posted)}"

    async def update(self, team, root, msg_id, card):
        self.updated.append(card)


async def drain():
    for _ in range(50):
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if not tasks:
            return
        await asyncio.gather(*tasks)


async def main() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        st = Store(tmp / "max.db")
        st.replace_team_content({"teamId": T, "teamName": "Planning", "channelId": "C1", "posts": [], "files": [],
                                 "meetings": []})
        for name, aad, role in (("Karthi M", "aad-k", "owner"), ("Prince Alex", "aad-p", "member"),
                                ("Daniel", "aad-d", "member")):
            st.touch_person(T, name, aad, "person", email=f"{name.split()[0].lower()}@{D}", role=role)
        clock = FakeClock(utc(2026, 11, 23, 9, 0))

        def setup(*replies):
            fg, cards, posts = FakeGraph(), Cards(), []

            async def poster(team, text, mentions=None, root=None):
                posts.append(text)

            def toolsets(ctx):
                return memory_tools(ctx) + task_tools(ctx) + action_tools(ctx)
            appr = Approvals(st, clock, fg, toolsets, cards.post, cards.update)
            model = ScriptedChatModel(replies=list(replies))
            graph = build_max_graph(Deps(st, ChatHandle(model, "scripted", "t"), clock, toolsets, poster, appr,
                                         extra={"graph": fg}), InMemorySaver())

            async def resume(run_id, decision, root):
                await resume_run(graph, run_id, decision)
            appr.resume = resume
            return graph, appr, fg, cards, posts, model

        def req():
            return new_request(st, T, "mention", "Karthi M", "aad-k", "root-7")

        meet = lambda start: ai_call(("create_meeting", {"title": "Pilot follow-up", "start": start, "minutes": 30,  # noqa: E731
                                                         "attendees": ["Prince Alex", "Daniel"],
                                                         "agenda": "Vector quote, pilot timeline"}))

        # ---------------------------------------------------------------- free/busy
        def after_free(m):
            assert "10:30" in m[-1].content, m[-1].content
            return ai_text(m[-1].content)
        graph, appr, fg, cards, posts, model = setup(
            ai_call(("find_free_times", {"attendees": ["Prince", "Daniel"], "date": "2026-11-24"})), after_free)
        await start_run(graph, req(), "when are we all free tomorrow?")
        check("free/busy: first common slot is 10:30 (Daniel busy until 10:30); the requester is included",
              posts[-1].startswith("Free for Karthi M, Prince Alex, Daniel") and "10:30" in posts[-1]
              and "09:00" not in posts[-1] and "14:00" not in posts[-1] and "16:00" not in posts[-1], posts[-1][:140])

        # ---------------------------------------------------------------- busy slot blocked before any card
        graph, appr, fg, cards, posts, model = setup(meet("2026-11-24 09:00"), lambda m: ai_text(m[-1].content))
        await start_run(graph, req(), "book 9am")
        check("booking when someone is busy is blocked in code (no card)",
              not cards.posted and "Daniel is busy" in posts[-1], posts[-1][:120])
        graph, appr, fg, cards, posts, model = setup(meet("2026-11-23 08:00"), lambda m: ai_text(m[-1].content))
        await start_run(graph, req(), "book in the past")
        check("a time in the past is blocked", not cards.posted and "passed" in posts[-1])

        # ---------------------------------------------------------------- asked time busy -> nearest time + why
        graph, appr, fg, cards, posts, model = setup(
            ai_call(("create_meeting", {"title": "Pilot follow-up", "start": "2026-11-24 10:30", "minutes": 30,
                                        "attendees": ["Prince Alex", "Daniel"], "asked_start": "2026-11-24 09:00"})),
            ai_text("ok"))
        await start_run(graph, req(), "book 9am with Prince and Daniel")
        note = next((b["text"] for b in cards.posted[-1]["body"] if b.get("text", "").startswith("💡")), "") \
            if cards.posted else ""
        check("asked time busy -> card at the nearest free time, with a note (checked in code) of who is busy then",
              note.startswith("💡 You asked for Tue 24 Nov 09:00, but Daniel is busy 09:00–10:30 UTC (Warehouse walk)")
              and "nearest time everyone is free" in note, note)
        p_note = st.pendings(T, "pending")[-1]
        await appr.on_click("cancel", {"pendingId": p_note["id"], "version": p_note["version"]}, "aad-k", "Karthi M")

        # ---------------------------------------------------------------- card -> approve -> event once
        graph, appr, fg, cards, posts, model = setup(meet("2026-11-24 10:30"), ai_text("Booked."))
        r = req()
        await start_run(graph, r, "book it")
        facts = {f["title"]: f["value"] for f in cards.posted[-1]["body"][1]["facts"]}
        check("meeting card: title, when (with time zone), Max as organizer, all attendees incl. the requester",
              facts.get("Title") == "Pilot follow-up" and facts.get("When", "").startswith("Tue 24 Nov 2026 10:30–11:00")
              and facts.get("Organizer", "").startswith("Max (AI)") and all(
                  n in facts.get("Attendees", "") for n in ("Karthi M", "Prince Alex", "Daniel")), facts)
        check("nothing booked before approval", fg.creates == 0)
        p = st.pendings(T, "pending")[-1]
        await appr.on_click("approve", {"pendingId": p["id"], "version": 1}, "aad-k", "Karthi M")
        await drain()
        ev = list(fg.events.values())
        check("approved: one Teams meeting in Max's calendar with the 3 attendees",
              fg.creates == 1 and len(ev) == 1 and len(ev[0]["attendees"]) == 3 and ev[0]["start"]["dateTime"] ==
              "2026-11-24T10:30:00", ev[:1])
        jobs = {j["kind"]: j for j in st.jobs(T, "pending")}
        check("reminders (24 h, 15 min) and Max's join job are scheduled, in the requester's thread",
              sum(j["kind"] == "remind_meeting" for j in st.jobs(T, "pending")) == 2 and "join_own_meeting" in jobs
              and json.loads(jobs["join_own_meeting"]["payload"])["threadRoot"] == "root-7"
              and jobs["join_own_meeting"]["run_at"] == utc(2026, 11, 24, 10, 29, 30).timestamp())
        res = st.pending(p["id"])["result"]
        check("result has the Teams link; card says Done", "meetup-join" in res and "Done" in cards.updated[-1]["body"][0]["text"])
        payload = json.loads(st.pending(p["id"])["payload"])
        from agent.actions import meeting_execute
        from agent.tools import ToolContext
        ctx = ToolContext(st, T, "Karthi M", clock, {"graph": fg})
        await meeting_execute(ctx, payload, None)          # a retry with the same transactionId
        check("a retried create (same transactionId) doesn't make a second meeting", fg.creates == 1)

        # ---------------------------------------------------------------- slot taken while the card waited
        graph, appr, fg, cards, posts, model = setup(
            meet("2026-11-24 12:00"),
            lambda m: meet("2026-11-24 12:30") if "not created" in m[-1].content else ai_text("??"),
            ai_text("Booked 12:30 instead."))
        await start_run(graph, req(), "book noon")
        p1 = st.pendings(T, "pending")[-1]
        fg.busy[f"prince@{D}"].append((utc(2026, 11, 24, 11, 45), utc(2026, 11, 24, 12, 15), "Urgent call"))
        await appr.on_click("approve", {"pendingId": p1["id"], "version": 1}, "aad-k", "Karthi M")
        await drain()
        p2 = st.pendings(T, "pending")[-1] if st.pendings(T, "pending") else None
        check("slot taken meanwhile: not booked, card failed, a NEW card proposes another time (never moved silently)",
              fg.creates == 0 and st.pending(p1["id"])["status"] == "failed" and p2 is not None and p2["id"] != p1["id"]
              and "12:30" in p2["preview"], st.pending(p1["id"])["result"])

        # ---------------------------------------------------------------- cancel a meeting Max organised
        graph, appr, fg, cards, posts, model = setup(meet("2026-11-24 10:30"), ai_text("Booked."),
                                                     ai_call(("cancel_meeting", {"meeting": "pilot follow-up"})),
                                                     ai_text("Cancelled."))
        await start_run(graph, req(), "book")
        await appr.on_click("approve", {"pendingId": st.pendings(T, "pending")[-1]["id"], "version": 1}, "aad-k", "Karthi M")
        await drain()
        eid = next(iter(fg.events))
        await start_run(graph, req(), "cancel the pilot follow-up")
        pc = st.pendings(T, "pending")[-1]
        check("cancel card names the meeting and who will be told",
              "Cancel this meeting" in pc["preview"] and "Pilot follow-up" in pc["preview"], posts[-1][:200])
        await appr.on_click("approve", {"pendingId": pc["id"], "version": 1}, "aad-k", "Karthi M")
        await drain()
        from agent.tools import ToolContext
        everything = memory_tools(ToolContext(st, T, None, clock)) + task_tools(ToolContext(st, T, None, clock)) + \
            action_tools(ToolContext(st, T, None, clock, {"graph": fg}))
        check("every tool is offered to the model (none silently cut)",
              "cancel_meeting" in model.tool_names[-1] and len(model.tool_names[-1]) == len(everything),
              (len(model.tool_names[-1]), len(everything)))
        check("cancelled: event deleted, its join job cancelled",
              eid in fg.deleted and not any(j["kind"] == "join_own_meeting" and f"join:{eid}" == j["dedupe_key"]
                                            for j in st.jobs(T, "pending")))
        st.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\nMEETINGS: ALL PASS" if not fails else f"\nMEETINGS: {fails} FAILED")


asyncio.run(main())
sys.exit(1 if fails else 0)
