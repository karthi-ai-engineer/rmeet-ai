"""
External actions: things that leave the team (step 4.4: email; 4.5 meetings; 4.6 file upload).

Each action is a ToolSpec with risk EXTERNAL and three functions the approval machinery calls:
  prepare(ctx, args)          -> {"blocked": why} | {"payload": frozen dict, "facts": [(label, value)], "body": text,
                                  "kind": ..., "graph_id": ...}   checks the RULES (in code) and creates the draft
  execute(ctx, payload, gid)  -> result text                     runs only after approval, sends exactly the payload
  cleanup(ctx, payload, gid)                                     undo a draft after cancel / change / expiry
The model never sees a way around these: it only proposes; code checks and a person approves.

Rules for email (step 4.4):
  - every recipient must be a person in the company (directory lookup); outside addresses are blocked
  - attachments only from the team's channel files (by name), each listed on the card with its size
  - sent from Max's own mailbox (MAX_MAILBOX), which Exchange RBAC limits Max to
"""

import base64
import os
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from langchain_core.tools import tool

from agent.tools import EXTERNAL, READ, ToolContext, ToolSpec

MAX_ATTACHMENT = 3 * 1024 * 1024


def mailbox() -> str:
    return os.environ.get("MAX_MAILBOX", "").strip()


async def resolve_people(ctx: ToolContext, items: list[str]) -> tuple[list[dict], list[str]]:
    """Names or email addresses -> company people [{name, address, aad}] + problems (outside, unknown, ...)."""
    graph, st = ctx.extra.get("graph"), ctx.store
    from graph_client import GraphError   # Max's module (max/ on sys.path)
    out, problems = [], []
    for raw in items or []:
        s = (raw or "").strip().strip("<>").strip()
        if not s:
            continue
        try:
            if "@" in s:
                found = (await graph.get("/users", {"$filter": f"mail eq '{s.lower()}'"})).get("value", [])
                if not found:
                    problems.append(f"{s} is not a person in the company (Max only emails and invites company people)")
                    continue
            else:
                person = st.person(ctx.team_id, s)
                if person is not None and person["email"]:
                    out.append({"name": person["name"], "address": person["email"], "aad": person["aad_id"]})
                    continue
                found = (await graph.get("/users", {"$filter": f"startswith(displayName,'{s.lower()}')"})).get("value", [])
                if not found:
                    problems.append(f"there is no one called '{s}' in the company directory")
                    continue
                if len(found) > 1:
                    problems.append(f"'{s}' matches several people ({', '.join(f['displayName'] for f in found)}): "
                                    "use the full name or email")
                    continue
        except GraphError as e:
            problems.append(f"I can't look people up in the directory yet (Graph said {e.status} {e.code}: an admin "
                            "needs to consent to User.ReadBasic.All)")
            continue
        u = found[0]
        out.append({"name": u["displayName"], "address": u["mail"], "aad": u["id"]})
    seen, unique = set(), []
    for p in out:
        if p["address"].lower() not in seen:
            seen.add(p["address"].lower())
            unique.append(p)
    return unique, problems


def _addrs(people: list[dict]) -> list[dict]:
    return [{"emailAddress": {"name": p["name"], "address": p["address"]}} for p in people]


def _fmt(people: list[dict]) -> str:
    return ", ".join(f"{p['name']} <{p['address']}>" for p in people)


# ----------------------------------------------------------------------------- email
@tool
def send_email(to: list[str], subject: str, body: str, cc: list[str] | None = None,
               attachments: list[str] | None = None) -> str:
    """Email people in the company from Max's mailbox (max@...). to / cc: names or email addresses of company
    people. body: the full plain-text email. attachments: names of files in the team channel. The requester or the
    manager sees the full email on an approval card and approves it before it is sent; call this directly."""
    return "handled by the approval gate"


