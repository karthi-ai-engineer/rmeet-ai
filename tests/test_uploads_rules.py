"""
Step 4.6 offline tests: saving a new file to SharePoint (approval, never overwrite, admin grant), the deadline-slip
rule's task date change (owner or manager confirms), and rule runs that stay silent. Scripted model, $0.
  .venv\\Scripts\\python tests\\test_uploads_rules.py
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

from agent.actions import action_tools  # noqa: E402
from agent.clock import FakeClock  # noqa: E402
from agent.graph import Deps, build_max_graph, new_request, resume_run, start_run  # noqa: E402
from agent.models import ChatHandle  # noqa: E402
from agent.testing import ScriptedChatModel, ai_call, ai_text  # noqa: E402
from agent.tools import memory_tools, task_tools  # noqa: E402
from approvals import Approvals  # noqa: E402
from graph_client import GraphError  # noqa: E402
from store import Store  # noqa: E402

fails = 0
T = "T1"


def check(name: str, ok, detail="") -> None:
    global fails
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f"  [{detail}]" if detail != "" else ""))


class FakeGraph:
    def __init__(self, deny=False, conflict=False):
        self.puts, self.deny, self.conflict = [], deny, conflict

    async def get(self, path, params=None):
        assert path.endswith("/filesFolder"), path
        return {"id": "FOLDER", "parentReference": {"driveId": "DRIVE"}}

    async def put_bytes(self, path, data, content_type="application/octet-stream", params=None):
        if self.deny:
            raise GraphError(403, "accessDenied", "no site grant")
        if self.conflict:
            raise GraphError(409, "nameAlreadyExists", "exists")
        self.puts.append({"path": path, "data": data, "type": content_type, "params": params})
        return {"name": path.split(":/")[1].split(":/")[0], "webUrl": "https://sp/x"}


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
        st.replace_team_content({"teamId": T, "teamName": "Planning", "channelId": "C1", "driveId": "DRIVE",
                                 "posts": [], "meetings": [],
                                 "files": [{"id": "f1", "name": "Budget v2.md", "author": "Prince Alex", "time": "t", "text": "v2"}]})
        for name, aad, role in (("Karthi M", "aad-k", "owner"), ("Daniel", "aad-d", "member"),
                                ("Jacob Thomas", "aad-j", "member")):
            st.touch_person(T, name, aad, "person", email=f"{name.split()[0].lower()}@x.com", role=role)
        clock = FakeClock(datetime(2026, 11, 23, 9, 0, tzinfo=timezone.utc))

        def setup(*replies, fg=None):
            fg = fg or FakeGraph()
            cards, posts = [], []

            async def post_card(team, card, root):
                cards.append(card)
                return f"c{len(cards)}"

            async def update_card(team, root, mid, card):
                cards.append(card)

            async def poster(team, text, mentions=None, root=None):
                posts.append(text)

            def toolsets(ctx):
                return memory_tools(ctx) + task_tools(ctx) + action_tools(ctx)
            appr = Approvals(st, clock, fg, toolsets, post_card, update_card)
            model = ScriptedChatModel(replies=list(replies))
            graph = build_max_graph(Deps(st, ChatHandle(model, "s", "t"), clock, toolsets, poster, appr,
                                         extra={"graph": fg}), InMemorySaver())

            async def resume(run_id, decision, root):
                await resume_run(graph, run_id, decision)
            appr.resume = resume
            return graph, appr, fg, cards, posts, model

        v3 = "# Budget v3 draft\n\n| Line | v2 | v3 |\n|---|---|---|\n| Total | 11,720K | 11,500K |\n"
        up = lambda name, content=v3: ai_call(("upload_file", {"name": name, "content": content}))  # noqa: E731

        # ---------------------------------------------------------------- upload: card, approve, saved once
        graph, appr, fg, cards, posts, model = setup(up("Budget v3 draft.md"), ai_text("Saved."))
        await start_run(graph, new_request(st, T, "mention", "Karthi M", "aad-k", "r1"), "save v3")
        facts = {f["title"]: f["value"] for f in cards[-1]["body"][1]["facts"]}
        body = [b["text"] for b in cards[-1]["body"] if b.get("type") == "TextBlock"]
        check("upload card: file name, place, 'overwrites nothing', and the full content", facts.get("File") ==
              "Budget v3 draft.md" and "nothing" in facts.get("Overwrites", "") and any("11,500K" in t for t in body), facts)
        check("nothing saved before approval", fg.puts == [])
        p = st.pendings(T, "pending")[-1]
        await appr.on_click("approve", {"pendingId": p["id"], "version": 1}, "aad-k", "Karthi M")
        await drain()
        check("approved: saved once, as a NEW file (conflictBehavior=fail), markdown type",
              len(fg.puts) == 1 and fg.puts[0]["params"] == {"@microsoft.graph.conflictBehavior": "fail"} and
              fg.puts[0]["type"] == "text/markdown" and b"11,500K" in fg.puts[0]["data"])

        for label, reply, why in (("existing name", up("budget V2.md"), "never overwrites"),
                                  ("not a text file", up("payload.exe"), ".md, .txt or .csv"),
                                  ("empty file", up("Empty.md", "  "), "empty")):
            graph, appr, fg, cards, posts, model = setup(reply, lambda m: ai_text(m[-1].content))
            await start_run(graph, new_request(st, T, "mention", "Karthi M", "aad-k", "r1"), "save")
            check(f"upload blocked ({label}): no card", not cards and why in posts[-1], posts[-1][:100])

        graph, appr, fg, cards, posts, model = setup(up("Notes v1.md"), ai_text("?"), fg=FakeGraph(deny=True))
        await start_run(graph, new_request(st, T, "mention", "Karthi M", "aad-k", "r1"), "save")
        await appr.on_click("approve", {"pendingId": st.pendings(T, "pending")[-1]["id"], "version": 1}, "aad-k", "Karthi M")
        await drain()
        check("no site grant: not uploaded, the card says what the admin must do",
              "Sites.Selected" in (st.pendings(T, "failed")[-1]["result"] or ""))

        # ---------------------------------------------------------------- deadline change: owner confirms
        tid = st.add_task(T, "Send Vector's Riverside quote", "Daniel", "2026-11-25", "meeting", "Review", "r9", "aad-d")
        st.add_job(T, "remind_task_due", datetime(2026, 11, 24, 9, 0, tzinfo=timezone.utc).timestamp(), {"taskId": tid},
                   dedupe_key=f"task:{tid}:remind_task_due:2026-11-25")
        rule = lambda: new_request(st, T, "deadline-rule", "Daniel", "aad-d", "r9",  # noqa: E731
                                   onlyTools=["propose_task_update"], silentIf="NO_CHANGE")
        graph, appr, fg, cards, posts, model = setup(
            ai_call(("propose_task_update", {"task_id": tid, "due": "2026-11-27", "reason": "I need till Friday"})),
            ai_text("Updated: the Vector quote is now due Fri 27 Nov."))
        await start_run(graph, rule(), "Daniel wrote: I need till Friday for the Vector quote")
        check("rule run is offered only the date-change tool", model.tool_names[-1] == ["propose_task_update"],
              model.tool_names[-1])
        facts = {f["title"]: f["value"] for f in cards[-1]["body"][1]["facts"]}
        check("date-change card: task, owner, old → new date, why", facts.get("Due") == "2026-11-25 → 2026-11-27"
              and facts.get("Owner") == "Daniel", facts)
        p = st.pendings(T, "pending")[-1]
        r = await appr.on_click("approve", {"pendingId": p["id"], "version": 1}, "aad-j", "Jacob Thomas")
        check("Jacob can't confirm Daniel's deadline change", "Only Daniel or Karthi M" in r.get("message", ""), r)
        await appr.on_click("approve", {"pendingId": p["id"], "version": 1}, "aad-d", "Daniel")
        await drain()
        t = st.task(tid)
        jobs = [j for j in st.jobs(T) if f'"taskId": {tid}' in j["payload"]]
        check("Daniel confirms: due date moved, old reminders cancelled, new ones planned",
              t["due"] == "2026-11-27" and any(j["status"] == "cancelled" for j in jobs)
              and any(j["status"] == "pending" and j["dedupe_key"].endswith("2026-11-27") for j in jobs))

        # ---------------------------------------------------------------- nothing to do: silent
        graph, appr, fg, cards, posts, model = setup(ai_text("NO_CHANGE"))
        req = rule()
        await start_run(graph, req, "Daniel wrote: thanks, I'll have it by Friday as planned")
        check("rule run that finds nothing posts nothing", posts == [] and not cards)
        check("…but it is still recorded as a run", any(r["id"] == req["runId"] and r["status"] == "ok" for r in st.runs(T)))
        st.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\nUPLOADS + RULES: ALL PASS" if not fails else f"\nUPLOADS + RULES: {fails} FAILED")


asyncio.run(main())
sys.exit(1 if fails else 0)
