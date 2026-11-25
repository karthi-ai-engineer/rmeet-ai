"""
Follow-ups Max does on its own (step 4.2), with no model calls: plain templates, zero tokens.

  save_meeting_tasks       meeting notes' action items -> tasks (owner, due date) + their reminder jobs
  schedule_task_jobs       "due tomorrow" reminder (09:00 the day before) + one overdue chase (09:00 the day after)
  schedule_meeting_reminders   24 h and 15 min before each upcoming Teams meeting Max knows about
  handlers(...)            what each job does: posts in the channel (in the task's thread) with @mentions

Times: stored as UTC; dates and "09:00" are in the team's time zone (teams.time_zone, default UTC;
MAX_TEAM_TZ sets it for a new team). Microsoft Graph gives meeting times in UTC.
"""

import re
import hashlib
import os
from datetime import date, datetime, timedelta, timezone
from typing import Awaitable, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from agent.clock import Clock
from store import Store

REMIND_HOUR = 9
MEETING_OFFSETS = (("24h", timedelta(hours=24)), ("15m", timedelta(minutes=15)))

# post(team_id, text, mentions=[(name, aad_id)], root_id=None) -> message id
Poster = Callable[..., Awaitable[str | None]]


def team_tz(store: Store, team_id: str) -> ZoneInfo:
    t = store.team(team_id) or {}
    name = t.get("timeZone") or os.environ.get("MAX_TEAM_TZ") or "UTC"
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def at_local(day: date, hour: int, tz: ZoneInfo) -> float:
    return datetime(day.year, day.month, day.day, hour, 0, tzinfo=tz).timestamp()


def parse_day(value: str | None) -> date | None:
    try:
        return date.fromisoformat((value or "").strip()[:10])
    except ValueError:
        return None


def nice_day(d: date) -> str:
    return d.strftime("%a %d %b").replace(" 0", " ")


# ----------------------------------------------------------------------------- tasks
def schedule_task_jobs(store: Store, team_id: str, task_id: int, clock: Clock) -> int:
    """Due-tomorrow reminder + one overdue chase for an open task with a due date. Returns jobs added."""
    t = store.task(task_id)
    due = parse_day(t["due"]) if t else None
    if not t or t["status"] != "open" or not due:
        return 0
    tz = team_tz(store, team_id)
    now = clock.now().timestamp()
    added = 0
    for kind, day in (("remind_task_due", due - timedelta(days=1)), ("chase_overdue", due + timedelta(days=1))):
        run_at = at_local(day, REMIND_HOUR, tz)
        if kind == "remind_task_due" and run_at < now:
            continue                                   # created too late for a "due tomorrow" note
        if store.add_job(team_id, kind, max(run_at, now), {"taskId": task_id},
                         dedupe_key=f"task:{task_id}:{kind}:{due.isoformat()}") is not None:
            added += 1
    return added


def reschedule_task(store: Store, team_id: str, task_id: int, clock: Clock) -> int:
    """After a due-date change: drop the old reminders, schedule new ones."""
    store.cancel_jobs(f"task:{task_id}:")
    return schedule_task_jobs(store, team_id, task_id, clock)


def save_meeting_tasks(store: Store, team_id: str, notes: dict, meeting_title: str, thread_root: str | None,
                       clock: Clock) -> list[int]:
    """Action items from meeting notes -> tasks (deduplicated per meeting) + reminder jobs. Returns new task ids."""
    ids = []
    for item in notes.get("action_items") or []:
        title = (item.get("task") or "").strip()
        if not title:
            continue
        owner = (item.get("owner") or "").strip() or None
        person = store.person(team_id, owner) if owner else None
        if (owner and re.fullmatch(r"max(?:\s*\(ai\))?", owner, re.IGNORECASE)) or (person and person["kind"] != "person"):
            continue                               # Max (the AI) never owns a task: it would only remind itself
        due = parse_day(item.get("due"))
        tid = store.add_task(team_id, title, person["name"] if person else owner, due.isoformat() if due else None,
                             "meeting", meeting_title, thread_root, person["aad_id"] if person else None)
        if tid is not None:
            ids.append(tid)
            schedule_task_jobs(store, team_id, tid, clock)
    return ids


def close_task(store: Store, task_id: int, status: str = "done") -> None:
    store.update_task(task_id, status=status)
    store.cancel_jobs(f"task:{task_id}:")