async def email_prepare(ctx: ToolContext, args: dict) -> dict:
    graph, st = ctx.extra.get("graph"), ctx.store
    from graph_client import GraphError
    box = mailbox()
    if not box or graph is None:
        return {"blocked": "Max has no mailbox configured (MAX_MAILBOX)"}
    subject, body = (args.get("subject") or "").strip(), (args.get("body") or "").strip()
    if not subject or not body:
        return {"blocked": "an email needs a subject and a body"}
    to, p1 = await resolve_people(ctx, args.get("to") or [])
    cc, p2 = await resolve_people(ctx, args.get("cc") or [])
    if p1 or p2:
        return {"blocked": "; ".join(p1 + p2)}
    if not to:
        return {"blocked": "no recipients"}
    files, atts = st.files(ctx.team_id), []
    team = st.team(ctx.team_id) or {}
    for name in args.get("attachments") or []:
        f = next((f for f in files if f["name"].lower() == name.lower()), None) or \
            next((f for f in files if name.lower() in f["name"].lower()), None)
        if f is None:
            return {"blocked": f"there is no channel file named like '{name}' (attachments must be team files)"}
        try:
            data = await graph.download(team.get("driveId"), f["id"])
        except Exception as e:  # noqa: BLE001
            return {"blocked": f"couldn't read the file {f['name']}: {e}"}
        if len(data) > MAX_ATTACHMENT:
            return {"blocked": f"{f['name']} is larger than 3 MB"}
        atts.append({"name": f["name"], "fileId": f["id"], "size": len(data), "data": data})
    try:
        draft = await graph.post(f"/users/{box}/messages", {
            "subject": subject, "body": {"contentType": "text", "content": body},
            "toRecipients": _addrs(to), "ccRecipients": _addrs(cc)})
        for a in atts:
            await graph.post(f"/users/{box}/messages/{draft['id']}/attachments", {
                "@odata.type": "#microsoft.graph.fileAttachment", "name": a["name"],
                "contentBytes": base64.b64encode(a["data"]).decode()})
    except GraphError as e:
        why = ("an admin needs to consent to Mail.ReadWrite for Max's mailbox" if e.status in (401, 403)
               else f"Graph said {e.status} {e.code}")
        return {"blocked": f"I can't prepare the email in my mailbox: {why}"}
    payload = {"from": box, "to": to, "cc": cc, "subject": subject, "body": body,
               "attachments": [{"name": a["name"], "fileId": a["fileId"], "size": a["size"]} for a in atts]}
    facts = [("From", f"Max (AI) <{box}>"), ("To", _fmt(to))]
    if cc:
        facts.append(("Cc", _fmt(cc)))
    facts.append(("Subject", subject))
    if atts:
        facts.append(("Attachments", ", ".join(f"{a['name']} ({max(1, a['size'] // 1024)} KB)" for a in atts)))
    return {"payload": payload, "facts": facts, "body": body, "kind": "email", "graph_id": draft["id"],
            "title": "Email for approval"}


async def email_execute(ctx: ToolContext, payload: dict, graph_id: str) -> str:
    from graph_client import GraphError
    graph = ctx.extra.get("graph")
    try:
        await graph.post(f"/users/{payload['from']}/messages/{graph_id}/send", {})
    except GraphError as e:
        if e.status == 404:
            return "not sent now: the draft was already sent or deleted (nothing sent twice)"
        if e.status in (401, 403):
            return "not sent: an admin needs to consent to Mail.Send for Max's mailbox"
        return f"not sent: Graph said {e.status} {e.code}"
    names = ", ".join(p["name"] for p in payload["to"] + payload["cc"])
    return f"sent: email '{payload['subject']}' to {names}" + (
        f" with {len(payload['attachments'])} attachment(s)" if payload["attachments"] else "")


async def email_cleanup(ctx: ToolContext, payload: dict, graph_id: str | None) -> None:
    if graph_id:
        try:
            await ctx.extra["graph"].delete(f"/users/{payload['from']}/messages/{graph_id}")
        except Exception:  # noqa: BLE001  best effort: an unsent draft in Max's own mailbox is harmless
            pass


# ----------------------------------------------------------------------------- calendar (step 4.5)
def _tz(ctx: ToolContext):
    import followups   # Max's module: team time zone
    return followups.team_tz(ctx.store, ctx.team_id)


def _parse_local(value: str, tz) -> datetime | None:
    try:
        return datetime.fromisoformat(value.strip().replace("T", " ")[:16]).replace(tzinfo=tz)
    except (ValueError, AttributeError):
        return None


