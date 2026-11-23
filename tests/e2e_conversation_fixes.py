"""
Live check of Karthi's channel conversation (22 Nov 2026):
  "@Max book a meeting tomorrow 11 am" (11:00 busy) -> Max asked in chat and invited people nobody named;
  then a NEW post "@Max yes go ahead" -> Max claimed "I have noted your approval…" without doing anything.
Now: an approval card at the nearest free time with a calendar-checked note why, only the people named; "yes go
ahead" as a new post -> Max points to the card (approving is a click); a lone "yes" with nothing to refer to ->
Max asks what is meant, never claims anything. Uses ~5-7 Gemini requests.
"""

import time

from e2e_lib import SIM, channel, check, ensure_installed, finish, gemini_requests, http, post, wait_for, wait_ready

wait_ready()
ensure_installed(fresh=True)
http("POST", SIM + "/api/admin", {"consent": True, "accessPolicy": True, "transcriptApiAccess": True})
time.sleep(4)
g0 = gemini_requests()


def replies(root):
    return next((p.get("replies", []) for p in channel()["posts"] if p["id"] == root), [])


def first_bot(root):
    return wait_for(lambda: next((r for r in replies(root) if r["isBot"]), None), 120, 1)[0]


def facts(msg):
    return {f["title"]: f["value"] for b in msg["cards"][0]["body"] if b["type"] == "FactSet" for f in b["facts"]}


def note(msg):
    return next((b["text"] for b in msg["cards"][0]["body"] if b.get("text", "").startswith("💡")), "")


# 1. a lone "yes" with nothing to refer to: Max asks, claims nothing
a0 = post("@Max yes go ahead")["id"]
r0 = first_bot(a0)
check("a lone 'yes go ahead' -> Max asks what is meant (no claim, no card)",
      r0 and not r0.get("cards") and "?" in r0["text"] and not any(w in r0["text"].lower() for w in
                                                                   ("noted your approval", "i will proceed", "i have scheduled")),
      r0 and r0["text"])

# 2. book at a busy time: card at the nearest free time, with a calendar-checked note; only Prince invited
a = post("@Max book a meeting tomorrow 11 am with Prince about the budget")["id"]
r1 = first_bot(a)
check("booking -> an approval card right away (no question in chat)", r1 and r1.get("cards"), r1 and r1["text"][:200])
if r1 and r1.get("cards"):
    f = facts(r1)
    print("    card:", {k: f[k] for k in ("Title", "When", "Attendees") if k in f}, "|", note(r1))
    check("only the people named are invited (Karthi + Prince), nobody else",
          "Prince Alex" in f.get("Attendees", "") and not any(n in f.get("Attendees", "") for n in ("Daniel", "Jacob")), f)
    at_11 = "11:00" in f.get("When", "")
    check("asked time free -> booked at 11:00; busy -> another time WITH a note saying who is busy at 11:00",
          at_11 or note(r1).startswith("💡 You asked for") and "11:00" in note(r1), (f.get("When"), note(r1)))

# 3. "yes go ahead" as a NEW post: Max points to the card, makes no second card
time.sleep(2)
b = post("@Max yes go ahead")["id"]
r2 = first_bot(b)
check("'yes go ahead' as a new post -> Max says to press Approve on the card; no second card",
      r2 and not r2.get("cards") and "approve" in r2["text"].lower() and
      not [x for x in replies(b) if x.get("cards")], r2 and r2["text"])

print(f"\n  Gemini requests used: {gemini_requests() - g0}")
finish("CONVERSATION FIXES")
