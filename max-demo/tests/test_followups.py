"""
Step 4.2 offline tests: tasks from meeting notes, reminder jobs and the job runner (fake clock, fake poster).
No model calls, $0.   .venv\\Scripts\\python tests\\test_followups.py
"""

import asyncio
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "max"))

import followups  # noqa: E402
from agent.clock import FakeClock  # noqa: E402
from jobs import JobRunner  # noqa: E402
from store import Store  # noqa: E402

fails = 0
T = "T1"


def check(name: str, ok, detail="") -> None:
    global fails
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f"  [{detail}]" if detail != "" else ""))


def utc(*a) -> datetime:
    return datetime(*a, tzinfo=timezone.utc)


class Poster:
    def __init__(self):
        self.posts, self.fail_next = [], 0

    async def __call__(self, team_id, text, mentions=None, root_id=None):
        if self.fail_next:
            self.fail_next -= 1
            raise RuntimeError("connector down")
        self.posts.append({"team": team_id, "text": text, "mentions": mentions or [], "root": root_id})
        return f"m{len(self.posts)}"


NOTES = {"action_items": [
    {"owner": "Prince", "task": "Budget v3", "due": "2026-11-24"},
    {"owner": "Daniel", "task": "Confirm Vector's Riverside quote", "due": "2026-11-25"},
    {"owner": "Jacob Thomas", "task": "Update campaign plan to option B", "due": ""},
    {"owner": "", "task": "", "due": "2026-11-26"}]}