def _utc_str(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _graph_dt(v: dict) -> datetime:
    return datetime.fromisoformat(v["dateTime"][:19]).replace(tzinfo=timezone.utc)


def _span(start: datetime, end: datetime, tz) -> str:
    s, e = start.astimezone(tz), end.astimezone(tz)
    return f"{s:%a %d %b %Y %H:%M}–{e:%H:%M} ({tz.key})".replace(" 0", " ", 1)


async def _with_requester(ctx: ToolContext, people: list[dict]) -> list[dict]:
    """The person who asked is always invited."""
    if ctx.requester:
        me = ctx.store.person(ctx.team_id, ctx.requester)
        if me is not None and me["email"] and all(p["address"].lower() != me["email"].lower() for p in people):
            people = [{"name": me["name"], "address": me["email"], "aad": me["aad_id"]}] + people
    return people


async def busy_times(ctx: ToolContext, people: list[dict], start: datetime, end: datetime) -> dict:
    """{address: [(start, end, subject)]} from Microsoft Graph getSchedule on Max's calendar."""
    res = await ctx.extra["graph"].post(f"/users/{mailbox()}/calendar/getSchedule", {
        "schedules": [p["address"] for p in people],
        "startTime": {"dateTime": _utc_str(start), "timeZone": "UTC"},
        "endTime": {"dateTime": _utc_str(end), "timeZone": "UTC"}, "availabilityViewInterval": 30})
    out = {}
    for s in res.get("value", []):
        out[s["scheduleId"].lower()] = [(_graph_dt(i["start"]), _graph_dt(i["end"]), i.get("subject") or "busy")
                                        for i in s.get("scheduleItems", []) if i.get("status") != "free"]
    return out


def _conflicts(people: list[dict], busy: dict, start: datetime, end: datetime) -> list[str]:
    out = []
    for p in people:
        for s, e, subj in busy.get(p["address"].lower(), []):
            if s < end and e > start:
                out.append(f"{p['name']} is busy {s:%H:%M}–{e:%H:%M} UTC ({subj})")
    return out


@tool
def create_meeting(title: str, start: str, minutes: int = 30, attendees: list[str] | None = None,
                   agenda: str = "", asked_start: str = "") -> str:
    """Book a Teams meeting from Max's calendar and send the invites. start: 'YYYY-MM-DD HH:MM' in the team's time
    zone (use find_free_times first). attendees: company names or emails (the requester is added automatically).
    asked_start: the time the person asked for, when it isn't free and you propose `start` instead (the card then
    shows who is busy at the asked time). The requester or the manager approves the full invite on a card before it
    goes out; call this directly."""
    return "handled by the approval gate"


@tool
def cancel_meeting(meeting: str) -> str:
    """Cancel a Teams meeting that Max organised, found by words from its title or its date (YYYY-MM-DD).
    The requester or the manager approves on a card before attendees are told."""
    return "handled by the approval gate"


async def meeting_prepare(ctx: ToolContext, args: dict) -> dict:
    from graph_client import GraphError
    box, tz = mailbox(), _tz(ctx)
    title = (args.get("title") or "").strip()
    start = _parse_local(args.get("start") or "", tz)
    minutes = int(args.get("minutes") or 30)
    if not title or start is None:
        return {"blocked": "a meeting needs a title and a start like 2026-11-24 10:30"}
    if not 5 <= minutes <= 480:
        return {"blocked": "a meeting must be between 5 minutes and 8 hours"}
    end = start + timedelta(minutes=minutes)
    if start <= ctx.clock.now() + timedelta(minutes=5):
        return {"blocked": "that time has already passed (or is too soon): pick a later time"}
    people, problems = await resolve_people(ctx, args.get("attendees") or [])
    if problems:
        return {"blocked": "; ".join(problems)}
    people = await _with_requester(ctx, people)
    if not people:
        return {"blocked": "no attendees"}
    try:
        busy = await busy_times(ctx, people, start - timedelta(minutes=1), end + timedelta(minutes=1))
    except GraphError as e:
        return {"blocked": f"I can't check calendars yet (Graph said {e.status} {e.code}: an admin needs to consent "
                           "to Calendars.Read / Calendars.ReadWrite for Max)"}
    clash = _conflicts(people, busy, start, end)
    if clash:
        return {"blocked": "; ".join(clash) + ". Pick another time (find_free_times)."}
    note = None
    asked = _parse_local(args.get("asked_start") or "", tz)
    if asked is not None and asked != start:      # checked here, not written by the model
        try:
            busy_then = await busy_times(ctx, people, asked - timedelta(minutes=1), asked + timedelta(minutes=minutes + 1))
            taken = _conflicts(people, busy_then, asked, asked + timedelta(minutes=minutes))
        except GraphError:
            taken = []
        if taken:
            note = (f"You asked for {asked.astimezone(tz):%a %d %b %H:%M}, but " + "; ".join(taken) +
                    f". This is the nearest time everyone is free; press Change for another time.")
    payload = {"organizer": box, "title": title, "startUtc": _utc_str(start), "endUtc": _utc_str(end),
               "tz": tz.key, "attendees": people, "agenda": (args.get("agenda") or "").strip(),
               "transactionId": uuid.uuid4().hex, "threadRoot": ctx.extra.get("threadRoot"), "teamId": ctx.team_id}
    facts = [("When", _span(start, end, tz)), ("Organizer", f"Max (AI) <{box}>"), ("Attendees", _fmt(people)),
             ("Teams meeting", "yes: the join link is created when you approve")]
    if payload["threadRoot"]:
        facts.append(("Meeting chat", "this channel thread: Max's answers, approvals and notes (link in the invite)"))
    return {"payload": payload, "facts": [("Title", title)] + facts, "body": payload["agenda"] or None,
            "kind": "meeting", "title": "Teams meeting for approval", "note": note}


def thread_link(channel_id: str, root: str, team_id: str) -> str:
    """Teams deep link to a channel thread (where Max keeps the meeting's chat, approvals and notes)."""
    from urllib.parse import quote
    return (f"https://teams.microsoft.com/l/message/{quote(channel_id, safe='')}/{root}"
            f"?groupId={team_id}&parentMessageId={root}")


def invite_body(st, payload: dict) -> str:
    body, root = payload["agenda"], payload.get("threadRoot")
    channel = (st.team(payload["teamId"]) or {}).get("channelId")
    if root and channel:
        body += ("\n\n" if body else "") + "Meeting chat and notes: " + thread_link(channel, root, payload["teamId"])
    return body


async def meeting_execute(ctx: ToolContext, payload: dict, graph_id: str | None) -> str:
    import followups
    from graph_client import GraphError
    graph, st = ctx.extra["graph"], ctx.store
    start = datetime.fromisoformat(payload["startUtc"]).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(payload["endUtc"]).replace(tzinfo=timezone.utc)
    try:
        busy = await busy_times(ctx, payload["attendees"], start - timedelta(minutes=1), end + timedelta(minutes=1))
        clash = _conflicts(payload["attendees"], busy, start, end)
        if clash:   # someone got busy while the card waited: never move the meeting silently
            return "not created: " + "; ".join(clash) + ". Propose a new time on a new card."
        ev = await graph.post(f"/users/{payload['organizer']}/events", {
            "subject": payload["title"], "body": {"contentType": "text", "content": invite_body(st, payload)},
            "start": {"dateTime": payload["startUtc"], "timeZone": "UTC"},
            "end": {"dateTime": payload["endUtc"], "timeZone": "UTC"},
            "attendees": [{"emailAddress": {"name": p["name"], "address": p["address"]}, "type": "required"}
                          for p in payload["attendees"]],
            "isOnlineMeeting": True, "onlineMeetingProvider": "teamsForBusiness",
            "transactionId": payload["transactionId"]})
    except GraphError as e:
        if e.status in (401, 403):
            return "not created: an admin needs to consent to Calendars.ReadWrite for Max's calendar"
        return f"not created: Graph said {e.status} {e.code}"
    join = (ev.get("onlineMeeting") or {}).get("joinUrl")
    team, root = payload["teamId"], payload.get("threadRoot")
    meeting = {"subject": payload["title"], "start": f"{start:%Y-%m-%d %H:%M}", "joinUrl": join, "threadRoot": root,
               "attendees": [{"name": x["name"], "aad": x.get("aad")} for x in payload["attendees"]],
               "agenda": payload["agenda"]}
    followups.schedule_meeting_reminders(st, team, [meeting], ctx.clock)
    if join:   # Max joins its own meeting when it starts (calendar meetings don't send Max a meetingStart event)
        st.add_job(team, "join_own_meeting", start.timestamp() - 30,
                   {"joinUrl": join, "subject": payload["title"], "threadRoot": root, "eventId": ev["id"],
                    "maxLateS": 20 * 60}, dedupe_key=f"join:{ev['id']}")
    tz = ZoneInfo(payload["tz"])
    return (f"created: Teams meeting '{payload['title']}' on {_span(start, end, tz)}; invites sent to "
            f"{', '.join(p['name'] for p in payload['attendees'])}; Teams link: {join}")


async def _max_events(ctx: ToolContext, days: int) -> list[dict]:
    now = ctx.clock.now()
    data = await ctx.extra["graph"].get(f"/users/{mailbox()}/calendarView", {
        "startDateTime": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endDateTime": (now + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")})
    return [e for e in data.get("value", []) if e.get("isOrganizer")]


