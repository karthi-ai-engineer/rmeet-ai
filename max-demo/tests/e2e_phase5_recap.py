"""
Phase 5.3 end-to-end: the end-of-meeting check. Max joins a meeting it booked; people agree things; "OK, let's wrap
up" -> Max reads back the draft decisions + action items in the meeting chat and asks what's missing; Daniel corrects
her date; Max confirms; the final notes and tasks use the correction, dates come from the meeting's real day
("tomorrow"), and Max owns no task. Uses ~6-8 Gemini requests.
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


def bot_texts(root):
    return [r["text"] for r in thread(root) if r["isBot"] and not r.get("cards")]


def calendar(user):
    return http("GET", f"{SIM}/api/calendar?user={user}")[1]["events"]


def say(key, who, text, pause=2.0):
    http("POST", SIM + "/api/calendar/say", {"key": key, "as": who, "text": text})
    time.sleep(pause)


# ------------------------------------------------------------------ 0. a meeting Max booked, Max joins
# calendar.yaml: Daniel is at Ayase on Tue 1 Dec until 13:00, so the meeting lands at 13:00 on Tue 1 Dec.
root = post("@Max please set up 30 minutes on Tuesday 1 Dec with Daniel and Jacob about the Q1 memory "
            "commitment, at the earliest time we're all free")["id"]
msg, _ = wait_for(lambda: next((r for r in thread(root) if r["isBot"] and r.get("cards")), None), 150, 1)
data = msg and next(a["data"] for a in msg["cards"][0]["actions"] if a["verb"] == "approve")
msg and http("POST", SIM + "/api/channel/card-action", {"messageId": msg["id"], "verb": "approve", "data": data,
                                                        "inputs": {}, "as": "karthi"})
ev, _ = wait_for(lambda: next((e for e in calendar("daniel") if e["createdByMax"]), None), 60, 1)
check("meeting booked by Max (its chat = this thread)", ev and ev["threadRoot"] == root)
if not ev:
    finish("PHASE 5.3 END-OF-MEETING CHECK")
http("POST", SIM + "/api/calendar/start", {"key": ev["key"], "as": "karthi"})
start = datetime.fromisoformat(ev["start"].replace("Z", "+00:00"))
max_hook("POST", "/test/clock", {"now": (start - timedelta(seconds=20)).isoformat()})
max_hook("POST", "/test/jobs/run")
joined, _ = wait_for(lambda: http("GET", SIM + "/api/calendar/live")[1].get("botInCall") or None, 60, 1)
check("Max joined its meeting (Tue 1 Dec)", joined)
time.sleep(3)
n0 = len(bot_texts(root))

# ------------------------------------------------------------------ 1. the meeting
for who, line in (("karthi", "Thanks for joining. Sarah confirmed the supplier accepts 84,000 DIMMs at plus 14%."),
                  ("daniel", "The signature deadline is still 4 December."),
                  ("karthi", "Decision: we commit 70% of the Q1 memory need."),
                  ("karthi", "Daniel, please confirm the order with Sarah in writing by Thursday the 3rd."),
                  ("jacob", "I'll update the January price list by Wednesday."),
                  ("karthi", "And I'll send the decisions to Robert tomorrow.")):
    say(ev["key"], who, line)
check("no recap while the meeting is going on", not [t for t in bot_texts(root)[n0:] if "📋" in t])

# ------------------------------------------------------------------ 2. wrap up -> draft read back
say(ev["key"], "karthi", "OK, let's wrap up.", pause=0)
draft, dt = wait_for(lambda: next((t for t in bot_texts(root)[n0:] if t.startswith("**📋")), None), 90, 1)
check("'let's wrap up' -> Max posts the draft notes in the meeting chat", draft, f"{dt:.0f}s")
print("   ", (draft or "").replace("\n", " | ")[:400])
check("draft: the 70% memory decision and Daniel's, Jacob's and Karthi's action items, and asks for corrections",
      draft and ("70%" in draft or "84,000" in draft) and all(n in draft for n in ("Daniel", "Jacob Thomas", "Karthi M"))
      and "missing or wrong" in draft)
# The draft writes due dates as "%a %d %b" (zero-padded day), so Wed 2 Dec shows as "Wed 02 Dec".
check("dates come from the meeting's real day: 'Wednesday' = Wed 2 Dec, 'tomorrow' = Wed 2 Dec",
      draft and "Jacob Thomas: " in draft and "Wed 02 Dec" in draft.split("Jacob Thomas: ")[1].split("\n")[0]
      and "Wed 02 Dec" in draft.split("Karthi M: ")[1].split("\n")[0], draft)
check("Max owns no action item in the draft", draft and "- Max" not in draft)

# ------------------------------------------------------------------ 3. a correction
n1 = len(bot_texts(root))
say(ev["key"], "daniel", "Max, one correction: my confirmation is due Friday the 4th, not the 3rd.", pause=0)
# single-digit day: look for the 4th as a date, not just any "4"
ack, dt = wait_for(lambda: next((t for t in bot_texts(root)[n1:] if any(x in t for x in ("4 Dec", "Dec 4", "04 Dec", "4th",
                                                                                          "12-04", "December 4"))), None), 60, 1)
check("Max confirms the correction in one sentence", ack, ack)
say(ev["key"], "karthi", "Great, thanks everyone.")
http("POST", SIM + "/api/calendar/end", {"key": ev["key"]})
notes, dt = wait_for(lambda: next((t for t in bot_texts(root) if t.lstrip("* ").startswith("📝 Meeting notes")), None), 120, 2)
check("final notes posted", notes, f"{dt:.0f}s")
check("final notes say the decisions were read back and corrections are included",
      notes and "read the decisions and action items back" in notes)
tasks = {t["owner"]: t["due"] for t in max_state()["tasks"]}
print("    tasks:", tasks)
check("the correction is in the tasks: Daniel's confirmation due 2026-12-04 (not the 3rd)",
      tasks.get("Daniel") == "2026-12-04", tasks)
check("Jacob's price list due Wed 2026-12-02; Karthi's 'tomorrow' = 2026-12-02 (the meeting's real date)",
      tasks.get("Jacob Thomas") == "2026-12-02" and tasks.get("Karthi M") == "2026-12-02", tasks)
check("no task for Max", not any(o and o.lower().startswith("max") for o in tasks), tasks)
max_hook("POST", "/test/clock", {"reset": True})

print(f"\n  Gemini requests used: {gemini_requests() - g0}")
finish("PHASE 5.3 END-OF-MEETING CHECK")
