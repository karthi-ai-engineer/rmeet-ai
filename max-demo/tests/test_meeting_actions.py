"""
Phase 5.2 offline tests: Max does things live in a meeting. Real agent graph, real Approvals, real database, a real
MeetingCall (no network: fake Teams app, text mode), fake Microsoft Graph and the scripted model. $0.
  .venv\\Scripts\\python tests\\test_meeting_actions.py
"""

import asyncio
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "max"))
os.environ["MAX_MAILBOX"] = "max@kestrelhomegoods.com"

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

import brain  # noqa: E402
import meeting_actions as ma  # noqa: E402
import policies  # noqa: E402
from agent.actions import action_tools, invite_body  # noqa: E402
from agent.clock import FakeClock  # noqa: E402
from agent.graph import Deps, build_max_graph, system_prompt  # noqa: E402
from agent.models import ChatHandle  # noqa: E402
from agent.testing import ScriptedChatModel, ai_call, ai_text, tool_pair_problems  # noqa: E402
from agent.tools import memory_tools, task_tools  # noqa: E402
from approvals import Approvals  # noqa: E402
from calling import MeetingCall  # noqa: E402
from store import Store  # noqa: E402

fails = 0
T, DOMAIN, ROOT_ID = "T1", "kestrelhomegoods.com", "1795300000001"
CONV = f"19:chan@thread.tacv2;messageid={ROOT_ID}"


def check(name: str, ok, detail="") -> None:
    global fails
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f"  [{detail}]" if detail != "" else ""))


# ------------------------------------------------------------------ fakes
class FakeGraph:
    DIRECTORY = [{"id": "aad-e", "displayName": "Elena Park", "mail": f"elena@{DOMAIN}"},
                 {"id": "aad-k", "displayName": "Karthi M", "mail": f"karthi@{DOMAIN}"},
                 {"id": "aad-p", "displayName": "Prince Alex", "mail": f"prince@{DOMAIN}"}]

    def __init__(self):
        self.drafts, self.sent = {}, []

    async def get(self, path, params=None):
        flt = ((params or {}).get("$filter") or "").lower()
        if "eq '" in flt:
            want = flt.split("eq '", 1)[1].rstrip("')")
            return {"value": [u for u in self.DIRECTORY if u["mail"] == want]}
        want = flt.split("'", 2)[1]
        return {"value": [u for u in self.DIRECTORY if u["displayName"].lower().startswith(want)]}

    async def post(self, path, body):
        if path.endswith("/messages"):
            mid = f"draft{len(self.drafts) + len(self.sent) + 1}"
            self.drafts[mid] = {**body, "att": []}
            return {"id": mid}
        mid = path.split("/messages/")[1].split("/")[0]
        if path.endswith("/send"):
            self.sent.append(self.drafts.pop(mid))
            return {}
        if path.endswith("/attachments"):
            self.drafts[mid]["att"].append(body["name"])
            return {}
        raise AssertionError(path)

    async def delete(self, path):
        self.drafts.pop(path.rsplit("/", 1)[1], None)

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


class Sent:
    def __init__(self, i):
        self.id = f"msg{i}"


class FakeApp:
    """The Teams app as MeetingCall uses it: send(conversation, text)."""

    def __init__(self):
        self.sent = []

    async def send(self, conversation_id, text, service_url=None):
        self.sent.append((conversation_id, text))
        return Sent(len(self.sent))


class FakeKB:
    def __init__(self, store):
        self.store = store
        self.messages = []

    def prompt_text(self):
        return "CHANNEL KNOWLEDGE: (test)"

    def add_message(self, mid, author, text, root):
        self.messages.append((author, text, root))


async def drain() -> None:
    for _ in range(80):
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if not tasks:
            return
        await asyncio.gather(*tasks)


def email_call(subject="Final H1 numbers"):
    return ai_call(("send_email", {"to": ["Elena Park"], "cc": [], "subject": subject,
                                   "body": "Hi Elena,\nThe final H1 total is 11,500K.\nKarthi", "attachments": []}))