async def main() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        st = Store(tmp / "max.db")
        st.save_team({"teamId": T, "teamName": "Planning", "channelId": "C1"})
        for name, aad in (("Prince Alex", "aad-p"), ("Daniel", "aad-d"), ("Jacob Thomas", "aad-j"), ("Karthi M", "aad-k")):
            st.touch_person(T, name, aad)
        clock = FakeClock(utc(2026, 11, 20, 12, 0))
        poster = Poster()
        runner = JobRunner(st, clock, followups.handlers(st, clock, poster))

        # ---------------------------------------------------------------- tasks from notes
        ids = followups.save_meeting_tasks(st, T, NOTES, "H1 FY2027 Budget Review", "root-1", clock)
        tasks = {t["title"]: t for t in st.tasks(T, None)}
        check("3 tasks saved from 4 action items (the empty one skipped)", len(ids) == 3, list(tasks))
        check("owner 'Prince' resolved to Prince Alex with his AAD id, 'Daniel' to Daniel",
              tasks["Budget v3"]["owner"] == "Prince Alex" and tasks["Budget v3"]["owner_aad"] == "aad-p"
              and tasks["Confirm Vector's Riverside quote"]["owner"] == "Daniel"
              and tasks["Confirm Vector's Riverside quote"]["owner_aad"] == "aad-d")
        check("task keeps its meeting and thread", tasks["Budget v3"]["source_ref"] == "H1 FY2027 Budget Review"
              and tasks["Budget v3"]["thread_root"] == "root-1")
        again = followups.save_meeting_tasks(st, T, NOTES, "H1 FY2027 Budget Review", "root-1", clock)
        check("saving the same notes again adds nothing", again == [] and len(st.tasks(T, None)) == 3)
        jobs = st.jobs(T)
        check("2 jobs per task with a due date (due-tomorrow + overdue chase), none without",
              len(jobs) == 4 and {j["kind"] for j in jobs} == {"remind_task_due", "chase_overdue"}, len(jobs))
        due_job = next(j for j in jobs if j["kind"] == "remind_task_due" and "Budget" not in j["payload"]
                       and j["run_at"] == utc(2026, 11, 23, 9, 0).timestamp())
        check("Budget v3 (due Tue 24 Nov) reminder at 09:00 the day before (team zone UTC)", due_job is not None)

        # ---------------------------------------------------------------- runner timing
        r = await runner.tick()
        check("nothing runs before its time", not poster.posts and r["done"] == 0)
        clock.set(utc(2026, 11, 23, 9, 2))
        r = await runner.tick()
        p = poster.posts[-1] if poster.posts else {}
        check("on time: one 'due tomorrow' reminder posted", r["done"] == 1 and len(poster.posts) == 1, r)
        check("reminder @mentions the owner by AAD id, in the meeting's thread",
              p.get("mentions") == [("Prince Alex", "aad-p")] and "<at>Prince Alex</at>" in p.get("text", "")
              and p.get("root") == "root-1", p)
        check("reminder text names the task and the day", "Budget v3" in p["text"] and "Tue 24 Nov" in p["text"], p["text"])
        await runner.tick()
        check("a reminder is never posted twice", len(poster.posts) == 1)

        # ---------------------------------------------------------------- closing a task cancels its chase
        followups.close_task(st, tasks["Budget v3"]["id"])
        clock.set(utc(2026, 11, 25, 9, 1))
        r = await runner.tick()
        texts = [x["text"] for x in poster.posts[1:]]
        check("closed task: no overdue chase", not any("Budget v3" in t and "still open" in t for t in texts), texts)
        check("open task due 25 Nov: due-tomorrow reminder came on 24 Nov? (missed if Max was off)",
              any(j["status"] in ("done", "missed") for j in st.jobs(T) if j["kind"] == "remind_task_due"))

        # ---------------------------------------------------------------- missed: too late is better not sent
        clock.set(utc(2026, 11, 28, 9, 0))
        before = len(poster.posts)
        r = await runner.tick()
        check("a chase more than a day late is marked missed, not posted",
              r["missed"] >= 1 and len(poster.posts) == before, r)

        # ---------------------------------------------------------------- retries
        tid = st.add_task(T, "Retry me", "Karthi M", "2026-12-02", "manual", "x", None, "aad-k")
        followups.schedule_task_jobs(st, T, tid, clock)
        clock.set(utc(2026, 12, 1, 9, 0))
        poster.fail_next = 1
        r = await runner.tick()
        check("post failed: job goes back to pending for a retry", r["retry"] == 1, r)
        clock.set(utc(2026, 12, 1, 9, 2))
        r = await runner.tick()
        check("retry a minute later succeeds", r["done"] == 1 and "Retry me" in poster.posts[-1]["text"], r)

        tid = st.add_task(T, "Always fails", "Karthi M", "2026-12-05", "manual", "y", None, "aad-k")
        followups.schedule_task_jobs(st, T, tid, clock)
        clock.set(utc(2026, 12, 4, 9, 0))
        poster.fail_next = 99
        for minutes in (0, 2, 7):
            clock.set(utc(2026, 12, 4, 9, minutes))
            await runner.tick()
        poster.fail_next = 0
        j = next(j for j in st.jobs(T) if j["payload"] == f'{{"taskId": {tid}}}' and j["kind"] == "remind_task_due")
        check("after 3 failed tries the job is marked failed", j["status"] == "failed" and j["attempts"] == 3,
              (j["status"], j["attempts"]))

        # ---------------------------------------------------------------- interrupted jobs are not repeated
        jid = st.add_job(T, "remind_meeting", utc(2026, 12, 4, 9, 0).timestamp(), {"subject": "x"}, "interrupted-1")
        claimed = st.claim_jobs(utc(2026, 12, 4, 9, 10).timestamp(), lock_s=60)
        check("a claimed job is handed out once", [c["id"] for c in claimed] == [jid]
              and st.claim_jobs(utc(2026, 12, 4, 9, 10).timestamp()) == [])
        clock.set(utc(2026, 12, 4, 9, 12))
        before = len(poster.posts)
        r = await runner.tick()
        check("Max stopped mid-job: marked failed, not re-posted (at most once)",
              r["interrupted"] == 1 and len(poster.posts) == before, r)

        # ---------------------------------------------------------------- meeting reminders
        clock.set(utc(2026, 12, 7, 8, 0))
        meetings = [{"subject": "Pilot follow-up", "start": "2026-12-08 10:00", "joinUrl": "https://join/1"},
                    {"subject": "Old one", "start": "2026-11-01 10:00", "joinUrl": "https://join/0"}]
        n = followups.schedule_meeting_reminders(st, T, meetings, clock)
        n2 = followups.schedule_meeting_reminders(st, T, meetings, clock)
        check("upcoming meeting: 24 h + 15 min reminders; past meeting none; no duplicates on re-sync",
              n == 2 and n2 == 0, (n, n2))
        st.add_task(T, "Bring the Vector quote", "Daniel", "2026-12-09", "manual", "z", None, "aad-d")
        clock.set(utc(2026, 12, 8, 9, 46))
        r = await runner.tick()
        txt = poster.posts[-1]["text"]
        check("15-minute reminder posted with join link and open action items",
              "starts in 15 minutes" in txt and "https://join/1" in txt and "Bring the Vector quote" in txt, txt[:160])
        check("the 24 h reminder that was due yesterday at 10:00 was missed, not posted late",
              any(j["status"] == "missed" and '"label": "24h"' in j["payload"] for j in st.jobs(T)))

        # ---------------------------------------------------------------- deadline moved
        tid = st.add_task(T, "Moved task", "Prince Alex", "2026-12-15", "manual", "m", "root-9", "aad-p")
        followups.schedule_task_jobs(st, T, tid, clock)
        st.update_task(tid, due="2026-12-18")
        followups.reschedule_task(st, T, tid, clock)
        mine = [j for j in st.jobs(T) if f'"taskId": {tid}' in j["payload"]]
        check("due date moved: old reminders cancelled, new ones for the new date",
              sum(j["status"] == "cancelled" for j in mine) == 2 and sum(j["status"] == "pending" for j in mine) == 2
              and any(j["run_at"] == utc(2026, 12, 17, 9, 0).timestamp() for j in mine if j["status"] == "pending"))

        # ---------------------------------------------------------------- two runners at once
        for i in range(10):
            st.add_job(T, "remind_meeting", utc(2026, 12, 8, 9, 50).timestamp(),
                       {"subject": f"Parallel {i}", "start": "2026-12-08 10:05", "label": "15m"}, f"par-{i}")
        clock.set(utc(2026, 12, 8, 9, 51))
        before = len(poster.posts)
        runner2 = JobRunner(st, clock, followups.handlers(st, clock, poster))
        await asyncio.gather(runner.tick(), runner2.tick())
        par = [p for p in poster.posts[before:] if "Parallel" in p["text"]]
        check("two runners at once: each of 10 jobs posted exactly once", len(par) == 10, len(par))

        # ---------------------------------------------------------------- time zone
        st.set_team_time_zone(T, "Asia/Kolkata")
        tid = st.add_task(T, "IST task", "Karthi M", "2026-12-20", "manual", "tz", None, "aad-k")
        followups.schedule_task_jobs(st, T, tid, clock)
        j = next(j for j in st.jobs(T) if f'"taskId": {tid}' in j["payload"] and j["kind"] == "remind_task_due")
        check("team in India: reminder at 09:00 IST (03:30 UTC)", j["run_at"] == utc(2026, 12, 19, 3, 30).timestamp())
        st.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\nFOLLOW-UPS: ALL PASS" if not fails else f"\nFOLLOW-UPS: {fails} FAILED")


asyncio.run(main())
sys.exit(1 if fails else 0)