async def cancel_prepare(ctx: ToolContext, args: dict) -> dict:
    from graph_client import GraphError
    q = (args.get("meeting") or "").strip().lower()
    try:
        events = await _max_events(ctx, 90)
    except GraphError as e:
        return {"blocked": f"I can't read my calendar (Graph said {e.status} {e.code})"}
    words = [w for w in q.split() if len(w) > 2]
    hits = [e for e in events if q in e["start"]["dateTime"][:10] or
            (words and all(w in e["subject"].lower() for w in words))]
    if not hits:
        return {"blocked": f"I haven't organised an upcoming meeting matching '{args.get('meeting')}'"}
    if len(hits) > 1:
        return {"blocked": "several meetings match: " + "; ".join(f"{e['subject']} ({e['start']['dateTime'][:16]})"
                                                                  for e in hits) + ". Be more specific."}
    e, tz = hits[0], _tz(ctx)
    start, end = _graph_dt(e["start"]), _graph_dt(e["end"])
    who = [a["emailAddress"]["name"] for a in e.get("attendees", [])]
    payload = {"organizer": mailbox(), "eventId": e["id"], "title": e["subject"], "startUtc": _utc_str(start),
               "joinUrl": (e.get("onlineMeeting") or {}).get("joinUrl")}
    return {"payload": payload, "facts": [("Cancel", e["subject"]), ("When", _span(start, end, tz)),
                                          ("Attendees told", ", ".join(who) or "-")],
            "kind": "meeting", "title": "Cancel this meeting?"}


