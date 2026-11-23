"""
Offline tests ($0) for two fixes found by Karthi in the channel (22 Nov 2026):
  1. "@Max yes go ahead" posted as a NEW post: Max gets its question from the other thread as context.
  2. Max's rules: never claim it did something no tool did; ask when a message is unclear; invite only the people
     named; a busy time goes on the approval card as the nearest free time, not a chat question.
  .venv\\Scripts\\python tests\\test_conversation.py
"""

import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "max"))

import conversation  # noqa: E402
from agent.clock import FakeClock  # noqa: E402
from agent.graph import Deps, system_prompt  # noqa: E402
from store import Store  # noqa: E402

fails = 0
T = "T1"


def check(name: str, ok, detail="") -> None:
    global fails
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f"  [{detail}]" if detail != "" else ""))


tmp = Path(tempfile.mkdtemp())
try:
    st = Store(tmp / "max.db")
    st.replace_team_content({"teamId": T, "teamName": "Planning", "channelId": "C", "driveId": "D", "posts": [],
                             "files": [], "meetings": []})
    now = time.time()

    def run(who, thread, asked, reply, ago_s, trigger="mention"):
        rid = st.start_run(T, trigger, who, thread)
        st.audit(rid, T, "question", {"from": who, "text": asked})
        st.finish_run(rid, "ok", reply)
        st.db.execute("UPDATE runs SET started_at = ? WHERE id = ?", (now - ago_s, rid))
        st.db.commit()

    run("Karthi M", "thread-A", "book a meeting tomorrow 11 am",
        "11:00 tomorrow is taken. The earliest time everyone is free is **12:00**. Who should I invite?", 120)
    ctx = conversation.earlier_question(st, T, "Karthi M", "thread-B", now)
    check("'yes go ahead' as a new post 2 min after Max asked a question elsewhere -> that exchange is the context",
          ctx and 'asked you: "book a meeting tomorrow 11 am"' in ctx and "Who should I invite?" in ctx
          and "(2 min ago)" in ctx and "approval card is still needed" in ctx, ctx)
    check("…not for someone else", conversation.earlier_question(st, T, "Prince Alex", "thread-B", now) is None)
    check("…not when the new post is in that same thread (the thread already has the context)",
          conversation.earlier_question(st, T, "Karthi M", "thread-A", now) is None)
    check("…not after 15 minutes", conversation.earlier_question(st, T, "Karthi M", "thread-B", now + 16 * 60) is None)
    run("Karthi M", "thread-C", "what's the budget gap?", "The gap is **220K**.", 30)
    check("…not when Max's latest reply to them wasn't a question",
          conversation.earlier_question(st, T, "Karthi M", "thread-B", now) is None)
    check("short posts count as possible answers ('yes go ahead', 'Prince and Daniel'); long ones don't",
          conversation.is_short_reply("yes go ahead") and conversation.is_short_reply("Prince and Daniel please")
          and not conversation.is_short_reply("can you tell me what we decided about the Northgate freight renegotiation "
                                              "in the last meeting?") and not conversation.is_short_reply(""))

    import json as _json
    st.add_pending({"id": "p1", "team_id": T, "run_id": "r9", "tool": "create_meeting", "call_id": "c", "payload": "{}",
                    "payload_hash": "h", "requester": "Karthi M", "requester_aad": "aad-k", "thread_root": "thread-D",
                    "status": "pending", "version": 1, "created_at": now - 60, "expires_at": now + 86400,
                    "preview": _json.dumps({"kind": "meeting", "title": "Teams meeting for approval",
                                            "facts": [["Title", "Meeting with Karthi M"], ["When", "Mon 23 Nov 11:00"]]})})
    ctx = conversation.earlier_question(st, T, "Karthi M", "thread-B", now)
    check("a card waiting in another thread: 'yes go ahead' -> Max points to the card (approving is a click)",
          ctx and "approval card" in ctx and "'Meeting with Karthi M', Mon 23 Nov 11:00" in ctx and
          "press Approve on that card" in ctx and "Don't create a second card" in ctx, ctx)
    check("…but not in the card's own thread", conversation.earlier_question(st, T, "Karthi M", "thread-D", now) is None
          or "approval card" not in conversation.earlier_question(st, T, "Karthi M", "thread-D", now))

    from datetime import datetime, timezone
    deps = Deps(st, None, FakeClock(datetime(2026, 11, 22, 12, 5, tzinfo=timezone.utc)), lambda ctx: [])
    sp = system_prompt(deps, {"teamId": T, "source": "mention", "requester": "Karthi M"}, [])
    check("rules: never claim an action no tool did; ask when a message is unclear on its own",
          "Never say you did, noted, approved or will do something unless a tool did it" in sp and
          "e.g. just 'yes' or 'go ahead'" in sp)
    check("rules: invite only the people named (ask if none); a busy time -> nearest free time on the card",
          "invite only the people the person names" in sp and "ask who to invite" in sp and
          "put the nearest time when everyone is free on the approval card" in sp)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\nCONVERSATION:", "ALL PASS" if not fails else f"{fails} FAILED")
sys.exit(1 if fails else 0)
