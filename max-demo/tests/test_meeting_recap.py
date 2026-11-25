"""
Phase 5.3 offline tests: the end-of-meeting check. When the meeting wraps up (or someone asks), Max reads back the
draft decisions and action items and asks what's missing; corrections go into the final notes. Also: notes use the
meeting's real date and Max never owns a task. Real MeetingCall (fake Teams app), real database, no model calls. $0.
  .venv\\Scripts\\python tests\\test_meeting_recap.py
"""

import asyncio
import json
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "max"))

import brain  # noqa: E402
import followups  # noqa: E402
import meeting_actions as ma  # noqa: E402
from agent.clock import FakeClock  # noqa: E402
from calling import MeetingCall  # noqa: E402
from store import Store  # noqa: E402

fails = 0
T, CONV = "T1", "19:chan@thread.tacv2;messageid=1795300000001"


def check(name: str, ok, detail="") -> None:
    global fails
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f"  [{detail}]" if detail != "" else ""))


class Sent:
    def __init__(self, i):
        self.id = f"msg{i}"


class FakeApp:
    def __init__(self):
        self.sent = []

    async def send(self, conversation_id, text, service_url=None):
        self.sent.append(text)
        return Sent(len(self.sent))


class FakeKB:
    def __init__(self, store):
        self.store = store

    def prompt_text(self):
        return "CHANNEL KNOWLEDGE: (test)"

    def add_message(self, *a):
        pass


async def drain() -> None:
    for _ in range(80):
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if not tasks:
            return
        await asyncio.gather(*tasks)


NOTES = {"summary": "We agreed the Riverside pilot.", "decisions": ["Go with Vector for the Riverside pilot (200K)."],
         "action_items": [{"owner": "Daniel", "task": "Confirm the Riverside quote", "due": "2026-11-26"},
                          {"owner": "Prince Alex", "task": "Send budget v3", "due": "2026-11-24"}],
         "risks": [], "final_total_k": None}


# ------------------------------------------------------------------ 1. triggers (pure)
def test_triggers() -> None:
    closes = ["OK, let's wrap up.", "Let's wrap this up, thanks everyone.", "Before we finish, anything else?",
              "That's all for today.", "Any other business?", "Alright, let's close here.", "To wrap up:",
              "I think we can end the meeting now", "Before we go, quick check."]
    not_closes = ["Okay, let's go with A, B and C. That closes the 220.", "Let's close the 220K gap first.",
                  "We need to finish the budget by Tuesday.", "Max, please post the summary.",
                  "That's all I have on the pilot.", "Before we lock that in, Max, what's the risk with option B?",
                  "The pilot ends in May."]
    asks = ["Max, can you recap?", "Max, what did we decide?", "Max, read back the action items please",
            "Max, go over the decisions", "Max, summarise where we are", "Max, let's wrap up"]
    wrong = ([c for c in closes if not ma.wants_recap(c, bool(re.search(r"\bmax\b", c, re.I)), 0, 10)] +
             [c for c in not_closes if ma.wants_recap(c, bool(re.search(r"\bmax\b", c, re.I)), 0, 10)] +
             [a for a in asks if not ma.wants_recap(a, True, 3, 2)])
    check(f"triggers: {len(closes)} ways of closing a meeting, {len(asks)} ways of asking Max (any time); "
          f"{len(not_closes)} look-alikes don't trigger", not wrong, wrong)
    check("closing words trigger the automatic recap only once, and not in a meeting that barely started",
          not ma.wants_recap("OK, let's wrap up.", False, 1, 20) and not ma.wants_recap("Let's wrap up.", False, 0, 3))
    check("'Max, email Elena the recap' is an action (agent), not a read-back",
          ma.wants_action("Max, email Elena the recap of what we decided"))


