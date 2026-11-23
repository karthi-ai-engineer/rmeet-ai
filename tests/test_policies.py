"""
Step 4.7 offline tests: per-team policies (RBAC): who may ask for a tool, who may approve, audit of changes.
Real graph + Approvals + policies + database; fake Graph; scripted model. $0.
  .venv\\Scripts\\python tests\\test_policies.py
"""

import asyncio
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "max"))
os.environ["MAX_MAILBOX"] = "max@kestrelhomegoods.com"

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

import policies  # noqa: E402
from agent.actions import action_tools  # noqa: E402
from agent.clock import FakeClock  # noqa: E402
from agent.graph import Deps, build_max_graph, new_request, resume_run, start_run  # noqa: E402
from agent.models import ChatHandle  # noqa: E402
from agent.testing import ScriptedChatModel, ai_call, ai_text  # noqa: E402
from agent.tools import memory_tools, task_tools  # noqa: E402
from approvals import Approvals  # noqa: E402
from store import Store  # noqa: E402

fails = 0
T, D = "T1", "kestrelhomegoods.com"


def check(name: str, ok, detail="") -> None:
    global fails
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f"  [{detail}]" if detail != "" else ""))


class FakeGraph:
    DIRECTORY = [{"id": "aad-e", "displayName": "Elena Park", "mail": f"elena@{D}"}]

    def __init__(self):
        self.drafts, self.sent = {}, []

    async def get(self, path, params=None):
        flt = (params or {}).get("$filter", "").lower()
        want = flt.split("'", 2)[1] if "'" in flt else ""
        return {"value": [u for u in self.DIRECTORY if u["mail"] == want or u["displayName"].lower().startswith(want)]}

    async def post(self, path, body):
        if path.endswith("/messages"):
            self.drafts["d1"] = body
            return {"id": "d1"}
        if path.endswith("/send"):
            self.sent.append(self.drafts.pop("d1"))
            return {}
        return {}

    async def delete(self, path):
        self.drafts.pop("d1", None)


async def drain():
    for _ in range(50):
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if not tasks:
            return
        await asyncio.gather(*tasks)


async def main() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        st = Store(tmp / "max.db")
        st.replace_team_content({"teamId": T, "teamName": "Planning", "channelId": "C1", "posts": [], "files": [],
                                 "meetings": []})
        for name, aad, role in (("Karthi M", "aad-k", "owner"), ("Prince Alex", "aad-p", "member")):
            st.touch_person(T, name, aad, "person", email=f"{name.split()[0].lower()}@{D}", role=role)
        clock = FakeClock(datetime(2026, 11, 23, 9, 0, tzinfo=timezone.utc))

        def setup(*replies):
            fg, posts, cards = FakeGraph(), [], []

            async def post_card(team, card, root):
                cards.append(card)
                return "c"

            async def update_card(team, root, mid, card):
                cards.append(card)

            async def poster(team, text, mentions=None, root=None):
                posts.append(text)

            def toolsets(ctx):
                return memory_tools(ctx) + task_tools(ctx) + action_tools(ctx)
            appr = Approvals(st, clock, fg, toolsets, post_card, update_card)
            model = ScriptedChatModel(replies=list(replies))
            graph = build_max_graph(Deps(st, ChatHandle(model, "s", "t"), clock, toolsets, poster, appr,
                                         policy=policies.make_filter(st), extra={"graph": fg}), InMemorySaver())

            async def resume(run_id, decision, root):
                await resume_run(graph, run_id, decision)
            appr.resume = resume
            return graph, appr, fg, model, posts, cards

        email = ai_call(("send_email", {"to": ["Elena Park"], "subject": "Budget", "body": "Hi Elena"}))
        prince = lambda: new_request(st, T, "mention", "Prince Alex", "aad-p", "r1")  # noqa: E731
        karthi = lambda: new_request(st, T, "mention", "Karthi M", "aad-k", "r1")   # noqa: E731

        # ---------------------------------------------------------------- defaults
        graph, appr, fg, model, posts, cards = setup(ai_text("hi"))
        await start_run(graph, prince(), "hi")
        check("default: every team member gets every tool", "send_email" in model.tool_names[-1])

        # ---------------------------------------------------------------- who may ask
        st.set_policy(T, "mail.send", who="owners", by="test")
        graph, appr, fg, model, posts, cards = setup(ai_text("I'm not allowed to send emails for you; ask Karthi."))
        await start_run(graph, prince(), "email Elena")
        sp = model.calls[-1][0].content
        check("mail.send = owners only: Prince (member) is not offered send_email",
              "send_email" not in model.tool_names[-1] and "find_free_times" in model.tool_names[-1])
        check("…and the model is told why, to explain politely", "policy doesn't let Prince Alex use: Send emails" in sp)
        graph, appr, fg, model, posts, cards = setup(ai_text("ok"))
        await start_run(graph, karthi(), "email Elena")
        check("…while Karthi (owner) still gets it", "send_email" in model.tool_names[-1])
        st.set_policy(T, "mail.send", who="nobody", by="test")
        graph, appr, fg, model, posts, cards = setup(ai_text("ok"))
        await start_run(graph, karthi(), "email Elena")
        check("mail.send = nobody: not even the owner", "send_email" not in model.tool_names[-1])
        st.set_policy(T, "mail.send", who="everyone", by="test")

        # ---------------------------------------------------------------- who approves
        st.set_policy(T, "mail.send", approvers="owners", by="test")
        graph, appr, fg, model, posts, cards = setup(email, ai_text("Sent."))
        await start_run(graph, prince(), "email Elena")
        p = st.pendings(T, "pending")[-1]
        names = " ".join(b.get("text", "") for b in cards[-1]["body"] if b.get("type") == "TextBlock")
        check("approvers = owners: the card names only Karthi, buttons only for Karthi",
              "can approve: Karthi M" in names and "Prince" not in names.split("can approve:")[1]
              and cards[-1]["refresh"]["userIds"] == ["aad-k"], names[-120:])
        r = await appr.on_click("approve", {"pendingId": p["id"], "version": 1}, "aad-p", "Prince Alex")
        check("Prince can't approve his own request under this policy", "Only Karthi M" in r.get("message", "") and not fg.sent)
        await appr.on_click("approve", {"pendingId": p["id"], "version": 1}, "aad-k", "Karthi M")
        await drain()
        check("Karthi approves: sent", len(fg.sent) == 1)

        # ---------------------------------------------------------------- audit + validation + catalog
        changes = [a for a in st.q("SELECT * FROM audit WHERE kind = 'policy-changed'")]
        check("every policy change is in the audit log", len(changes) == 4, len(changes))
        try:
            st.set_policy(T, "mail.send", who="admins-only")
            check("unknown policy values are refused", False)
        except ValueError:
            check("unknown policy values are refused", True)
        cat = policies.catalog(st, T, lambda ctx: memory_tools(ctx) + task_tools(ctx) + action_tools(ctx), clock,
                               {"graph": None})
        tags = {c["tag"]: c for c in cat}
        check("admin catalog: one row per tag with tools, kind and Microsoft permission",
              tags["mail.send"]["risk"] == "external" and tags["mail.send"]["approvers"] == "owners"
              and "create_meeting" in tags["meetings.create"]["tools"] and tags["tasks.write"]["risk"] == "external"
              and "Mail.Send" in tags["mail.send"]["permission"], sorted(tags))
        st.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\nPOLICIES: ALL PASS" if not fails else f"\nPOLICIES: {fails} FAILED")


asyncio.run(main())
sys.exit(1 if fails else 0)