async def cancel_execute(ctx: ToolContext, payload: dict, graph_id: str | None) -> str:
    import followups
    from graph_client import GraphError
    try:
        await ctx.extra["graph"].delete(f"/users/{payload['organizer']}/events/{payload['eventId']}")
    except GraphError as e:
        return f"not cancelled: Graph said {e.status} {e.code}"
    ctx.store.cancel_jobs(f"join:{payload['eventId']}")
    if payload.get("joinUrl"):
        ctx.store.cancel_jobs(followups.meeting_job_prefix(payload["joinUrl"]))
    return f"cancelled: '{payload['title']}' ({payload['startUtc'][:16].replace('T', ' ')} UTC); attendees are told"


def calendar_tools(ctx: ToolContext) -> list[ToolSpec]:
    from graph_client import GraphError

    @tool
    async def find_free_times(attendees: list[str], date: str, minutes: int = 30, earliest: str = "09:00",
                              latest: str = "18:00") -> str:
        """Find times on a date (YYYY-MM-DD, team time zone) when all attendees (company names or emails) are free.
        The person asking is included automatically. Returns the first free start times."""
        tz = _tz(ctx)
        day_start = _parse_local(f"{date} {earliest}", tz)
        day_end = _parse_local(f"{date} {latest}", tz)
        if day_start is None or day_end is None or day_end <= day_start:
            return "date must be YYYY-MM-DD and earliest/latest like 09:00 / 18:00"
        people, problems = await resolve_people(ctx, attendees)
        if problems:
            return "; ".join(problems)
        people = await _with_requester(ctx, people)
        try:
            busy = await busy_times(ctx, people, day_start, day_end)
        except GraphError as e:
            return f"can't read calendars (Graph said {e.status} {e.code})"
        now, slots, t = ctx.clock.now() + timedelta(minutes=15), [], day_start
        while t + timedelta(minutes=minutes) <= day_end and len(slots) < 6:
            if t >= now and not _conflicts(people, busy, t, t + timedelta(minutes=minutes)):
                slots.append(t)
            t += timedelta(minutes=30)
        names = ", ".join(p["name"] for p in people)
        if not slots:
            return f"No {minutes}-minute slot on {date} between {earliest} and {latest} when {names} are all free."
        return (f"Free for {names} on {date} ({tz.key}), {minutes} min: "
                + ", ".join(f"{s.astimezone(tz):%H:%M}" for s in slots))

    @tool
    async def list_my_meetings(days: int = 30) -> str:
        """List the upcoming Teams meetings Max has organised (title, time, attendees)."""
        try:
            events = await _max_events(ctx, max(1, min(days, 90)))
        except GraphError as e:
            return f"can't read my calendar (Graph said {e.status} {e.code})"
        tz = _tz(ctx)
        return "\n".join(f"- {e['subject']} | {_span(_graph_dt(e['start']), _graph_dt(e['end']), tz)} | "
                         f"{', '.join(a['emailAddress']['name'] for a in e.get('attendees', []))}"
                         for e in events) or "I have no upcoming meetings."

    return [ToolSpec(find_free_times, READ, "Calendars.Read (free/busy via getSchedule)", "meetings.read"),
            ToolSpec(list_my_meetings, READ, "Calendars.Read (Max's calendar)", "meetings.read"),
            ToolSpec(create_meeting, EXTERNAL, "Calendars.ReadWrite (Max's calendar only, Exchange RBAC)",
                     "meetings.create", prepare=meeting_prepare, execute=meeting_execute),
            ToolSpec(cancel_meeting, EXTERNAL, "Calendars.ReadWrite (Max's calendar only, Exchange RBAC)",
                     "meetings.cancel", prepare=cancel_prepare, execute=cancel_execute)]