# ------------------------------------------------------------------ 1. router (pure)
def test_router() -> None:
    acts = ["Max, book a 30 minute follow-up on Tuesday with Prince and Daniel",
            "Max, please email Elena the final numbers",
            "Max can you cancel Friday's sync?",
            "Max, add a task for Jacob to update the campaign plan by Wednesday",
            "Max, move Prince's budget deadline to Friday",
            "Max, schedule a call with Vector next week",
            "Max, could you send the notes to Elena?",
            "Max, set up a meeting with everyone here for Thursday",
            "Max, remind Daniel about the Riverside quote tomorrow",
            "Thanks Max. Could you send that summary to Elena?",
            "Max, remind me tomorrow to call Northgate"]
    questions = ["Max, when did we shortlist Vector, and what was LiftLine's lead time?",
                 "Max, what's the budget gap?",
                 "Max, did we send the email to Elena?",
                 "Max, who said LiftLine is 40K cheaper?",
                 "Max, how much does the pilot save in H1?",
                 "Max, what is the risk with option B?",
                 "Max, remind me, what revenue uplift did I estimate for Option B of the campaign?",
                 "That sounds like a solid plan, but before we lock that in, Max, what's the risk with option B again?",
                 "Actions: Prince, v3 by Tuesday. I'll send the final budget to Elena by the 28th. Max, please post the summary."]
    wrong = [a for a in acts if not ma.wants_action(a, "hybrid")] + [q for q in questions if ma.wants_action(q, "hybrid")]
    check(f"router: {len(acts)} action requests -> agent, {len(questions)} questions -> fast classic answer",
          not wrong, wrong)
    check("router: MAX_MEETING_BRAIN=agent sends everything to the agent; classic sends nothing",
          ma.wants_action(questions[0], "agent") and not ma.wants_action(acts[0], "classic"))
    check("router: 'should we / let's' questions that ask for an action still go to the agent",
          ma.wants_action("Max, should we book a follow-up with Daniel for Tuesday?", "hybrid"))


def test_lines() -> None:
    one = ma.pause_line("meeting", [{"name": "Karthi M", "aad_id": "k"}])
    two = ma.pause_line("email", [{"name": "Prince Alex"}, {"name": "Karthi M"}])
    cancel = ma.pause_line("meeting", [{"name": "Karthi M"}], "Cancel this meeting?")
    check("pause line names the thing and who approves (one / two approvers, cancellation)",
          one == "I've put the meeting invite in the meeting chat for Karthi M to approve." and
          two == "I've put the email in the meeting chat for Prince Alex or Karthi M to approve." and
          "meeting cancellation" in cancel, (one, two, cancel))
    text = ma.request_text([("Karthi M", "Let's start."), ("Prince Alex", "Budget is 11,500K.")], "Karthi M",
                           "Max, book a follow-up")
    check("request text carries the live transcript and who said what to Max",
          "Prince Alex: Budget is 11,500K." in text and text.endswith('Karthi M just said to you in the call: "Max, book a follow-up"'))
    check("classic meeting answers must never claim an action is done",
          "Never say you have sent, booked, cancelled or changed anything" in brain.MEETING_RULES and
          "confirm briefly" not in brain.MEETING_RULES)


