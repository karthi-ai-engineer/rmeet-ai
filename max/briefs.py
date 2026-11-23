"""
Pre-meeting brief (Phase 5.1): 15 minutes before a meeting Max knows, it posts in the meeting's thread:

  🗒️ Meeting brief: <title> · starts in 15 minutes (time, team time zone) · Join
  With: @attendees
  Agenda              from the invite Max booked
  Last time           decisions of the meeting this one follows on from (same Teams meeting / thread / title)
                      + how many of its action items are done
  Open action items   of the people in this meeting (overdue first), else the team's
  New since last time files added or updated in the channel since that meeting
  Waiting for approval  cards still open in this thread

No AI: everything comes from Max's database, so it costs nothing and can't invent anything. Sections with nothing
to say are left out.
"""

from datetime import datetime, timezone

MAX_DECISIONS, MAX_TASKS, MAX_FILES = 4, 8, 5


def _day(d: str | None, tz) -> str:
    try:
        return datetime.fromisoformat(d).strftime("%a %d %b").replace(" 0", " ") if d else ""
    except ValueError:
        return d or ""


def _file_time(t: str | None) -> float | None:
    """Files carry 'YYYY-MM-DD HH:MM' (UTC) or ISO times."""
    if not t:
        return None
    try:
        dt = datetime.fromisoformat(t.replace("Z", "+00:00").replace(" ", "T"))
        return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).timestamp()
    except ValueError:
        return None


def compose(store, team_id: str, p: dict, now: datetime, tz) -> tuple[str, list[tuple[str, str]]]:
    """(message text, mentions) for the 15-minute brief. p = the reminder job payload."""
    from followups import meeting_start                       # noqa: PLC0415  (followups imports this module)
    start = meeting_start(p)
    when = start.astimezone(tz).strftime("%a %d %b %H:%M").replace(" 0", " ") if start else (p.get("start") or "")
    title = p.get("subject") or "Meeting"
    lines = [f"🗒️ **Meeting brief: {title}** · starts in 15 minutes ({when} {tz.key})"]
    if p.get("joinUrl"):
        lines.append(f"[Join the meeting]({p['joinUrl']})")

    # who: @mention the invited team members (people only, never Max)
    mentions, names = [], []
    for a in p.get("attendees") or []:
        person = store.person(team_id, a.get("name") or "")
        if person and person["kind"] == "person":
            names.append(person["name"])
            if person["aad_id"]:
                mentions.append((person["name"], person["aad_id"]))
    if names:
        lines.append("With: " + ", ".join(f"<at>{n}</at>" if any(m[0] == n for m in mentions) else n for n in names))

    if (p.get("agenda") or "").strip():
        lines += ["", "**Agenda**", p["agenda"].strip()]

    # last time: the meeting this one follows on from
    before = start.timestamp() if start else now.timestamp()
    prev = store.previous_meeting_notes(team_id, before, p.get("joinUrl"), p.get("threadRoot"), title)
    if prev:
        held = datetime.fromtimestamp(prev["held_at"], timezone.utc).astimezone(tz).strftime("%a %d %b").replace(" 0", " ")
        decisions = [d for d in prev["notes"].get("decisions") or [] if isinstance(d, str) and d.strip()]
        lines += ["", f"**Last time** ({prev['title']}, {held})"]
        lines += [f"- {d}" for d in decisions[:MAX_DECISIONS]] or ["- No decisions were recorded."]
        if len(decisions) > MAX_DECISIONS:
            lines.append(f"- …and {len(decisions) - MAX_DECISIONS} more")
        theirs = [t for t in store.tasks(team_id, None) if t["source_kind"] == "meeting" and t["source_ref"] == prev["title"]]
        if theirs:
            done = sum(t["status"] == "done" for t in theirs)
            lines.append(f"- Action items from then: {done} of {len(theirs)} done")

    # open action items: the people in this meeting first (overdue first, then by due date)
    today = now.astimezone(tz).date().isoformat()
    open_tasks = list(store.tasks(team_id, "open"))
    mine = [t for t in open_tasks if t["owner"] in names] if names else open_tasks
    mine.sort(key=lambda t: (t["due"] or "9999-12-31", t["id"]))
    if mine:
        lines += ["", "**Open action items" + (" for this meeting's people**" if names else "**")]
        for t in mine[:MAX_TASKS]:
            late = bool(t["due"]) and t["due"] < today
            due = (f" (was due {_day(t['due'], tz)})" if late else f" (due {_day(t['due'], tz)})") if t["due"] else ""
            lines.append(f"- {'⚠️ ' if late else ''}{t['owner'] or '?'}: {t['title']}{due}")
        if len(mine) > MAX_TASKS:
            lines.append(f"- …and {len(mine) - MAX_TASKS} more")

    # what changed in the channel since last time
    if prev:
        new = [f for f in store.files(team_id) if (_file_time(f["time"]) or 0) > prev["held_at"]]
        if new:
            lines += ["", "**New since last time**"]
            lines += [f"- {f['name']}" + (f" ({f['author']})" if f["author"] else "") for f in new[:MAX_FILES]]
            if len(new) > MAX_FILES:
                lines.append(f"- …and {len(new) - MAX_FILES} more files")

    # approvals still open in this thread
    waiting = [x for x in store.pendings(team_id, "pending") if p.get("threadRoot") and x["thread_root"] == p["threadRoot"]]
    if waiting:
        import json
        lines += ["", "**Waiting for approval**"]
        for x in waiting:
            prev_card = json.loads(x["preview"])
            facts = dict(prev_card.get("facts") or [])
            what = facts.get("Title") or facts.get("Subject") or prev_card.get("title") or x["tool"]
            lines.append(f"- {prev_card.get('kind') or 'action'} '{what}' (asked by {x['requester'] or '?'})")

    lines += ["", "_I'll join to take notes. In the meeting, say \"Max, …\" to ask me something or get it done._"]
    return "\n".join(lines), mentions