# ----------------------------------------------------------------------------- SharePoint upload (step 4.6)
UPLOAD_TYPES = {".md": "text/markdown", ".txt": "text/plain", ".csv": "text/csv"}
MAX_UPLOAD = 1024 * 1024
CARD_PREVIEW = 4000


@tool
def upload_file(name: str, content: str) -> str:
    """Save a NEW text file (.md, .txt or .csv) in the team channel's files, e.g. a 'Budget v3 draft.md' Max wrote.
    content: the full file text. Max never overwrites an existing file: pick a new name. The requester or the
    manager approves the file (name + content) on a card before it is saved; call this directly."""
    return "handled by the approval gate"


async def upload_prepare(ctx: ToolContext, args: dict) -> dict:
    from graph_client import GraphError
    import re as _re
    name = _re.sub(r'[\\/:*?"<>|]+', "_", (args.get("name") or "").strip())
    content = args.get("content") or ""
    ext = os.path.splitext(name)[1].lower()
    if not name or ext not in UPLOAD_TYPES:
        return {"blocked": "Max can only save text files: give the file a name ending in .md, .txt or .csv"}
    if not content.strip():
        return {"blocked": "the file is empty"}
    data = content.encode("utf-8")
    if len(data) > MAX_UPLOAD:
        return {"blocked": "the file is larger than 1 MB"}
    if any(f["name"].lower() == name.lower() for f in ctx.store.files(ctx.team_id)):
        return {"blocked": f"a file named '{name}' already exists; Max never overwrites files: use a new name "
                           "(for example with 'v3' or a date)"}
    team = ctx.store.team(ctx.team_id) or {}
    try:
        folder = await ctx.extra["graph"].get(f"/teams/{ctx.team_id}/channels/{team.get('channelId')}/filesFolder")
    except GraphError as e:
        return {"blocked": f"I can't open the channel's files (Graph said {e.status} {e.code})"}
    payload = {"name": name, "content": content, "driveId": folder["parentReference"]["driveId"],
               "folderId": folder["id"], "teamId": ctx.team_id}
    shown = content if len(content) <= CARD_PREVIEW else content[:CARD_PREVIEW] + f"\n… (+{len(content) - CARD_PREVIEW} more characters)"
    return {"payload": payload, "kind": "upload", "title": "New file for approval",
            "facts": [("File", name), ("Where", "Team channel files (General folder)"),
                      ("Size", f"{max(1, len(data) // 1024)} KB"), ("Overwrites", "nothing (new file)")],
            "body": shown}


