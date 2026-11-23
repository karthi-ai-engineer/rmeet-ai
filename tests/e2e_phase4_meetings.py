"""
Phase 4 step 4.5 end-to-end: Max books a Teams meeting (free/busy + approval card), the invite lands in everyone's
calendar, Max joins its own meeting when it starts, answers in it, and posts notes + tasks back in the thread.
Uses ~6-10 Gemini requests.   needs: simulator (:8100) + Max (:3978, MAX_TEST_HOOKS=1, agent on)
"""

import time
from datetime import datetime, timedelta

from e2e_lib import (SIM, check, channel, finish, gemini_requests, http, max_hook, max_state, post, wait_for,
                     wait_ready)

wait_ready()
http("POST", SIM + "/api/channel/reset", {})
time.sleep(2)
http("POST", SIM + "/api/admin", {"consent": True, "accessPolicy": True, "transcriptApiAccess": True})
http("POST", SIM + "/api/channel/install", {"action": "add"})
welcome, _ = wait_for(lambda: next((p for p in channel()["posts"] if p["isBot"]), None), 120)
check("Max installed (fresh channel, consent incl. Calendars.ReadWrite)", welcome)
time.sleep(3)
g0 = gemini_requests()


def thread(root):
    return next((p.get("replies", []) for p in channel()["posts"] if p["id"] == root), [])


def card_msg(root):
    return next((r for r in thread(root) if r["isBot"] and r.get("cards")), None)


def calendar(user):
    return http("GET", f"{SIM}/api/calendar?user={user}")[1]["events"]


# ------------------------------------------------------------------ 1. book with free/busy + card
root = post("@Max please set up 30 minutes on Tuesday 24 Nov with Prince and Daniel about the Riverside pilot "
            "quote, at the earliest time we're all free")["id"]
msg, dt = wait_for(lambda: card_msg(root), 150, 1)
check("a meeting approval card appears in the thread", msg is not None, f"{dt:.0f}s")
if not msg:
    finish("PHASE 4.5 MEETINGS")
facts = {f["title"]: f["value"] for b in msg["cards"][0]["body"] if b["type"] == "FactSet" for f in b["facts"]}
print("    card:", facts)
check("card: Tue 24 Nov at 10:30 (first slot all three are free), Max organizer, Karthi + Prince + Daniel",
      "24 Nov 2026 10:30" in facts.get("When", "") and facts.get("Organizer", "").startswith("Max (AI)") and
      all(n in facts.get("Attendees", "") for n in ("Karthi M", "Prince Alex", "Daniel")), facts)
check("nothing in Prince's calendar yet", not [e for e in calendar("prince") if e["createdByMax"]])

data = next(a["data"] for a in msg["cards"][0]["actions"] if a["verb"] == "approve")
s, r = http("POST", SIM + "/api/channel/card-action", {"messageId": msg["id"], "verb": "approve", "data": data,
                                                       "inputs": {}, "as": "karthi"})
check("Karthi approves", s == 200 and "Sending" in r.get("card", {}).get("body", [{}])[0].get("text", ""), r)
ev, _ = wait_for(lambda: next((e for e in calendar("prince") if e["createdByMax"]), None), 60, 1)
check("the meeting is in Prince's calendar: Teams meeting, booked by Max, 10:30–11:00",
      ev and ev["online"] and ev["start"].startswith("2026-11-24T10:30") and ev["end"].startswith("2026-11-24T11:00"), ev)
check("…and in Daniel's and Karthi's calendars", ev and any(e["key"] == ev["key"] for e in calendar("daniel"))
      and any(e["key"] == ev["key"] for e in calendar("karthi")))
jobs = [j for j in max_state()["jobs"] if j["status"] == "pending"]
check("Max planned reminders (24 h, 15 min) and joining its own meeting",
      sum(j["kind"] == "remind_meeting" for j in jobs) == 2 and any(j["kind"] == "join_own_meeting" for j in jobs))

# ------------------------------------------------------------------ 2. the meeting starts: Max joins by itself
s, r = http("POST", SIM + "/api/calendar/start", {"key": ev["key"], "as": "karthi"})
check("Karthi starts the meeting from the calendar", s == 200, r)
start = datetime.fromisoformat(ev["start"].replace("Z", "+00:00"))
max_hook("POST", "/test/clock", {"now": (start - timedelta(seconds=20)).isoformat()})
max_hook("POST", "/test/jobs/run")
joined, dt = wait_for(lambda: next((e for e in calendar("karthi") if e["key"] == ev["key"] and e["botInCall"]), None), 60, 1)
check("Max joined its own meeting at the start time (no meetingStart event needed)", joined, f"{dt:.0f}s")

# ------------------------------------------------------------------ 3. talk in the meeting, then end it
time.sleep(3)
for who, line in (("karthi", "Thanks for joining. Today we check the Riverside pilot quote from Vector Robotics."),
                  ("daniel", "Vector's Riverside quote is 200K, same as in the proposal."),
                  ("karthi", "Max, what lead time did LiftLine give us?")):
    http("POST", SIM + "/api/calendar/say", {"key": ev["key"], "as": who, "text": line})
    time.sleep(2)
ans, dt = wait_for(lambda: next((r for r in thread(root) if r["isBot"] and "14" in r["text"] and not r.get("cards")), None),
                   90, 2)
check("Max answered the question in the meeting (in the thread, text mode): LiftLine 14 weeks", ans, f"{dt:.0f}s")
http("POST", SIM + "/api/calendar/say", {"key": ev["key"], "as": "karthi",
                                         "text": "Decision: we go with Vector. Prince, please send the updated budget v3 by 2026-11-26."})
time.sleep(3)
http("POST", SIM + "/api/calendar/end", {"key": ev["key"]})
notes, dt = wait_for(lambda: next((r for r in thread(root) if r["isBot"] and r["text"].lstrip("* ").startswith("📝 Meeting notes")), None),
                     120, 2)
check("after the meeting, Max posted the notes back in the same thread", notes, f"{dt:.0f}s")
task = next((t for t in max_state()["tasks"] if t["owner"] == "Prince Alex"), None)
check("the action item became a task for Prince Alex with its due date", task and task["due"] == "2026-11-26", task)
max_hook("POST", "/test/clock", {"reset": True})

print(f"\n  Gemini requests used: {gemini_requests() - g0}")
finish("PHASE 4.5 MEETINGS")
