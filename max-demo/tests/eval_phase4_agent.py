"""
Phase 4 step 4.3 live eval: Max answers @mentions with the LangGraph agent (search tools, not the whole memory).
Deterministic fact checks on the Thirdwave Business Planning world; prints model calls, tokens and $ per question.

  needs: simulator (:8100) + Max (:3978, MAX_TEST_HOOKS=1, agent on). Uses ~15-25 Gemini requests.
"""

import re
import sys
import time

from e2e_lib import (SIM, TEAM_ID, check, channel, finish, gemini_requests, http, max_state, post, wait_for,
                     wait_ready)

wait_ready()
# Clean channel, full admin access (calendars, meetings, transcripts) BEFORE install, so the pre-read has it all.
http("POST", SIM + "/api/channel/reset", {})
time.sleep(2)
http("POST", SIM + "/api/admin", {"consent": True, "accessPolicy": True, "transcriptApiAccess": True})
http("POST", SIM + "/api/channel/install", {"action": "add"})
welcome, dt = wait_for(lambda: next((p for p in channel()["posts"] if p["isBot"]), None), 120)
check("Max installed and pre-read the channel (with meetings + transcripts)",
      welcome and "official transcripts" in welcome["text"], f"{dt:.0f}s")
time.sleep(2)
g0 = gemini_requests()


def ask(text: str, root: str | None = None, timeout: float = 90):
    q = post(text, root)
    rid = root or q["id"]
    seen = {r["id"] for p in channel()["posts"] if p["id"] == rid for r in p.get("replies", [])}

    def reply():
        for p in channel()["posts"]:
            if p["id"] == rid:
                return next((r for r in p.get("replies", []) if r["isBot"] and r["id"] not in seen), None)
    r, dt = wait_for(reply, timeout, 1)
    run = next((x for x in max_state()["runs"] if x["thread_id"] == rid and x["trigger"] == "mention"), None)
    return (r or {}).get("text", ""), dt, run


rows = []
SKIP = int(sys.argv[sys.argv.index("--skip") + 1]) if "--skip" in sys.argv else 0   # re-run only the later ones
asked = [0]


def q(name: str, text: str, ok_fn, root: str | None = None):
    asked[0] += 1
    if asked[0] <= SKIP:
        print(f"SKIP {name}")
        return ""
    ans, dt, run = ask(text, root)
    calls, tokens, cost = (run or {}).get("model_calls", 0), (run or {}).get("tokens", 0), (run or {}).get("cost_usd", 0)
    rows.append((name, calls, tokens, cost, dt))
    check(name, ans and ok_fn(ans.lower()), f"{dt:.0f}s, {calls} calls, {tokens} tok | {ans[:170]}")
    return ans


q("gap in landing v1 + Prince's landing actions", "@Max quick check before the decision meeting: what is the gap in H1 "
  "landing v1, and which three landing actions did Prince find to close it?",
  lambda a: "2.5" in a and all(x in a for x in ("0.24", "0.45", "0.21")))
seed = next(p for p in channel()["posts"] if p["author"] == "daniel" and "84,000" in p["text"])
q("memory option (b) under the charter rule (reply in an existing thread)", "@Max does option (b) need Karthi's sign-off "
  "under the charter's decision rights, and how much would it commit?", lambda a: "0.98" in a or "980" in a,
  root=seed["id"])
q("transcript attribution (4 Nov, Prince)", "@Max in the 4 Nov meeting transcript, who asked whether Friday the "
  "thirteenth is a good date for a sale?", lambda a: "prince" in a)
q("transcript attribution (20 Oct, Karthi)", "@Max according to the 20 Oct meeting transcript, who said 'Somebody will "
  "queue from the thirty-first with a sleeping bag' about the lucky bags?",
  lambda a: ("karthi" in a.split(",", 1)[-1] or "you" in a) and not re.search(r"\bren\b", a.split(",", 1)[-1]))
q("tender meeting date + GPU count", "@Max when did Tom present the PREF-AI-27 tender to us, and how many GPUs "
  "does it need?", lambda a: "17" in a and "nov" in a and "160" in a)
q("create a task by chat", "@Max please create a task for Daniel: send Sarah the monthly split for the 70% memory "
  "commitment, due 2026-11-27", lambda a: "daniel" in a)
task = next((t for t in max_state()["tasks"] if t["owner"] == "Daniel" and t["due"] == "2026-11-27"), None)
check("the task exists with owner Daniel, due 2026-11-27, reminders planned",
      task and any(f'"taskId": {task["id"]}' in j["payload"] for j in max_state()["jobs"]), task and task["title"])
q("list someone's open tasks", "@Max what open tasks does Daniel have?", lambda a: "memory" in a and "split" in a)

used = gemini_requests() - g0
print("\n  question                                              calls  tokens   $paid   secs")
for name, calls, tokens, cost, dt in rows:
    print(f"  {name[:52]:52} {calls:>5} {tokens:>7} {cost:>7.4f} {dt:>6.0f}")
print(f"  {'TOTAL':52} {sum(r[1] for r in rows):>5} {sum(r[2] for r in rows):>7} {sum(r[3] for r in rows):>7.4f}")
print(f"  Gemini requests (meter): {used}")
finish("PHASE 4.3 AGENT EVAL")
