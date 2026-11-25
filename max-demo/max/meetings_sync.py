"""
Max finds the team's Teams meetings and their official transcripts through Microsoft Graph.

Algorithm (docs/research/teams/02-graph-knowledge-apis.md §6 "Recommended Max algorithm"):
  1. team members                       GET /teams/{id}/members                  (RSC TeamMember.Read.Group)
  2. each member's calendar             GET /users/{id}/calendarView             (Calendars.Read, admin consent)
  3. keep Teams meetings, dedupe on iCalUId
  4. resolve the online meeting         GET /users/{organizer}/onlineMeetings?$filter=JoinWebUrl eq '...'
                                        (OnlineMeetings.Read.All + application access policy)
  5. transcripts (WebVTT)               GET .../onlineMeetings/{id}/transcripts[/{id}/content]
                                        (OnlineMeetingTranscript.Read.All + policy + tenant switch)
Each step can be blocked by a tenant setting; Max records why instead of failing.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, unquote, urlsplit

from graph_client import GraphClient, GraphError

REASONS = {
    "calendar": "I can't read the team's calendars yet: an admin needs to grant consent for Calendars.Read.",
    "meetings": "I can't open meeting records yet: an admin needs to consent to OnlineMeetings.Read.All and assign me "
                "an application access policy.",
    "GraphAccessToTranscriptsDisabled": "Meeting transcripts are switched off for this tenant "
                                        "(Teams admin setting 'Graph API access to transcripts').",
    "transcripts": "I can't read meeting transcripts yet: an admin needs to consent to OnlineMeetingTranscript.Read.All "
                   "(with an application access policy).",
}


def parse_vtt(vtt: str) -> list[dict]:
    """WebVTT with <v Speaker> tags -> [{start, speaker, text}]."""
    cues, start = [], None
    for line in vtt.splitlines():
        line = line.strip()
        m = re.match(r"^(\d\d):(\d\d):(\d\d(?:\.\d+)?)\s+-->", line)
        if m:
            start = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
            continue
        v = re.match(r"^<v ([^>]+)>(.*?)(?:</v>)?$", line)
        if v and start is not None:
            cues.append({"start": round(start, 1), "speaker": v.group(1).strip(), "text": v.group(2).strip()})
    return cues


def organizer_from_join_url(url: str) -> str | None:
    try:
        ctx = parse_qs(urlsplit(url).query).get("context", [""])[0]
        return json.loads(unquote(ctx)).get("Oid")
    except (ValueError, AttributeError):
        return None


async def sync_meetings(graph: GraphClient, team_id: str, days_back: int = 120, days_ahead: int = 30) -> dict:
    """Returns {"meetings": [...], "access": {...}} — never raises for permission problems."""
    access = {"calendar": "ok", "meetings": "ok", "transcripts": "ok"}
    meetings: dict[str, dict] = {}
    members = await graph.get_all(f"/teams/{team_id}/members")
    now = datetime.now(timezone.utc)
    window = {"startDateTime": (now - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "endDateTime": (now + timedelta(days=days_ahead)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    for mem in members:
        uid = mem.get("userId")
        if not uid:
            continue
        try:
            events = await graph.get_all(f"/users/{uid}/calendarView", window)
        except GraphError as e:
            if e.status in (401, 403):
                access["calendar"] = REASONS["calendar"]
                break
            raise
        for ev in events:
            if not ev.get("isOnlineMeeting") or ev.get("onlineMeetingProvider") != "teamsForBusiness":
                continue
            join = (ev.get("onlineMeeting") or {}).get("joinUrl")
            if not join or ev["iCalUId"] in meetings:
                continue
            meetings[ev["iCalUId"]] = {
                "subject": ev.get("subject"), "start": ev["start"]["dateTime"][:16].replace("T", " "),
                "end": ev["end"]["dateTime"][:16].replace("T", " "), "joinUrl": join,
                "organizer": ((ev.get("organizer") or {}).get("emailAddress") or {}).get("name"),
                "organizerId": organizer_from_join_url(join), "onlineMeetingId": None,
                "transcripts": [], "transcriptNote": None}

    for m in meetings.values():
        if access["meetings"] != "ok" or not m["organizerId"]:
            m["transcriptNote"] = access["meetings"] if access["meetings"] != "ok" else "Organizer unknown."
            continue
        try:
            found = await graph.get(f"/users/{m['organizerId']}/onlineMeetings",
                                    {"$filter": f"JoinWebUrl eq '{m['joinUrl']}'"})
            om = (found.get("value") or [None])[0]
        except GraphError as e:
            if e.status in (401, 403):
                access["meetings"] = REASONS["meetings"]
                m["transcriptNote"] = access["meetings"]
                continue
            raise
        if not om:
            continue
        m["onlineMeetingId"] = om["id"]
        await fetch_transcripts(graph, m, access)
    return {"meetings": sorted(meetings.values(), key=lambda m: m["start"]), "access": access}


async def fetch_transcripts(graph: GraphClient, m: dict, access: dict | None = None) -> None:
    access = access if access is not None else {}
    if access.get("transcripts", "ok") != "ok":
        m["transcriptNote"] = access["transcripts"]
        return
    base = f"/users/{m['organizerId']}/onlineMeetings/{m['onlineMeetingId']}/transcripts"
    try:
        listed = await graph.get_all(base)
        out = []
        for t in listed:
            vtt = await graph.get_text(f"{base}/{t['id']}/content", {"$format": "text/vtt"})
            out.append({"id": t["id"], "created": t.get("createdDateTime", "")[:16].replace("T", " "),
                        "cues": parse_vtt(vtt)})
        m["transcripts"] = out
        m["transcriptNote"] = None if out else "No transcript (transcription wasn't started)."
    except GraphError as e:
        if e.status in (401, 403):
            reason = REASONS.get(e.code) or REASONS["transcripts"]
            access["transcripts"] = reason
            m["transcriptNote"] = reason
        else:
            raise
