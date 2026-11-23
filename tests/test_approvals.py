"""
Step 4.4 offline tests: approvals + email with the real graph, real Approvals, real database; a fake Microsoft
Graph (directory + Max's mailbox) and the scripted model. No model calls, $0.
  .venv\\Scripts\\python tests\\test_approvals.py
"""

import asyncio
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "max"))
os.environ["MAX_MAILBOX"] = "max@kestrelhomegoods.com"

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from agent.actions import action_tools  # noqa: E402
from agent.clock import FakeClock  # noqa: E402
from agent.graph import Deps, build_max_graph, new_request, resume_run, start_run  # noqa: E402
from agent.models import ChatHandle  # noqa: E402
from agent.testing import ScriptedChatModel, ai_call, ai_text, tool_pair_problems  # noqa: E402
from agent.tools import memory_tools, task_tools  # noqa: E402
from approvals import Approvals  # noqa: E402
from graph_client import GraphError  # noqa: E402
from store import Store  # noqa: E402

fails = 0
T = "T1"
DOMAIN = "kestrelhomegoods.com"


def check(name: str, ok, detail="") -> None:
    global fails
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f"  [{detail}]" if detail != "" else ""))


class FakeGraph:
    DIRECTORY = [{"id": "aad-e", "displayName": "Elena Park", "mail": f"elena@{DOMAIN}"},
                 {"id": "aad-k", "displayName": "Karthi M", "mail": f"karthi@{DOMAIN}"},
                 {"id": "aad-p", "displayName": "Prince Alex", "mail": f"prince@{DOMAIN}"}]

    def __init__(self, deny_mail=False):
        self.drafts, self.sent, self.deleted, self.deny_mail = {}, [], [], deny_mail

    async def get(self, path, params=None):
        flt = ((params or {}).get("$filter") or "").lower()
        if "eq '" in flt:
            want = flt.split("eq '", 1)[1].rstrip("')")
            return {"value": [u for u in self.DIRECTORY if u["mail"] == want]}
        want = flt.split("'", 2)[1]
        return {"value": [u for u in self.DIRECTORY if u["displayName"].lower().startswith(want)]}

    async def post(self, path, body):
        if path.endswith("/messages"):
            if self.deny_mail:
                raise GraphError(403, "ErrorAccessDenied", "Access is denied.")
            mid = f"draft{len(self.drafts) + len(self.sent) + len(self.deleted) + 1}"
            self.drafts[mid] = {**body, "att": []}
            return {"id": mid}
        mid = path.split("/messages/")[1].split("/")[0]
        if path.endswith("/attachments"):
            self.drafts[mid]["att"].append(body["name"])
            return {}
        if path.endswith("/send"):
            if mid not in self.drafts:
                raise GraphError(404, "ErrorItemNotFound", "not found")
            self.sent.append(self.drafts.pop(mid))
            return {}
        raise AssertionError(path)

    async def delete(self, path):
        mid = path.rsplit("/", 1)[1]
        self.drafts.pop(mid, None)
        self.deleted.append(mid)

    async def download(self, drive_id, item_id):
        return b"x" * 2048


class Cards:
    def __init__(self):
        self.posted, self.updated = [], []

    async def post(self, team, card, root):
        self.posted.append({"card": card, "root": root})
        return f"card{len(self.posted)}"

    async def update(self, team, root, msg_id, card):
        self.updated.append({"id": msg_id, "card": card})


class Poster:
    def __init__(self):
        self.posts = []

    async def __call__(self, team, text, mentions=None, root=None):
        self.posts.append(text)
        return "m"


def head(card) -> str:
    return card["body"][0]["text"]


async def drain() -> None:
    for _ in range(50):
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if not tasks:
            return
        await asyncio.gather(*tasks)