# ------------------------------------------------------------------ 2-5. agent + call
async def main() -> None:
    test_router()
    test_lines()
    tmp = Path(tempfile.mkdtemp())
    try:
        st = Store(tmp / "max.db")
        st.replace_team_content({"teamId": T, "teamName": "Planning", "channelId": "19:chan@thread.tacv2",
                                 "driveId": "D1", "posts": [], "files": [], "meetings": []})
        for name, aad, role in (("Karthi M", "aad-k", "owner"), ("Prince Alex", "aad-p", "member"),
                                ("Jacob Thomas", "aad-j", "member")):
            st.touch_person(T, name, aad, "person", email=f"{name.split()[0].lower()}@{DOMAIN}", role=role)
        clock = FakeClock(datetime(2026, 11, 23, 9, 0, tzinfo=timezone.utc))
        posts = []

        async def post(team, text, mentions=None, root=None):
            posts.append((text, root))
            return "p"

        def setup(*replies):
            fg, cards, runs, locks = FakeGraph(), Cards(), {}, {}

            def toolsets(ctx):
                return memory_tools(ctx) + task_tools(ctx) + action_tools(ctx)
            appr = Approvals(st, clock, fg, toolsets, cards.post, cards.update)
            model = ScriptedChatModel(replies=list(replies))
            deps = Deps(st, ChatHandle(model, "scripted", "test"), clock, toolsets, post, appr,
                        policy=policies.make_filter(st), extra={"graph": fg, "deliver_meeting": ma.make_deliver(runs, post)})
            graph = build_max_graph(deps, InMemorySaver())

            async def resume(run_id, decision, root):
                from agent.graph import resume_run
                await resume_run(graph, run_id, decision)
            appr.resume = resume
            return graph, appr, fg, cards, model, runs, locks, deps

        def new_call(act=None):
            app = FakeApp()
            call = MeetingCall(app, None, T, FakeKB(st), CONV, "https://svc", "Budget follow-up", lambda c: None,
                               clock=clock, act=act)
            call.audio_mode = False                         # text-mode call: Max's words go to the meeting chat
            call.roster = {"1": {"name": "Karthi M", "id": "aad-k"}, "2": {"name": "Prince Alex", "id": "aad-p"},
                           "3": {"name": "Jacob Thomas", "id": "aad-j"}}
            return call, app

        async def hear(call, msi, text):
            who = call.roster[str(msi)]
            await call._on_control({"t": "transcript", "msi": msi, "text": text,
                                    "speaker": {"displayName": who["name"], "id": who["id"]}})
            await drain()

        # ---------------------------------------------------------------- 2. the call routes lines
        acted = []

        async def fake_act(call, speaker, aad, said):
            acted.append((speaker, aad, said))
            await call.say("I've put the email in the meeting chat for Karthi M to approve.")

        call, app = new_call(fake_act)
        call.session.answer = lambda: (call.session.transcript.append(("Max", "In the 20 October meeting.")) or
                                       "In the 20 October meeting.")
        await hear(call, 2, "The final total is 11,500K.")
        await hear(call, 1, "Max, when did we shortlist Vector?")
        await hear(call, 1, "Max, please email Elena the final numbers")
        check("call: a question gets the fast classic answer in the meeting chat (text call)",
              (CONV, "In the 20 October meeting.") in app.sent, app.sent)
        check("call: an action request goes to the agent with the speaker's name and AAD id (who asked = approver)",
              acted == [("Karthi M", "aad-k", "Max, please email Elena the final numbers")], acted)
        check("call: lines not addressed to Max are only heard", len(app.sent) == 2 and len(acted) == 1)
        check("call: Max's own words are kept in the transcript (for the notes)",
              ("Max", "I've put the email in the meeting chat for Karthi M to approve.") in call.session.transcript)
        check("call: people() = names in the call", call.people() == ["Karthi M", "Prince Alex", "Jacob Thomas"])

        # ---------------------------------------------------------------- 3. agent in a meeting: question
        graph, appr, fg, cards, model, runs, locks, deps = setup(ai_text("The final total is **11,500K**."))
        call, app = new_call()
        call.session.transcript = [("Prince Alex", "The final total is 11,500K."), ("Karthi M", "Max, what's the total?")]
        r = await ma.run_request(call, "Karthi M", "aad-k", "Max, what's the total?", graph=graph, store=st,
                                 approvals=appr, runs=runs, locks=locks)
        sysmsg = model.calls[0][0].content
        check("meeting run: system prompt = live meeting, title, people in the call, spoken style, no Markdown rule",
              "in a live Teams meeting 'Budget follow-up'" in sysmsg and "Karthi M, Prince Alex, Jacob Thomas" in sysmsg
              and "1-2 short spoken sentences" in sysmsg and "light Markdown" not in sysmsg, sysmsg[:200])
        check("meeting run: the request includes the transcript so far",
              "Prince Alex: The final total is 11,500K." in model.calls[0][1].content)
        check("meeting run: the answer is said in the call (text call -> meeting chat), not posted elsewhere",
              not r["paused"] and app.sent == [(CONV, "The final total is **11,500K**.")] and not posts, (app.sent, posts))
        run = st.q1("SELECT * FROM runs WHERE id = ?", (r["runId"],))
        check("meeting run is recorded: source 'meeting', thread = the meeting's thread, requester",
              run["trigger"] == "meeting" and run["thread_id"] == ROOT_ID and run["requester"] == "Karthi M", dict(run))

        # ---------------------------------------------------------------- 4. agent in a meeting: email -> approve
        graph, appr, fg, cards, model, runs, locks, deps = setup(email_call(), ai_text("Done: I emailed Elena the final numbers."))
        call, app = new_call()
        call.session.transcript = [("Karthi M", "Max, please email Elena the final numbers")]
        r = await ma.run_request(call, "Karthi M", "aad-k", "Max, please email Elena the final numbers", graph=graph,
                                 store=st, approvals=appr, runs=runs, locks=locks)
        p = st.pendings(T, "pending")[-1]
        check("email asked in the meeting: run paused, card posted in the MEETING thread, nothing sent yet",
              r["paused"] and cards.posted[-1]["root"] == ROOT_ID and fg.sent == [] and len(fg.drafts) == 1)
        check("Max says one line in the call about the card (no model call for it)",
              app.sent == [(CONV, "I've put the email in the meeting chat for Karthi M to approve.")] and
              len(model.calls) == 1, app.sent)
        data = next(a["data"] for a in cards.posted[-1]["card"]["actions"] if a["verb"] == "approve")
        res = await appr.on_click("approve", data, "aad-p", "Prince Alex")
        check("someone else (Prince) can't approve Karthi's email (policy: requester or owner)",
              "message" in res and st.pending(p["id"])["status"] == "pending", res)
        res = await appr.on_click("approve", data, "aad-k", "Karthi M")
        await drain()
        check("Karthi approves in the meeting chat: email sent exactly once",
              len(fg.sent) == 1 and st.pending(p["id"])["status"] == "done", st.pending(p["id"])["status"])
        check("the outcome is said in the call while it lasts",
              app.sent[-1] == (CONV, "Done: I emailed Elena the final numbers.") and not posts, app.sent[-1])
        state = (await graph.aget_state({"configurable": {"thread_id": r["runId"]}})).values
        check("every tool call has exactly one result", not tool_pair_problems(state["messages"]))

        # ---------------------------------------------------------------- 5. approved after the call ended
        graph, appr, fg, cards, model, runs, locks, deps = setup(email_call("Pilot quote"), ai_text("Done: emailed Elena."))
        call, app = new_call()
        call.session.transcript = [("Karthi M", "Max, email Elena about the pilot quote")]
        r = await ma.run_request(call, "Karthi M", "aad-k", "Max, email Elena about the pilot quote", graph=graph,
                                 store=st, approvals=appr, runs=runs, locks=locks)
        call.finished = True                                  # the meeting is over
        data = next(a["data"] for a in cards.posted[-1]["card"]["actions"] if a["verb"] == "approve")
        await appr.on_click("approve", data, "aad-k", "Karthi M")
        await drain()
        check("approved after the meeting ended: the outcome is posted in the meeting thread instead",
              posts and posts[-1] == ("Done: emailed Elena.", ROOT_ID) and len(app.sent) == 1, (posts[-1:], app.sent))

        # ---------------------------------------------------------------- 5b. "Change" in the meeting chat
        graph, appr, fg, cards, model, runs, locks, deps = setup(
            email_call("Go-live"), email_call("Go-live (1 May)"), ai_text("Done: sent with 1 May."))
        call, app = new_call()
        call.session.transcript = [("Karthi M", "Max, email Elena the go-live date")]
        r = await ma.run_request(call, "Karthi M", "aad-k", "Max, email Elena the go-live date", graph=graph,
                                 store=st, approvals=appr, runs=runs, locks=locks)
        from agent.graph import resume_run
        data = next(a["data"] for a in cards.posted[-1]["card"]["actions"] if a["verb"] == "change")
        res = await appr.on_click("change", {**data, "edit": "go-live is 1 May"}, "aad-k", "Karthi M")
        await drain()
        result = await graph.aget_state({"configurable": {"thread_id": r["runId"]}})
        await ma.announce_pause(call, {"__interrupt__": result.interrupts}, st, appr, updated=True)
        check("after 'Change' a new card is posted and Max says the UPDATED version is in the chat",
              len(cards.posted) >= 2 and app.sent[-1][1] ==
              "I've put the updated email in the meeting chat for Karthi M to approve.", app.sent[-1:])
        mine = [x for x in st.pendings(T) if x["run_id"] == r["runId"]]
        check("notes skip the replaced version (only the final one is listed)",
              [x["status"] for x in mine] == ["superseded", "pending"] and
              ma.done_section(mine).count("email") == 1 and "Waiting for approval" in ma.done_section(mine),
              ma.done_section(mine))

        # ---------------------------------------------------------------- 6. policy still applies in meetings
        st.set_policy(T, "mail.send", "owners", "requester_or_owner", "test")
        graph, appr, fg, cards, model, runs, locks, deps = setup(ai_text("Sorry, only the team owner can ask me to send emails."))
        call, app = new_call()
        call.session.transcript = [("Jacob Thomas", "Max, email Elena the campaign plan")]
        await ma.run_request(call, "Jacob Thomas", "aad-j", "Max, email Elena the campaign plan", graph=graph,
                             store=st, approvals=appr, runs=runs, locks=locks)
        offered = model.tool_names[-1]
        sysmsg = model.calls[0][0].content
        check("team policy applies in meetings too: Jacob (not owner) isn't offered send_email, told why",
              "doesn't let Jacob Thomas use" in sysmsg and "send_email" not in offered and "search_memory" in offered,
              offered)
        st.set_policy(T, "mail.send", "everyone", "requester_or_owner", "test")

        # ---------------------------------------------------------------- 7. notes list what was done
        call, app = new_call()
        call.recording = True
        call.run_ids = list(dict.fromkeys(x["run_id"] for x in st.pendings(T) if x["requester"] == "Karthi M"))
        call.session.transcript = [("Karthi M", "Let's start."), ("Prince Alex", "Total is 11,500K.")]
        call.session.summarize = lambda: {"summary": "We closed the budget.", "decisions": ["Total 11,500K."],
                                          "action_items": [], "risks": [], "final_total_k": 11500}
        await call.finish()
        notes = app.sent[-1][1]
        check("meeting notes include 'Done during the meeting' with each action's outcome and who approved",
              "**Done during the meeting**" in notes and "✅ Done (approved by Karthi M): email 'Final H1 numbers'" in notes
              and "email 'Pilot quote'" in notes and "⏳ Waiting for approval: email 'Go-live (1 May)'" in notes
              and "'Go-live'," not in notes, notes[-600:])

        # ---------------------------------------------------------------- 8. meeting chat link in invites
        body = invite_body(st, {"agenda": "Riverside quote", "threadRoot": ROOT_ID, "teamId": T})
        src = (ROOT / "simulations" / "rmeet" / "server.py").read_text(encoding="utf-8")
        pattern = re.search(r'THREAD_LINK = re\.compile\(r"(.+?)"\)', src).group(1)
        found = re.search(pattern, body)
        check("invites Max books carry a Teams deep link to the meeting's channel thread (the meeting chat)",
              body.startswith("Riverside quote\n\nMeeting chat and notes: https://teams.microsoft.com/l/message/")
              and f"parentMessageId={ROOT_ID}" in body and found and found.group(1) == ROOT_ID, body)
        check("no thread -> the agenda is unchanged",
              invite_body(st, {"agenda": "x", "threadRoot": None, "teamId": T}) == "x")
        check("channel requests keep the channel prompt (Markdown, @mentions)",
              "light Markdown" in system_prompt(deps, {"teamId": T, "source": "mention", "requester": "Karthi M"}, []))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


asyncio.run(main())
print("\nMEETING ACTIONS:", "ALL PASS" if not fails else f"{fails} FAILED")
sys.exit(1 if fails else 0)