def test_recap_text() -> None:
    spoken, draft = brain.recap_text(NOTES)
    check("spoken recap: counts, decisions, each owner + task + spoken date, asks for corrections",
          spoken == ("Before we finish, here's what I have: 1 decision and 2 action items. Decisions: Go with Vector "
                     "for the Riverside pilot (200K). Actions: Daniel, confirm the Riverside quote by Thursday 26 "
                     "November; Prince Alex, send budget v3 by Tuesday 24 November. Is anything missing or wrong?"), spoken)
    check("chat draft: heading, Decisions, Action items with dates, how to correct",
          draft.startswith("**📋 Before we finish: draft notes**") and "- Daniel: Confirm the Riverside quote by Thu 26 Nov"
          in draft and "Max, that date is the 27th" in draft, draft)
    empty = brain.recap_text({"decisions": [], "action_items": []})
    check("nothing noted yet -> Max says so and asks what to add",
          "haven't noted any decisions or action items" in empty[0] and "(none yet)" in empty[1])
    check("Max is never an action-item owner ('Max', 'Max (AI)'); people named Max-something are",
          brain.is_max("Max") and brain.is_max("max (AI) ") and not brain.is_max("Maxine Lee") and not brain.is_max("Prince"))


# ------------------------------------------------------------------ 2-6. in the call
async def main() -> None:
    test_triggers()
    test_recap_text()
    tmp = Path(tempfile.mkdtemp())
    try:
        st = Store(tmp / "max.db")
        st.replace_team_content({"teamId": T, "teamName": "Planning", "channelId": "C", "driveId": "D", "posts": [],
                                 "files": [], "meetings": [], "timeZone": "Asia/Kolkata"})
        for name, aad, kind in (("Karthi M", "aad-k", "person"), ("Daniel", "aad-d", "person"),
                                ("Prince Alex", "aad-p", "person"), ("Max", "bot-max", "bot")):
            st.touch_person(T, name, aad, kind)
        # 22 Nov 2026 20:00 UTC = 23 Nov 01:30 in Kolkata: the meeting's date is the TEAM's date
        clock = FakeClock(datetime(2026, 11, 22, 20, 0, tzinfo=timezone.utc))

        def new_call(audio=False):
            app = FakeApp()
            call = MeetingCall(app, None, T, FakeKB(st), CONV, "https://svc", "Riverside quote", lambda c: None,
                               clock=clock)
            call.audio_mode = audio
            call.roster = {"1": {"name": "Karthi M", "id": "aad-k"}, "2": {"name": "Daniel", "id": "aad-d"}}
            return call, app

        async def hear(call, msi, text):
            who = call.roster[str(msi)]
            await call._on_control({"t": "transcript", "msi": msi, "text": text,
                                    "speaker": {"displayName": who["name"], "id": who["id"]}})
            await drain()

        # ---------------------------------------------------------------- 2. the meeting date
        call, app = new_call()
        check("notes use the meeting's real date in the team's time zone (not a fixed scenario date)",
              call.session.today_iso == "2026-11-23" and call.session.today == "Monday 23 Nov 2026",
              (call.session.today, call.session.today_iso))
        seen = []
        orig = brain.qwen_chat

        def fake_chat(messages, **kw):
            seen.append(messages[-1]["content"])
            return json.dumps({**NOTES, "action_items": NOTES["action_items"] +
                               [{"owner": "Max", "task": "Email Elena the update", "due": "2026-11-23"}]})
        brain.qwen_chat = fake_chat
        try:
            notes = call.session.summarize()
        finally:
            brain.qwen_chat = orig
        check("notes prompt: real date, Max never an owner, corrections after the recap win",
              "Today is 2026-11-23" in seen[0] and "Max (the AI) is never an owner" in seen[0]
              and "corrections after it are the truth" in seen[0])
        check("an action item the model gave to Max is dropped from the notes",
              [a["owner"] for a in notes["action_items"]] == ["Daniel", "Prince Alex"], notes["action_items"])

        # ---------------------------------------------------------------- 3. wrap-up -> recap once (text call)
        call, app = new_call()
        calls = []
        call.session.summarize = lambda: calls.append(1) or json.loads(json.dumps(NOTES))
        call.session.answer = lambda: "In the 20 October meeting."
        for i, line in enumerate(["Morning all.", "Vector confirmed 200K.", "Go-live is 1 May.", "Good, we go with Vector.",
                                  "Daniel, please confirm the quote by the 26th.", "Prince, budget v3 by Tuesday."]):
            await hear(call, 1 + i % 2, line)
        check("no recap during the meeting", calls == [] and app.sent == [])
        await hear(call, 1, "OK, let's wrap up.")
        check("'let's wrap up' -> Max posts the draft notes in the meeting chat (one model call)",
              calls == [1] and len(app.sent) == 1 and app.sent[0].startswith("**📋 Before we finish: draft notes**"), app.sent)
        check("the spoken recap is in the transcript (so the final notes know what was read back)",
              call.session.transcript[-1][0] == "Max" and call.session.transcript[-1][1].startswith("Before we finish"))
        await hear(call, 2, "Before we finish, my date is the 27th, not the 26th.")
        check("closing words again -> no second automatic recap", calls == [1] and len(app.sent) == 1, len(app.sent))
        await hear(call, 1, "Max, can you recap again?")
        check("asking Max -> it reads back again (with the correction now in the transcript)",
              calls == [1, 1] and len(app.sent) == 2 and call.recaps == 2)
        await hear(call, 1, "Max, what lead time did LiftLine give us?")
        check("questions still get the normal answer after a recap", app.sent[-1] == "In the 20 October meeting.")

        # ---------------------------------------------------------------- 4. busy -> the recap waits
        call, app = new_call()
        call.session.summarize = lambda: json.loads(json.dumps(NOTES))
        gate = asyncio.Event()

        async def slow_answer():
            await gate.wait()
            await call._chat("answer")
        call._answer = slow_answer
        call.session.transcript = [("Karthi M", f"line {i}") for i in range(8)]
        await call._on_control({"t": "transcript", "msi": 1, "text": "Max, what's the gap?",
                                "speaker": {"displayName": "Karthi M", "id": "aad-k"}})
        await call._on_control({"t": "transcript", "msi": 2, "text": "Great, that's all for today.",
                                "speaker": {"displayName": "Daniel", "id": "aad-d"}})
        check("wrap-up while Max is answering: the recap waits", call.recap_waiting and app.sent == [])
        gate.set()
        await drain()
        check("…and runs right after the answer", app.sent[0] == "answer" and app.sent[1].startswith("**📋")
              and not call.answering and call.recaps == 1, app.sent)

        # ---------------------------------------------------------------- 5. voice call: spoken + chat draft
        call, app = new_call(audio=True)
        call.ws = object()
        spoken = []

        async def fake_speak(text):
            spoken.append(text)
        call._speak = fake_speak
        call.session.summarize = lambda: json.loads(json.dumps(NOTES))
        call.session.transcript = [("Karthi M", f"line {i}") for i in range(8)]
        await hear(call, 1, "Alright, before we go, Max, read back the action items please.")
        check("voice call: Max SAYS the short recap and posts the draft in the chat",
              len(spoken) == 1 and spoken[0].startswith("Before we finish") and app.sent[0].startswith("**📋"),
              (spoken, app.sent))

        # ---------------------------------------------------------------- 6. final notes + tasks
        call, app = new_call()
        call.recording, call.recaps = True, 1
        call.session.transcript = [("Karthi M", "x"), ("Daniel", "y")]
        call.session.summarize = lambda: {**json.loads(json.dumps(NOTES)), "action_items": NOTES["action_items"] +
                                          [{"owner": "Max (AI)", "task": "Email Elena", "due": "2026-11-23"}]}
        await call.finish()
        check("final notes say the decisions were read back and corrections are included",
              "I read the decisions and action items back before the end of the meeting" in app.sent[-1])
        owners = [t["owner"] for t in st.tasks(T, None)]
        check("tasks are saved for people only: none for Max (it would only remind itself)",
              sorted(owners) == ["Daniel", "Prince Alex"], owners)
        n = followups.save_meeting_tasks(st, T, {"action_items": [{"owner": "Max", "task": "Chase Daniel", "due": ""}]},
                                         "Riverside quote", "r", clock)
        check("save_meeting_tasks skips Max even when called directly", n == [])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


asyncio.run(main())
print("\nMEETING RECAP:", "ALL PASS" if not fails else f"{fails} FAILED")
sys.exit(1 if fails else 0)
