"""
Phase 4 step 4.2 end-to-end (no model calls): meeting action items -> tasks -> Max posts reminders in the
channel thread with real @mentions, at the right time (Max's clock is moved with its test hooks).

  needs: simulator (:8100) + Max (:3978) with MAX_TEST_HOOKS=1
"""

from datetime import date, datetime, timedelta, timezone

from e2e_lib import (MAX, TEAM_ID, all_messages, check, ensure_installed, finish, gemini_requests, max_hook,
                     max_state, post, wait_for, wait_ready)

wait_ready()
ensure_installed()
g0 = gemini_requests()

state = max_state()
people = {p["name"]: p for p in state["people"]}
check("Max knows the team's people with their AAD ids (team members via Graph)",
      all(people.get(n, {}).get("aad_id") for n in ("Karthi M", "Prince Alex", "Daniel", "Jacob Thomas")),
      sorted(people))
check("the team owner is known (approver later)", people.get("Karthi M", {}).get("role") == "owner")

# A real thread to attach the tasks to (as the meeting chat would be).
root = post("E2E follow-ups: notes thread")["id"]
due = (date.today() + timedelta(days=3)).isoformat()
notes = {"action_items": [{"owner": "Prince Alex", "task": f"E2E budget v3 {root}", "due": due},
                          {"owner": "Daniel", "task": f"E2E Vector quote {root}", "due": due}]}
s, r = max_hook("POST", "/test/notes", {"teamId": TEAM_ID, "title": "E2E review", "root": root, "notes": notes})
check("notes -> 2 tasks saved", s == 200 and len(r.get("taskIds", [])) == 2, r)
ids = r.get("taskIds", [])
tasks = {t["id"]: t for t in max_state()["tasks"]}
check("task owners resolved with AAD ids", all(tasks[i]["owner_aad"] for i in ids if i in tasks))

# Move Max's clock to 09:01 (team zone, UTC here) the day before the due date and run due jobs.
d = date.fromisoformat(due) - timedelta(days=1)
max_hook("POST", "/test/clock", {"now": datetime(d.year, d.month, d.day, 9, 1, tzinfo=timezone.utc).isoformat()})
s, counts = max_hook("POST", "/test/jobs/run")      # Max's own 5 s loop may have run them already
check("job runner ran", s == 200, counts)


def reminders():
    return [m for m in all_messages() if m["isBot"] and m.get("rootId") == root and "due tomorrow" in m["text"]]


found, _ = wait_for(lambda: len(reminders()) == 2 and reminders(), 15)
check("reminders appear in the same thread in the channel", found, len(reminders()))
if found:
    mentioned = sorted(n for m in found for n in m["mentions"])
    check("each reminder @mentions its owner (real mention entities)", mentioned == ["Daniel", "Prince Alex"],
          mentioned)
    print("    e.g.", found[0]["text"][:140])

max_hook("POST", "/test/jobs/run")
check("running the jobs again posts nothing new", len(reminders()) == 2)

# Prince's task is done; Daniel's is not -> only Daniel is chased after the due date.
max_hook("POST", f"/test/tasks/{ids[0]}/close")
d = date.fromisoformat(due) + timedelta(days=1)
max_hook("POST", "/test/clock", {"now": datetime(d.year, d.month, d.day, 9, 1, tzinfo=timezone.utc).isoformat()})
max_hook("POST", "/test/jobs/run")


def chased():
    return [m for m in all_messages() if m["isBot"] and m.get("rootId") == root and "still open" in m["text"]]


wait_for(lambda: chased(), 15)
chases = chased()
check("after the due date: only the open task is chased", len(chases) == 1 and chases[0]["mentions"] == ["Daniel"],
      [c["text"][:80] for c in chases])
jobs = [j for j in max_state()["jobs"] if any(f'"taskId": {i}' in j["payload"] for i in ids)]
check("the closed task's chase was cancelled, not sent",
      any(j["status"] == "cancelled" and f'"taskId": {ids[0]}' in j["payload"] for j in jobs))

max_hook("POST", "/test/clock", {"reset": True})
check("no model calls used (templates only)", gemini_requests() == g0, gemini_requests() - g0)
finish("PHASE 4.2 FOLLOW-UPS")