# ----------------------------------------------------------------------------- meetings
def meeting_start(m: dict) -> datetime | None:
    try:
        return datetime.fromisoformat((m.get("start") or "").replace(" ", "T")[:16]).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _meeting_key(m: dict) -> str:
    return hashlib.sha1((m.get("joinUrl") or f"{m.get('subject')}|{m.get('start')}").encode()).hexdigest()[:16]


def meeting_job_prefix(join_url: str) -> str:
    """dedupe-key prefix of a meeting's reminder jobs (to cancel them when the meeting is cancelled)."""
    return f"meet:{_meeting_key({'joinUrl': join_url})}:"


def schedule_meeting_reminders(store: Store, team_id: str, meetings: list[dict], clock: Clock) -> int:
    now = clock.now()
    added = 0
    for m in meetings:
        start = meeting_start(m)
        if not start or start <= now:
            continue
        key = _meeting_key(m)
        for label, before in MEETING_OFFSETS:
            run_at = start - before
            if run_at < now:
                continue
            payload = {"subject": m.get("subject"), "start": m.get("start"), "joinUrl": m.get("joinUrl"),
                       "label": label, "threadRoot": m.get("threadRoot"),
                       "attendees": m.get("attendees") or [], "agenda": m.get("agenda") or ""}   # for the brief
            if store.add_job(team_id, "remind_meeting", run_at.timestamp(), payload,
                             dedupe_key=f"meet:{key}:{label}") is not None:
                added += 1
    return added


# ----------------------------------------------------------------------------- handlers (templates, no AI)
def mention(name: str | None, aad: str | None) -> tuple[str, list]:
    if name and aad:
        return f"<at>{name}</at>", [(name, aad)]
    return (name or "someone"), []


def handlers(store: Store, clock: Clock, post: Poster) -> dict:
    async def remind_task_due(job: dict) -> str | None:
        t = store.task(job["payload"]["taskId"])
        if not t or t["status"] != "open":
            return "skipped"
        who, ments = mention(t["owner"], t["owner_aad"])
        due = parse_day(t["due"])
        src = f" (from {t['source_ref']})" if t["source_ref"] else ""
        await post(job["team_id"], f"⏰ Reminder: {who}, **{t['title']}** is due tomorrow, {nice_day(due)}{src}.",
                   ments, t["thread_root"])
        return None

    async def chase_overdue(job: dict) -> str | None:
        t = store.task(job["payload"]["taskId"])
        if not t or t["status"] != "open":
            return "skipped"
        who, ments = mention(t["owner"], t["owner_aad"])
        due = parse_day(t["due"])
        await post(job["team_id"], f"📌 {who}, **{t['title']}** was due {nice_day(due)} and is still open. "
                                   "Is it done? Reply here with @Max and I'll update it.", ments, t["thread_root"])
        return None

    async def remind_meeting(job: dict) -> str | None:
        p = job["payload"]
        start = meeting_start(p)
        tz = team_tz(store, job["team_id"])
        if p.get("label") == "15m":               # 15 minutes before: the pre-meeting brief (no AI)
            import briefs
            text, mentions = briefs.compose(store, job["team_id"], p, clock.now(), tz)
            await post(job["team_id"], text, mentions, p.get("threadRoot"))
            return None
        when = start.astimezone(tz).strftime("%a %d %b %H:%M").replace(" 0", " ") if start else p.get("start")
        lead = "starts in 15 minutes" if p.get("label") == "15m" else "is tomorrow"
        lines = [f"⏰ **{p.get('subject') or 'Meeting'}** {lead} ({when} {tz.key})."]
        if p.get("joinUrl"):
            lines.append(f"[Join the meeting]({p['joinUrl']})")
        open_tasks = store.tasks(job["team_id"], "open")[:5]
        if open_tasks:
            lines.append("\nOpen action items:")
            lines += [f"- {t['owner'] or '?'}: {t['title']}" + (f" (due {nice_day(parse_day(t['due']))})"
                                                                if parse_day(t["due"]) else "") for t in open_tasks]
        await post(job["team_id"], "\n".join(lines), [], p.get("threadRoot"))
        return None

    return {"remind_task_due": remind_task_due, "chase_overdue": chase_overdue, "remind_meeting": remind_meeting}
