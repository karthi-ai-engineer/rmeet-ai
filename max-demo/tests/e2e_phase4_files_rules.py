"""
Phase 4 step 4.6 end-to-end: Max saves a NEW file to the channel (approval card, admin site grant) and the
deadline-slip rule (a team member says a deadline moves -> date-change card -> owner confirms -> task + reminders
move). Uses ~8-12 Gemini requests.   needs: simulator (:8100) + Max (:3978, MAX_TEST_HOOKS=1, agent on)
"""

import time

from e2e_lib import (SIM, TEAM_ID, check, channel, finish, gemini_requests, http, max_hook, max_state, post, wait_for,
                     wait_ready)

wait_ready()
http("POST", SIM + "/api/channel/reset", {})
time.sleep(2)
http("POST", SIM + "/api/admin", {"consent": True, "accessPolicy": True, "transcriptApiAccess": True, "siteGrant": True})
http("POST", SIM + "/api/channel/install", {"action": "add"})
welcome, _ = wait_for(lambda: next((p for p in channel()["posts"] if p["isBot"]), None), 120)
check("Max installed (consent + Sites.Selected write grant on the team site)", welcome)
time.sleep(3)
g0 = gemini_requests()


def thread(root):
    return next((p.get("replies", []) for p in channel()["posts"] if p["id"] == root), [])


def cards_in(root):
    return [r for r in thread(root) if r["isBot"] and r.get("cards")]


def approve(msg, who):
    data = next(a["data"] for a in msg["cards"][0]["actions"] if a["verb"] == "approve")
    return http("POST", SIM + "/api/channel/card-action", {"messageId": msg["id"], "verb": "approve", "data": data,
                                                           "inputs": {}, "as": who})


# ------------------------------------------------------------------ 1. Max saves a new file (approval)
root = post("@Max please write a short markdown file named 'H1 landing actions summary.md' with a table of the "
            "three H1 landing actions and their H1 revenue impact, and save it in the channel files")["id"]
msg, dt = wait_for(lambda: (cards_in(root) or [None])[0], 150, 1)
check("an upload approval card appears", msg is not None, f"{dt:.0f}s")
if msg:
    facts = {f["title"]: f["value"] for b in msg["cards"][0]["body"] if b["type"] == "FactSet" for f in b["facts"]}
    shown = " ".join(b.get("text", "") for b in msg["cards"][0]["body"] if b["type"] == "TextBlock")
    print("    card:", facts)
    check("card: the new file name, 'overwrites nothing', and the table content itself",
          facts.get("File", "").lower().endswith(".md") and "nothing" in facts.get("Overwrites", "") and "|" in shown, facts)
    check("not saved before approval", not any(f["name"] == facts.get("File") for f in channel()["files"]))
    s, r = approve(msg, "karthi")
    f, dt = wait_for(lambda: next((f for f in channel()["files"] if f["name"] == facts.get("File")), None), 60, 1)
    check("approved: the file is in the channel files, saved by Max", f and f["author"] == "max", f)
    done, _ = wait_for(lambda: next((r for r in thread(root) if r["isBot"] and not r.get("cards")), None), 60, 1)
    check("Max confirms it saved the file (not 'a card is coming')", done and "card" not in done["text"].lower(),
          (done or {}).get("text", "")[:160])

# ------------------------------------------------------------------ 2. deadline-slip rule
root2 = post("Notes from today's memory sync with Purchasing")["id"]
s, r = max_hook("POST", "/test/notes", {"teamId": TEAM_ID, "title": "Memory sync", "root": root2, "notes": {
    "action_items": [{"owner": "Daniel", "task": "Send Sarah the monthly split for the 70% memory commitment",
                      "due": "2026-11-25"}]}})
tid = (r.get("taskIds") or [None])[0]
check("a task for Daniel exists (due 2026-11-25)", tid is not None)
def rule_runs() -> int:
    return sum(r["trigger"] == "deadline-rule" for r in max_state()["runs"])


before = rule_runs()
http("POST", SIM + "/api/channel/post", {"text": "Thanks! See you all on Friday.", "rootId": root2, "as": "daniel"})
time.sleep(6)
check("a friendly message with a date but no 'slip' words starts no AI run (code gate)", rule_runs() == before)

http("POST", SIM + "/api/channel/post", {"text": "Quick heads-up: I need till Friday 27 Nov for the monthly split, "
                                                 "Sarah is at Ayase all week.", "rootId": root2, "as": "daniel"})
msg2, dt = wait_for(lambda: (cards_in(root2) or [None])[0], 120, 1)
check("Max noticed the slip and posted a date-change card in the thread", msg2 is not None, f"{dt:.0f}s")
if msg2:
    facts = {f["title"]: f["value"] for b in msg2["cards"][0]["body"] if b["type"] == "FactSet" for f in b["facts"]}
    print("    card:", facts)
    check("card: Daniel's task, 2026-11-25 → 2026-11-27", facts.get("Due") == "2026-11-25 → 2026-11-27", facts)
    s, r = approve(msg2, "jacob")
    check("Jacob can't confirm Daniel's deadline", "Only Daniel" in r.get("message", ""), r)
    approve(msg2, "daniel")
    t, _ = wait_for(lambda: next((t for t in max_state()["tasks"] if t["id"] == tid and t["due"] == "2026-11-27"), None),
                    60, 1)
    check("Daniel confirmed: the task is now due 2026-11-27 and its reminders moved",
          t and any(j["dedupe_key"] and j["dedupe_key"].endswith("2026-11-27") and j["status"] == "pending"
                    for j in max_state()["jobs"]))

print(f"\n  Gemini requests used: {gemini_requests() - g0}")
finish("PHASE 4.6 FILES + RULES")