def email(to=("Elena Park",), subject="H1 budget draft v2", body="Hi Elena,\nPlease find draft v2 attached.\nKarthi",
          attachments=("Budget_Draft_v2",), cc=()):
    return ai_call(("send_email", {"to": list(to), "cc": list(cc), "subject": subject, "body": body,
                                   "attachments": list(attachments)}))


async def main() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        st = Store(tmp / "max.db")
        st.replace_team_content({"teamId": T, "teamName": "Planning", "channelId": "C1", "driveId": "D1", "posts": [],
                                 "files": [{"id": "f1", "name": "04_H1_FY2027_Budget_Draft_v2.xlsx",
                                            "author": "Prince Alex", "time": "t", "text": "budget"}], "meetings": []})
        for name, aad, role in (("Karthi M", "aad-k", "owner"), ("Prince Alex", "aad-p", "member"),
                                ("Jacob Thomas", "aad-j", "member")):
            st.touch_person(T, name, aad, "person", email=f"{name.split()[0].lower()}@{DOMAIN}", role=role)
        clock = FakeClock(datetime(2026, 11, 23, 9, 0, tzinfo=timezone.utc))

        def setup(*replies, deny_mail=False):
            fg, cards, poster = FakeGraph(deny_mail), Cards(), Poster()

            def toolsets(ctx):
                return memory_tools(ctx) + task_tools(ctx) + action_tools(ctx)
            appr = Approvals(st, clock, fg, toolsets, cards.post, cards.update)
            model = ScriptedChatModel(replies=list(replies))
            deps = Deps(st, ChatHandle(model, "scripted", "test"), clock, toolsets, poster, appr, extra={"graph": fg})
            graph = build_max_graph(deps, InMemorySaver())

            async def resume(run_id, decision, root):
                await resume_run(graph, run_id, decision)
            appr.resume = resume
            return graph, appr, fg, cards, poster, model

        def ask(graph, who=("Karthi M", "aad-k")):
            return new_request(st, T, "mention", who[0], who[1], "root-1")

        # ---------------------------------------------------------------- prepare: the card shows everything
        graph, appr, fg, cards, poster, model = setup(email(), ai_text("Sent the draft v2 to Elena."))
        req = ask(graph)
        out = await start_run(graph, req, "email Elena the budget draft v2")
        p = st.pendings(T, "pending")[-1]
        card = cards.posted[-1]["card"]
        facts = {f["title"]: f["value"] for f in card["body"][1]["facts"]}
        check("run paused for approval; draft created in Max's mailbox, nothing sent",
              out.get("__interrupt__") and len(fg.drafts) == 1 and fg.sent == [])
        check("card shows From (Max), To (Elena, resolved in the directory), Subject, attachment with size, full body",
              facts.get("From", "").startswith("Max (AI) <max@") and facts.get("To") == f"Elena Park <elena@{DOMAIN}>"
              and facts.get("Subject") == "H1 budget draft v2" and "04_H1_FY2027_Budget_Draft_v2.xlsx (2 KB)" in
              facts.get("Attachments", "") and any("Please find draft v2" in b.get("text", "") for b in card["body"]), facts)
        check("card posted in the requester's thread with Approve / Change / Cancel and approver-only refresh",
              cards.posted[-1]["root"] == "root-1" and [a["verb"] for a in card["actions"]] == ["approve", "change", "cancel"]
              and card["refresh"]["userIds"] == ["aad-k"])
        check("expiry job scheduled 24 h later", any(j["kind"] == "expire_approval" for j in st.jobs(T, "pending")))

        # ---------------------------------------------------------------- wrong person clicks
        r = await appr.on_click("approve", {"pendingId": p["id"], "version": 1}, "aad-j", "Jacob Thomas")
        check("Jacob (not requester, not manager) can't approve; nothing changes",
              "message" in r and "Only Karthi M" in r["message"] and st.pending(p["id"])["status"] == "pending", r)
        check("the denied attempt is in the audit log",
              any(a["kind"] == "approval-denied" for a in st.audit_for(req["runId"])))

        # ---------------------------------------------------------------- approve (answered at once), sent once
        r = await appr.on_click("approve", {"pendingId": p["id"], "version": 1}, "aad-k", "Karthi M")
        check("approve: the click is answered at once with a 'Sending…' card", "Sending" in head(r["card"]))
        await drain()
        check("email sent exactly once, with its attachment", len(fg.sent) == 1 and fg.sent[0]["att"] ==
              ["04_H1_FY2027_Budget_Draft_v2.xlsx"] and not fg.drafts)
        check("card updated to Done; reply posted in the thread",
              "✅ Done · approved by Karthi M" in head(cards.updated[-1]["card"]) and "Sent" in poster.posts[-1])
        r = await appr.on_click("approve", {"pendingId": p["id"], "version": 1}, "aad-k", "Karthi M")
        await drain()
        check("a second click changes nothing (no second send)", len(fg.sent) == 1 and "Done" in head(r["card"]))
        st_run = await graph.aget_state({"configurable": {"thread_id": req["runId"]}})
        check("history rule held through the whole approval", tool_pair_problems(st_run.values["messages"]) == [])

        # ---------------------------------------------------------------- the manager can approve someone else's
        graph, appr, fg, cards, poster, model = setup(email(), ai_text("Sent."))
        await start_run(graph, ask(graph, ("Prince Alex", "aad-p")), "email Elena")
        p = st.pendings(T, "pending")[-1]
        await appr.on_click("approve", {"pendingId": p["id"], "version": 1}, "aad-k", "Karthi M")
        await drain()
        check("the manager (team owner) may approve Prince's request", len(fg.sent) == 1)

        # ---------------------------------------------------------------- rules block before any card
        for name, reply, why in (
                ("outside address", email(to=("x@evil.example",)), "not a person in the company"),
                ("unknown person", email(to=("Nobody Here",)), "no one called"),
                ("attachment not in the channel", email(attachments=("secret.pdf",)), "no channel file"),
                ("hidden Bcc-style extra via cc outside", email(cc=("spy@other.example",)), "not a person in the company")):
            graph, appr, fg, cards, poster, model = setup(
                reply, lambda m: ai_text("Can't: " + m[-1].content))
            out = await start_run(graph, ask(graph), "email")
            check(f"blocked ({name}): no draft, no card, the model is told why",
                  not fg.drafts and not cards.posted and out.get("__interrupt__") is None and why in poster.posts[-1],
                  poster.posts[-1][:120])

        graph, appr, fg, cards, poster, model = setup(email(), lambda m: ai_text("Can't: " + m[-1].content), deny_mail=True)
        await start_run(graph, ask(graph), "email")
        check("no Mail consent: blocked with the admin step named", "Mail.ReadWrite" in poster.posts[-1], poster.posts[-1])

        # ---------------------------------------------------------------- change -> new version
        graph, appr, fg, cards, poster, model = setup(
            email(), lambda m: email(subject="H1 budget draft v2 (for Friday)"), ai_text("Sent the new version."))
        req = ask(graph)
        await start_run(graph, req, "email Elena")
        p1 = st.pendings(T, "pending")[-1]
        r = await appr.on_click("change", {"pendingId": p1["id"], "version": 1, "edit": ""}, "aad-k", "Karthi M")
        check("change without text: asked to type it first", "Type what should change" in r.get("message", ""))
        r = await appr.on_click("change", {"pendingId": p1["id"], "version": 1, "edit": "add 'for Friday' to the subject"},
                                "aad-k", "Karthi M")
        await drain()
        p2 = st.pendings(T, "pending")[-1]
        check("change: old card superseded, old draft deleted, new card with the new subject",
              st.pending(p1["id"])["status"] == "superseded" and p1["graph_id"] in fg.deleted
              and p2["id"] != p1["id"] and "for Friday" in p2["preview"])
        r = await appr.on_click("approve", {"pendingId": p1["id"], "version": 1}, "aad-k", "Karthi M")
        await drain()
        check("clicking Approve on the OLD card does nothing", fg.sent == [] and "Changed" in head(r["card"]))
        await appr.on_click("approve", {"pendingId": p2["id"], "version": 1}, "aad-k", "Karthi M")
        await drain()
        check("approve the new card: exactly the new version is sent", len(fg.sent) == 1 and
              fg.sent[0]["subject"] == "H1 budget draft v2 (for Friday)")

        # ---------------------------------------------------------------- cancel
        graph, appr, fg, cards, poster, model = setup(email())
        await start_run(graph, ask(graph), "email")
        p = st.pendings(T, "pending")[-1]
        await appr.on_click("cancel", {"pendingId": p["id"], "version": 1}, "aad-k", "Karthi M")
        await drain()
        check("cancel: draft deleted, nothing sent, 'cancelled' reply, no extra model call",
              fg.sent == [] and not fg.drafts and "cancelled" in poster.posts[-1] and len(model.calls) == 1)

        # ---------------------------------------------------------------- expiry
        graph, appr, fg, cards, poster, model = setup(email())
        await start_run(graph, ask(graph), "email")
        p = st.pendings(T, "pending")[-1]
        job = next(j for j in st.jobs(T, "pending") if json.loads(j["payload"]).get("pendingId") == p["id"])
        clock.advance(hours=25)
        await appr.expire_job({"payload": {"pendingId": p["id"]}, "team_id": T})
        await drain()
        check("after 24 h: expired, draft deleted, card says Expired, reply posted",
              st.pending(p["id"])["status"] == "expired" and not fg.drafts and "Expired" in head(cards.updated[-1]["card"])
              and "expired" in poster.posts[-1], job["kind"])
        r = await appr.on_click("approve", {"pendingId": p["id"], "version": 1}, "aad-k", "Karthi M")
        check("a late click after expiry sends nothing", fg.sent == [] and "Expired" in head(r["card"]))
        clock.advance(hours=-25)

        # ---------------------------------------------------------------- tamper + recovery
        graph, appr, fg, cards, poster, model = setup(email(), ai_text("?"))
        req = ask(graph)
        await start_run(graph, req, "email")
        p = st.pendings(T, "pending")[-1]
        with st.tx() as db:   # someone edits the stored payload after the card was shown
            db.execute("UPDATE pending_actions SET payload = REPLACE(payload, 'elena@', 'evil@') WHERE id = ?", (p["id"],))
        await appr.on_click("approve", {"pendingId": p["id"], "version": 1}, "aad-k", "Karthi M")
        await drain()
        check("payload changed after it was shown: refused, nothing sent", fg.sent == [] and
              st.pending(p["id"])["status"] == "failed")

        graph, appr, fg, cards, poster, model = setup(email(), ai_text("Sent."))
        await start_run(graph, ask(graph), "email")
        p = st.pendings(T, "pending")[-1]
        st.claim_pending(p["id"], "pending", "approved", by="Karthi M")         # approved, then Max stopped
        await appr.recover()
        await drain()
        check("restart: an approved-but-not-sent email is sent once after the restart",
              len(fg.sent) == 1 and st.pending(p["id"])["status"] == "done")
        graph, appr, fg, cards, poster, model = setup(email())
        await start_run(graph, ask(graph), "email")
        p = st.pendings(T, "pending")[-1]
        st.claim_pending(p["id"], "pending", "approved", by="Karthi M")
        st.claim_pending(p["id"], "approved", "executing")                     # stopped in the middle of sending
        await appr.recover()
        check("restart: one stuck 'executing' is marked failed, never re-sent", fg.sent == [] and
              st.pending(p["id"])["status"] == "failed")
        st.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\nAPPROVALS: ALL PASS" if not fails else f"\nAPPROVALS: {fails} FAILED")


asyncio.run(main())
sys.exit(1 if fails else 0)