async def upload_execute(ctx: ToolContext, payload: dict, graph_id: str | None) -> str:
    from urllib.parse import quote
    from graph_client import GraphError
    ext = os.path.splitext(payload["name"])[1].lower()
    try:
        item = await ctx.extra["graph"].put_bytes(
            f"/drives/{payload['driveId']}/items/{payload['folderId']}:/{quote(payload['name'])}:/content",
            payload["content"].encode("utf-8"), UPLOAD_TYPES.get(ext, "text/plain"),
            params={"@microsoft.graph.conflictBehavior": "fail"})
    except GraphError as e:
        if e.status == 409:
            return f"not uploaded: a file named '{payload['name']}' appeared in the meantime (nothing overwritten)"
        if e.status in (401, 403):
            return "not uploaded: an admin needs to grant Max write access to the team site (Sites.Selected)"
        return f"not uploaded: Graph said {e.status} {e.code}"
    return f"uploaded: '{item.get('name', payload['name'])}' is now in the channel files ({item.get('webUrl', '')})"


# ----------------------------------------------------------------------------- task date change (step 4.6)
@tool
def propose_task_update(task_id: int, due: str, reason: str) -> str:
    """Propose moving a task's due date (YYYY-MM-DD) because someone said its deadline changes. The task owner or
    the manager confirms on a card; then Max updates the task and its reminders."""
    return "handled by the approval gate"


async def task_update_prepare(ctx: ToolContext, args: dict) -> dict:
    from agent.tools import _date
    try:
        t = ctx.store.task(int(args.get("task_id")))
    except (TypeError, ValueError):
        t = None
    if t is None or t["team_id"] != ctx.team_id or t["status"] != "open":
        return {"blocked": f"there is no open task #{args.get('task_id')}"}
    new = _date(args.get("due") or "")
    if new is None:
        return {"blocked": "due must be a date like 2026-11-27"}
    if new == t["due"]:
        return {"blocked": "that is already the due date"}
    payload = {"taskId": t["id"], "due": new, "old": t["due"], "title": t["title"]}
    return {"payload": payload, "kind": "task", "title": "Move this deadline?",
            "facts": [("Task", f"#{t['id']} {t['title']}"), ("Owner", t["owner"] or "?"),
                      ("Due", f"{t['due'] or 'none'} → {new}"), ("Why", (args.get("reason") or "")[:300])]}


async def task_update_execute(ctx: ToolContext, payload: dict, graph_id: str | None) -> str:
    import followups
    t = ctx.store.task(payload["taskId"])
    if t is None or t["status"] != "open":
        return "not changed: the task is no longer open"
    ctx.store.update_task(payload["taskId"], due=payload["due"])
    followups.reschedule_task(ctx.store, ctx.team_id, payload["taskId"], ctx.clock)
    return f"updated: task #{payload['taskId']} '{payload['title']}' is now due {payload['due']} (reminders moved)"


def action_tools(ctx: ToolContext) -> list[ToolSpec]:
    return [ToolSpec(send_email, EXTERNAL, "Mail.ReadWrite + Mail.Send (Max's mailbox only, Exchange RBAC)",
                     "mail.send", prepare=email_prepare, execute=email_execute,
                     preview=lambda a: f"Email to {', '.join(a.get('to') or [])}")] + calendar_tools(ctx) + [
        ToolSpec(upload_file, EXTERNAL, "Sites.Selected (write on the team site only)", "files.upload",
                 prepare=upload_prepare, execute=upload_execute),
        ToolSpec(propose_task_update, EXTERNAL, "local (confirmed by the owner or manager)", "tasks.write",
                 prepare=task_update_prepare, execute=task_update_execute)]


CLEANUP = {"send_email": email_cleanup}
