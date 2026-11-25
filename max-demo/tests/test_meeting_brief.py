"""
Phase 5.1 offline tests: the pre-meeting brief. 15 minutes before a meeting Max posts the agenda, what was decided
last time, each attendee's open action items (overdue first), files new since last time and open approvals, and
@mentions the people invited. No AI. Real database, real job runner and handlers, real MeetingCall for storing the
notes. $0.
  .venv\\Scripts\\python tests\\test_meeting_brief.py
"""

import asyncio
import json
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "max"))

import briefs  # noqa: E402
import followups  # noqa: E402
from agent.clock import FakeClock  # noqa: E402
from calling import MeetingCall  # noqa: E402
from jobs import JobRunner  # noqa: E402
from store import Store  # noqa: E402

fails = 0
T, ROOT_ID = "T1", "1795300000001"
UTC = timezone.utc


def check(name: str, ok, detail="") -> None:
    global fails
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f"  [{detail}]" if detail != "" else ""))


def ts(*a) -> float:
    return datetime(*a, tzinfo=UTC).timestamp()


class Poster:
    def __init__(self):
        self.posts = []

    async def __call__(self, team, text, mentions=None, root=None):
        self.posts.append({"text": text, "mentions": mentions or [], "root": root})
        return "m"


async def main() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        st = Store(tmp / "max.db")
        check("database schema v6 (meeting_notes table)",
              sqlite3.connect(tmp / "max.db").execute("PRAGMA user_version").fetchone()[0] == 6)
        st.replace_team_content({"teamId": T, "teamName": "Planning", "channelId": "C", "driveId": "D", "posts": [],
                                 "files": [{"id": "f1", "name": "07_Pilot_Proposal.pdf", "author": "Daniel",
                                            "time": "2026-11-18 16:45", "text": "x"},
                                           {"id": "f2", "name": "11_Northgate_Rate_Offer.md", "author": "Prince Alex",
                                            "time": "2026-11-21 11:00", "text": "y"}],
                                 "meetings": [], "timeZone": "UTC"})
        for name, aad, kind in (("Karthi M", "aad-k", "person"), ("Prince Alex", "aad-p", "person"),
                                ("Daniel", "aad-d", "person"), ("Jacob Thomas", "aad-j", "person"),
                                ("Max", "bot-max", "bot")):
            st.touch_person(T, name, aad, kind)
        clock = FakeClock(datetime(2026, 11, 24, 10, 15, tzinfo=UTC))
        tz = ZoneInfo("UTC")

        # last time: the meeting this one follows on from (same thread), held Fri 20 Nov
        prev_title = "Riverside pilot quote discussion"
        st.add_meeting_notes(T, prev_title, ROOT_ID, "https://join/prev", ts(2026, 11, 20, 10, 30),
                             {"decisions": ["Go with Vector for the Riverside pilot (200K)", "Go-live 1 May 2027",
                                            "Fund the 95K net with options D and E", "Campaign Option B",
                                            "Final total 11,500K"],
                              "action_items": []})
        st.add_meeting_notes(T, "Leadership sync", None, "https://join/other", ts(2026, 11, 22, 9, 0),
                             {"decisions": ["Unrelated decision"], "action_items": []})
        t1 = st.add_task(T, "Confirm the quote in writing", "Daniel", "2026-11-23", "meeting", prev_title, ROOT_ID, "aad-d")
        t2 = st.add_task(T, "Update the budget to v3", "Prince Alex", "2026-11-25", "meeting", prev_title, ROOT_ID, "aad-p")
        st.add_task(T, "Update the campaign plan", "Jacob Thomas", "2026-11-25", "meeting", "Campaign review", None, "aad-j")
        t4 = st.add_task(T, "Book the Riverside site visit", "Karthi M", "2026-11-22", "meeting", prev_title, ROOT_ID, "aad-k")
        st.update_task(t4, status="done")
        st.add_pending({"id": "pend1", "team_id": T, "run_id": "r1", "tool": "send_email", "call_id": "c1",
                        "payload": "{}", "payload_hash": "h", "requester": "Karthi M", "requester_aad": "aad-k",
                        "thread_root": ROOT_ID, "status": "pending", "version": 1, "created_at": ts(2026, 11, 24, 9),
                        "expires_at": ts(2026, 11, 25, 9),
                        "preview": json.dumps({"kind": "email", "title": "Email for approval",
                                               "facts": [["Subject", "Riverside update"]]})})

        p = {"subject": "Follow-up: Riverside pilot quote discussion", "start": "2026-11-24 10:30",
             "joinUrl": "https://join/new", "label": "15m", "threadRoot": ROOT_ID, "agenda": "Check the signed quote.",
             "attendees": [{"name": "Karthi M", "aad": "aad-k"}, {"name": "Prince Alex", "aad": "aad-p"},
                           {"name": "Daniel", "aad": "aad-d"}, {"name": "Max", "aad": "bot-max"}]}
        text, mentions = briefs.compose(st, T, p, clock.now(), tz)
        print("   ---\n   " + text.replace("\n", "\n   ") + "\n   ---")
        check("heading: title, starts in 15 minutes, time + time zone, join link",
              text.startswith("🗒️ **Meeting brief: Follow-up: Riverside pilot quote discussion** · starts in 15 minutes "
                              "(Tue 24 Nov 10:30 UTC)") and "[Join the meeting](https://join/new)" in text)
        check("@mentions the invited people (never Max)",
              mentions == [("Karthi M", "aad-k"), ("Prince Alex", "aad-p"), ("Daniel", "aad-d")] and
              "With: <at>Karthi M</at>, <at>Prince Alex</at>, <at>Daniel</at>" in text and "Max</at>" not in text)
        check("agenda from the invite", "**Agenda**\nCheck the signed quote." in text)
        check("last time = the meeting in the same thread (not the more recent unrelated one), 4 decisions + 'more'",
              "**Last time** (Riverside pilot quote discussion, Fri 20 Nov)" in text and "Go with Vector" in text
              and "…and 1 more" in text and "Unrelated decision" not in text)
        check("how many of last time's action items are done", "Action items from then: 1 of 3 done" in text)
        sec = text.split("**Open action items for this meeting's people**")[1].split("\n\n")[0]
        check("open action items of the people in the meeting: overdue first and flagged; others' and done ones left out",
              sec.strip().splitlines() == ["- ⚠️ Daniel: Confirm the quote in writing (was due Mon 23 Nov)",
                                           "- Prince Alex: Update the budget to v3 (due Wed 25 Nov)"], sec)
        check("files new since last time (not older ones)",
              "**New since last time**\n- 11_Northgate_Rate_Offer.md (Prince Alex)" in text and "07_Pilot" not in text)
        check("approvals still waiting in this thread", "**Waiting for approval**\n- email 'Riverside update' (asked by Karthi M)" in text)
        check("ends by saying Max will join and how to ask it", text.endswith('say "Max, …" to ask me something or get it done._'))

        # a channel meeting Max only knows from Graph: no attendees, no agenda, nothing before it
        bare, m2 = briefs.compose(st, T, {"subject": "Q1 planning kickoff", "start": "2026-11-24 10:30", "label": "15m"},
                                  clock.now(), tz)
        check("first meeting of its kind: no 'Last time' / 'New since' (never someone else's meeting), team's open items",
              "Last time" not in bare and "New since" not in bare and "With:" not in bare and not m2 and
              "**Open action items**" in bare and "Jacob Thomas" in bare, bare)

        # matching rules
        same_series = st.previous_meeting_notes(T, ts(2026, 12, 1), join_url="https://join/other")
        by_title = st.previous_meeting_notes(T, ts(2026, 12, 1), title="FU: Riverside pilot quote discussion")
        future = st.previous_meeting_notes(T, ts(2026, 11, 19), thread_root=ROOT_ID)
        check("follows-on rules: same Teams meeting > same thread > same title ('Follow-up:'/'FU:' ignored); "
              "only meetings held before", same_series["title"] == "Leadership sync" and
              by_title["title"] == prev_title and future is None)

        # ---------------------------------------------------------------- the job at T-15
        poster = Poster()
        runner = JobRunner(st, clock, followups.handlers(st, clock, poster))
        n = followups.schedule_meeting_reminders(st, T, [{**{k: v for k, v in p.items() if k != "label"},
                                                         "start": "2026-11-24 10:45"}], clock)
        job = next(j for j in st.jobs(T) if j["kind"] == "remind_meeting" and '"15m"' in j["payload"])
        payload = json.loads(job["payload"])
        check("the 15-minute reminder job carries the attendees and agenda", n == 1 and payload["agenda"] ==
              "Check the signed quote." and len(payload["attendees"]) == 4, payload)
        clock.set(datetime(2026, 11, 24, 10, 30, 5, tzinfo=UTC))
        await runner.tick()
        post = poster.posts[-1] if poster.posts else {}
        check("at T-15 the brief is posted in the meeting's thread with the @mentions",
              post.get("root") == ROOT_ID and post.get("text", "").startswith("🗒️ **Meeting brief") and
              len(post.get("mentions", [])) == 3, post.get("text", "")[:80])

        # ---------------------------------------------------------------- notes are stored for next time
        class App:
            async def send(self, conv, text, service_url=None):
                return type("S", (), {"id": "n1"})()

        class KB:
            store = st

            def prompt_text(self):
                return ""

            def add_message(self, *a):
                pass
        call = MeetingCall(App(), None, T, KB(), f"19:c;messageid={ROOT_ID}", "svc", "Follow-up: Riverside pilot quote discussion",
                           lambda c: None, clock=clock)
        call.join_url, call.recording = "https://join/new", True
        call.session.transcript = [("Karthi M", "a"), ("Daniel", "b")]
        call.session.summarize = lambda: {"summary": "s", "decisions": ["Quote signed"], "action_items": [],
                                          "risks": [], "final_total_k": None}
        await call.finish()
        nxt = st.previous_meeting_notes(T, ts(2026, 12, 31), join_url="https://join/new")
        check("after a meeting Max stores its notes (title, thread, Teams link, decisions) for the next brief",
              nxt and nxt["notes"]["decisions"] == ["Quote signed"] and nxt["thread_root"] == ROOT_ID, nxt)
        st.delete_team(T)
        check("deleting a team removes its stored notes too",
              st.previous_meeting_notes(T, ts(2027, 1, 1), thread_root=ROOT_ID) is None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


asyncio.run(main())
print("\nMEETING BRIEF:", "ALL PASS" if not fails else f"{fails} FAILED")
sys.exit(1 if fails else 0)
