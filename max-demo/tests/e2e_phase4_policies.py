"""
Phase 4 step 4.7 end-to-end: Max's admin page and per-team policies (RBAC) in the running system.
Uses ~1-3 Gemini requests.   needs: simulator (:8100) + Max (:3978, MAX_TEST_HOOKS=1, agent on)
"""

import time

from e2e_lib import (MAX, SIM, TEAM_ID, check, channel, finish, gemini_requests, http, post, wait_for, wait_ready)

wait_ready()
if not (channel().get("install") or {}).get("installed"):
    http("POST", SIM + "/api/admin", {"consent": True, "accessPolicy": True, "transcriptApiAccess": True})
    http("POST", SIM + "/api/channel/install", {"action": "add"})
    wait_for(lambda: next((p for p in channel()["posts"] if p["isBot"]), None), 120)
g0 = gemini_requests()

s, page = http("GET", MAX + "/admin")
check("admin page is served on this machine", s == 200 and b"<title>Max Admin</title>" in page)
s, st = http("GET", f"{MAX}/admin/api/state?team={TEAM_ID}")
tags = {p["tag"]: p for p in st.get("policies", [])}
check("admin state lists the policy catalog (tools, kind, Microsoft permission) and activity",
      s == 200 and "mail.send" in tags and tags["mail.send"]["risk"] == "external" and "runs" in st, sorted(tags))
s, r = http("POST", MAX + "/admin/api/team", {"team": TEAM_ID, "timeZone": "Mars/Olympus"})
check("an unknown time zone is refused", s == 400)

s, r = http("POST", MAX + "/admin/api/policy", {"team": TEAM_ID, "tag": "mail.send", "who": "owners"})
check("policy set: only team owners may ask Max to send email", s == 200 and r["who"] == "owners", r)
q = http("POST", SIM + "/api/channel/post", {"text": "@Max please email Robert Hayes a one-line hello from the team",
                                             "as": "jacob"})[1]
reply, dt = wait_for(lambda: next((r for p in channel()["posts"] if p["id"] == q["id"] for r in p.get("replies", [])
                                   if r["isBot"]), None), 120, 1)
check("Jacob (member) asks for an email: no card; Max explains politely",
      reply and not reply.get("cards") and any(w in reply["text"].lower() for w in ("policy", "owner", "not allowed",
                                                                                  "can't", "cannot", "unable")),
      (reply or {}).get("text", "")[:180])
http("POST", MAX + "/admin/api/policy", {"team": TEAM_ID, "tag": "mail.send", "who": "everyone"})
s, st = http("GET", f"{MAX}/admin/api/state?team={TEAM_ID}")
run = next((r for r in st["runs"] if r["requester"] == "Jacob Thomas"), None)
s, audit = http("GET", f"{MAX}/admin/api/audit/{run['id']}") if run else (0, [])
intake = next((a for a in audit if a["kind"] == "intake"), None)
check("the activity log shows the run and that send_email was withheld by policy",
      intake and "send_email" not in intake["detail"] and "Send emails" in intake["detail"], (intake or {}).get("detail", "")[:160])

print(f"\n  Gemini requests used: {gemini_requests() - g0}")
finish("PHASE 4.7 POLICIES")
