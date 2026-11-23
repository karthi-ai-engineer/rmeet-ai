"""
Phase 5.1 end-to-end: the pre-meeting brief. Max books meeting 1 and takes notes in it (decisions + action items);
a follow-up is booked in the same thread; 15 minutes before the follow-up Max posts the brief in the thread:
@mentions, agenda, what was decided last time, open action items of the people invited. The brief itself uses no
AI. Uses ~7-9 Gemini requests (two bookings + meeting 1's notes).
  needs: simulator (:8100) + Max (:3978, MAX_TEST_HOOKS=1, agent on)
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
check("Max installed (fresh channel, all consents)", welcome)
time.sleep(3)
g0 = gemini_requests()


def thread(root):
    return next((p.get("replies", []) for p in channel()["posts"] if p["id"] == root), [])


def calendar(user):
    return http("GET", f"{SIM}/api/calendar?user={user}")[1]["events"]


def book_and_approve(text, root=None, known=()):
    """Ask Max to book (in a new post or in the thread), approve the card, return the new event."""
    r = post(text, root)
    where = root or r["id"]
    seen = {m["id"] for m in thread(where) if m.get("cards")}
    msg, _ = wait_for(lambda: next((m for m in thread(where) if m["isBot"] and m.get("cards") and m["id"] not in seen),
                                   None), 150, 1)
    if not msg:
        return where, None
    data = next(a["data"] for a in msg["cards"][0]["actions"] if a["verb"] == "approve")
    http("POST", SIM + "/api/channel/card-action", {"messageId": msg["id"], "verb": "approve", "data": data,
                                                    "inputs": {}, "as": "karthi"})
    ev, _ = wait_for(lambda: next((e for e in calendar("prince") if e["createdByMax"] and e["key"] not in known), None),
                     60, 1)
    return where, ev


# ------------------------------------------------------------------ 1. meeting 1 (Max takes notes)
root, ev1 = book_and_approve("@Max please set up 30 minutes on Tuesday 24 Nov with Prince and Daniel about the "
                             "Riverside pilot quote, at the earliest time we're all free")
check("meeting 1 booked by Max", ev1)
if not ev1:
    finish("PHASE 5.1 PRE-MEETING BRIEF")
http("POST", SIM + "/api/calendar/start", {"key": ev1["key"], "as": "karthi"})
start1 = datetime.fromisoformat(ev1["start"].replace("Z", "+00:00"))
max_hook("POST", "/test/clock", {"now": (start1 - timedelta(seconds=20)).isoformat()})
max_hook("POST", "/test/jobs/run")
joined, _ = wait_for(lambda: http("GET", SIM + "/api/calendar/live")[1].get("botInCall") or None, 60, 1)
check("Max joined meeting 1", joined)
time.sleep(3)
for who, line in (("karthi", "Vector confirmed the Riverside quote at 200K."),
                  ("karthi", "Decision: we go with Vector for the Riverside pilot."),
                  ("karthi", "Daniel, please get the quote signed by Thursday the 26th."),
                  ("prince", "I'll update the budget to v3 by Wednesday.")):
    http("POST", SIM + "/api/calendar/say", {"key": ev1["key"], "as": who, "text": line})
    time.sleep(2)
http("POST", SIM + "/api/calendar/end", {"key": ev1["key"]})
notes, _ = wait_for(lambda: next((m for m in thread(root) if m["isBot"] and m["text"].lstrip("* ").startswith("📝 Meeting notes")),
                                 None), 120, 2)
check("meeting 1 notes posted (and stored for next time)", notes)

# ------------------------------------------------------------------ 2. a follow-up in the same thread
_, ev2 = book_and_approve("@Max please book a 30 minute follow-up with Prince and Daniel on Friday 27 Nov at the "
                          "earliest time we're all free. Agenda: check the signed Vector quote.", root, {ev1["key"]})
check("follow-up booked in the same thread (Fri 27 Nov)", ev2 and ev2["start"].startswith("2026-11-27") and
      ev2["threadRoot"] == root, ev2 and ev2["start"])
if not ev2:
    finish("PHASE 5.1 PRE-MEETING BRIEF")
g_before_brief = gemini_requests()
n_before = len(thread(root))

# ------------------------------------------------------------------ 3. 15 minutes before: the brief
start2 = datetime.fromisoformat(ev2["start"].replace("Z", "+00:00"))
max_hook("POST", "/test/clock", {"now": (start2 - timedelta(minutes=15) + timedelta(seconds=5)).isoformat()})
max_hook("POST", "/test/jobs/run")
brief, dt = wait_for(lambda: next((m for m in thread(root)[n_before:] if m["isBot"] and m["text"].startswith("🗒️")), None), 30, 1)
check("15 minutes before the follow-up, Max posts the brief in the meeting's thread", brief, f"{dt:.0f}s")
text = brief["text"] if brief else ""
print("   ---\n   " + text.replace("\n", "\n   ") + "\n   ---")
check("brief heading: the follow-up's title, starts in 15 minutes, join link",
      f"Meeting brief: {ev2['title']}" in text and "starts in 15 minutes" in text and "Join the meeting" in text)
check("@mentions the people invited (Karthi, Prince, Daniel), not Max",
      brief and all(any(n in str(m) for m in brief.get("mentions") or []) for n in ("Prince Alex", "Daniel")) and
      "With:" in text and "Max</at>" not in text, brief and brief.get("mentions"))
check("agenda from the invite", "**Agenda**" in text and "signed" in text.split("**Agenda**")[1].split("\n\n")[0].lower())
check("last time = meeting 1: its title and the Vector decision; 0 of its action items done yet",
      f"**Last time** ({ev1['title']}" in text and "Vector" in text.split("**Last time**")[1].split("\n\n")[0]
      and "Action items from then: 0 of 2 done" in text, text)
open_sec = text.split("**Open action items for this meeting's people**")[1].split("\n\n")[0] if "for this meeting's people" in text else ""
check("open action items of the people invited: Daniel's signed quote (overdue on Fri 27th) and Prince's v3",
      "⚠️ Daniel" in open_sec and "Prince Alex" in open_sec and "was due" in open_sec, open_sec)
check("the brief cost no Gemini requests", gemini_requests() == g_before_brief, gemini_requests() - g_before_brief)
max_hook("POST", "/test/clock", {"reset": True})

print(f"\n  Gemini requests used: {gemini_requests() - g0}")
finish("PHASE 5.1 PRE-MEETING BRIEF")
