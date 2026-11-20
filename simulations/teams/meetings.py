"""
Calendar events, Teams online meetings and meeting transcripts (fake Microsoft Graph).

  GET /users/{id}/calendarView?startDateTime=&endDateTime=          role Calendars.Read
  GET /users/{id}/events/{event-id}                                  role Calendars.Read
  GET /users/{id}/onlineMeetings?$filter=JoinWebUrl eq '{url}'       role OnlineMeetings.Read.All + access policy
  GET /users/{id}/onlineMeetings/{meeting-id}                        role OnlineMeetings.Read.All + access policy
  GET /users/{id}/onlineMeetings/{meeting-id}/transcripts[/{id}[/content]]
                                       role OnlineMeetingTranscript.Read.All + access policy + tenant switch

Seeded with the 3 past Planning Department meetings (official transcripts as WebVTT)
and today's budget review. When a live meeting ends, its transcript is added and
subscribers are notified. Contract: docs/research/teams/02-graph-knowledge-apis.md §5-6.
"""

import base64
import hashlib
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote

import yaml

from httpx_types import Req, Resp, Router
from identity import GRAPH_AUDIENCE, Identity
from store import TENANT_ID, WORLD, TeamsStore, iso

NS = uuid.NAMESPACE_URL
LINE_RE = re.compile(r"^\[(\d\d):(\d\d):(\d\d)\]\s+\*\*(.+?):\*\*\s+(.*)$")


def _ms(dt: str) -> int:
    return int(datetime.fromisoformat(dt).replace(tzinfo=timezone.utc).timestamp() * 1000)


def vtt_time(sec: float) -> str:
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def build_vtt(cues: list[tuple[float, str, str]]) -> str:
    """cues: [(start_seconds, speaker, text)] -> WebVTT with <v Speaker> tags (Teams format)."""
    out = ["WEBVTT", ""]
    for i, (start, speaker, text) in enumerate(cues):
        end = cues[i + 1][0] if i + 1 < len(cues) else start + max(2.0, len(text.split()) / 2.6)
        end = max(end - 0.1, start + 0.5)
        out += [f"{vtt_time(start)} --> {vtt_time(end)}", f"<v {speaker}>{text}</v>", ""]
    return "\n".join(out)


class MeetingsData:
    def __init__(self, store: TeamsStore):
        self.store = store
        self.lock = threading.RLock()
        self.listeners = []
        self.meetings: dict[str, dict] = {}
        self.extra_transcripts: dict[str, list] = {}       # live transcripts added at runtime (not persisted)
        org = store.users["karthi"]
        for d in sorted((WORLD / "meetings").iterdir()):
            if not d.is_dir():
                continue
            lines = (d / "transcript.md").read_text(encoding="utf-8").splitlines()
            title = lines[0].lstrip("# ").replace("Transcript: ", "")
            start = _ms(f"{d.name[:10]}T10:00:00")
            cues = []
            for ln in lines:
                m = LINE_RE.match(ln.strip())
                if m:
                    hh, mm, ss, who, text = m.groups()
                    cues.append((int(hh) * 3600 + int(mm) * 60 + int(ss), who, text))
            end = start + int((cues[-1][0] + 30) * 1000) if cues else start + 45 * 60_000
            self._add(d.name, title, start, end, org, [build_vtt(cues)] if cues else [])
        scenario = yaml.safe_load((WORLD / "budget-review" / "scenario.yaml").read_text(encoding="utf-8"))["meeting"]
        start = _ms(str(scenario["date"]).replace(" ", "T")[:19])
        self._add("live-budget-review", scenario["title"], start, start + scenario["duration_min"] * 60_000, org, [])

    def on_change(self, fn) -> None:
        self.listeners.append(fn)

    def _add(self, key: str, title: str, start: int, end: int, org: dict, vtts: list[str]) -> None:
        h = hashlib.sha256(key.encode()).digest()
        thread = "19:meeting_" + base64.b64encode(h[:24]).decode().rstrip("=").replace("+", "a").replace("/", "b") + "@thread.v2"
        mid = base64.b64encode(f"1*{org['aadObjectId']}*0**{thread}".encode()).decode()
        ctx = quote('{"Tid":"%s","Oid":"%s"}' % (TENANT_ID, org["aadObjectId"]))
        join = f"https://teams.microsoft.com/l/meetup-join/{quote(thread, safe='')}/0?context={ctx}"
        self.meetings[key] = {
            "key": key, "title": title, "startMs": start, "endMs": end, "organizer": "karthi",
            "bfMeetingId": base64.b64encode(f"0#{thread}#0".encode()).decode(),     # Bot Framework meeting id
            "attendees": [k for k in self.store.users if k != "karthi"], "threadId": thread,
            "onlineMeetingId": mid, "joinUrl": join,
            "eventId": "AAMkAGI" + base64.urlsafe_b64encode(hashlib.sha1(key.encode()).digest()).decode().rstrip("="),
            "iCalUId": "040000008200E00074C5B7101A82E008" + hashlib.md5(key.encode()).hexdigest().upper(),
            "transcripts": [self._transcript(key, i, start, end, v) for i, v in enumerate(vtts)],
        }

    def _transcript(self, key: str, idx: int, start: int, end: int, vtt: str) -> dict:
        tid = base64.b64encode(f"1*{key}*{idx}*{uuid.uuid5(NS, key + str(idx))}".encode()).decode()
        return {"id": tid, "createdMs": start, "endMs": end, "vtt": vtt,
                "callId": str(uuid.uuid5(NS, f"call/{key}/{idx}")),
                "contentCorrelationId": str(uuid.uuid5(NS, f"corr/{key}/{idx}"))}

    def by_online_id(self, mid: str):
        return next((m for m in self.meetings.values() if m["onlineMeetingId"] == mid), None)

    def add_live_transcript(self, key: str, cues: list[tuple[float, str, str]]) -> dict | None:
        """Called when a simulated live meeting ends (transcription was running)."""
        if not cues:
            return None
        with self.lock:
            m = self.meetings[key]
            now = self.store.now_ms()
            t = self._transcript(key, len(m["transcripts"]), now - int((cues[-1][0] + 10) * 1000), now,
                                 build_vtt(cues))
            m["transcripts"].append(t)
        for fn in self.listeners:
            try:
                fn({"type": "transcript", "meeting": m, "transcript": t})
            except Exception:
                pass
        return t


class GraphMeetings:
    def __init__(self, base_url: str, identity: Identity, store: TeamsStore, data: MeetingsData, err):
        self.root = base_url.rstrip("/") + "/graph/v1.0"
        self.identity, self.store, self.data, self._err = identity, store, data, err

    def routes(self, r: Router) -> None:
        u = r"/graph/v1\.0/users/([^/?]+)"
        r.add("GET", u + r"/calendarView", self._calendar_view)
        r.add("GET", u + r"/events/([^/?]+)", self._event)
        r.add("GET", u + r"/onlineMeetings", self._find_meeting)
        r.add("GET", u + r"/onlineMeetings/([^/?]+)", self._meeting)
        r.add("GET", u + r"/onlineMeetings/([^/?]+)/transcripts", self._transcripts)
        r.add("GET", u + r"/onlineMeetings/([^/?]+)/transcripts/([^/?]+)", self._transcript)
        r.add("GET", u + r"/onlineMeetings/([^/?]+)/transcripts/([^/?]+)/content", self._content)

    # ------------------------------------------------------------ guards
    def _user(self, uid: str):
        uid = unquote(uid).lower()
        return next((k for k, u in self.store.users.items()
                     if u["aadObjectId"] == uid or u["email"].lower() == uid), None)

    def _guard(self, req: Req, uid: str, role: str, policy: bool = False, transcripts: bool = False):
        claims = self.identity.verify_app_token(req.bearer(), GRAPH_AUDIENCE)
        if not claims:
            return None, self._err(401, "InvalidAuthenticationToken", "Access token validation failure.")
        if role not in claims.get("roles", []):
            return None, self._err(403, "Forbidden", f"Missing role permissions on the request. API requires one of "
                                                     f"'{role}'. Roles on the request '{','.join(claims.get('roles', []))}'.")
        user = self._user(uid)
        if not user:
            return None, self._err(404, "ResourceNotFound" if not policy else "NotFound",
                                   f"User '{unquote(uid)}' not found.")
        if policy and not self.store.admin.get("accessPolicy"):
            return None, self._err(403, "Forbidden", "No application access policy found for this app")
        if transcripts and not self.store.admin.get("transcriptApiAccess"):
            return None, Resp.json(403, {"error": {"code": "Forbidden",
                                                   "message": "Graph API access to transcripts is disabled for this tenant.",
                                                   "innerError": {"code": "GraphAccessToTranscriptsDisabled"}}})
        return user, None

    def _meeting_for(self, user: str, mid: str):
        m = self.data.by_online_id(unquote(mid))
        if not m or (user != m["organizer"] and user not in m["attendees"]):
            return None
        return m

    # --------------------------------------------------------- resources
    def _addr(self, key: str) -> dict:
        u = self.store.users[key]
        return {"emailAddress": {"name": u["name"], "address": u["email"]}}

    def _event_json(self, m: dict, viewer: str) -> dict:
        start = datetime.fromtimestamp(m["startMs"] / 1000, tz=timezone.utc)
        end = datetime.fromtimestamp(m["endMs"] / 1000, tz=timezone.utc)
        return {
            "@odata.etag": f'W/"{base64.b64encode(m["eventId"][:12].encode()).decode()}"',
            "id": m["eventId"], "createdDateTime": iso(m["startMs"] - 7 * 86400_000),
            "lastModifiedDateTime": iso(m["startMs"] - 6 * 86400_000), "iCalUId": m["iCalUId"],
            "subject": m["title"], "bodyPreview": f"{m['title']}: Planning Department",
            "isCancelled": False, "isOrganizer": viewer == m["organizer"], "showAs": "busy",
            "type": "singleInstance", "isOnlineMeeting": True, "onlineMeetingProvider": "teamsForBusiness",
            "onlineMeetingUrl": None,
            "start": {"dateTime": start.strftime("%Y-%m-%dT%H:%M:%S.0000000"), "timeZone": "UTC"},
            "end": {"dateTime": end.strftime("%Y-%m-%dT%H:%M:%S.0000000"), "timeZone": "UTC"},
            "attendees": [{"type": "required", "status": {"response": "accepted", "time": iso(m["startMs"] - 6 * 86400_000)},
                           **self._addr(k)} for k in m["attendees"]],
            "organizer": self._addr(m["organizer"]),
            "onlineMeeting": {"joinUrl": m["joinUrl"], "conferenceId": str(int(hashlib.md5(m["key"].encode()).hexdigest(), 16))[:9],
                              "tollNumber": None},
        }

    def _meeting_json(self, m: dict) -> dict:
        org = self.store.users[m["organizer"]]
        return {
            "id": m["onlineMeetingId"], "creationDateTime": iso(m["startMs"] - 7 * 86400_000),
            "startDateTime": iso(m["startMs"]), "endDateTime": iso(m["endMs"]),
            "expiryDateTime": iso(m["endMs"] + 60 * 86400_000), "joinWebUrl": m["joinUrl"], "subject": m["title"],
            "isEntryExitAnnounced": True, "allowedPresenters": "everyone",
            "chatInfo": {"@odata.type": "#microsoft.graph.chatInfo", "threadId": m["threadId"], "messageId": "0"},
            "participants": {
                "organizer": {"upn": org["email"], "role": "presenter", "identity": {"user": {
                    "id": org["aadObjectId"], "displayName": None, "tenantId": TENANT_ID, "identityProvider": "AAD"}}},
                "attendees": [{"@odata.type": "#microsoft.graph.identitySet", "upn": self.store.users[k]["email"],
                               "identity": {"user": {"@odata.type": "#microsoft.graph.identity",
                                                     "id": self.store.users[k]["aadObjectId"],
                                                     "displayName": self.store.users[k]["name"]}}}
                              for k in m["attendees"]],
                "producers": [], "contributors": []},
            "meetingSpokenLanguageTag": "en-US",
            "lobbyBypassSettings": {"scope": "organization", "isDialInBypassEnabled": False},
            "joinMeetingIdSettings": {"isPasscodeRequired": False,
                                      "joinMeetingId": str(int(hashlib.md5(m["key"].encode()).hexdigest(), 16))[:10],
                                      "passcode": None},
        }

    def _transcript_json(self, m: dict, t: dict) -> dict:
        org = self.store.users[m["organizer"]]
        base = f"{self.root}/users/{org['aadObjectId']}/onlineMeetings/{m['onlineMeetingId']}/transcripts/{t['id']}"
        return {"id": t["id"], "meetingId": m["onlineMeetingId"], "callId": t["callId"],
                "createdDateTime": iso(t["createdMs"]), "endDateTime": iso(t["endMs"]),
                "contentCorrelationId": t["contentCorrelationId"], "transcriptContentUrl": f"{base}/content",
                "meetingOrganizer": {"application": None, "device": None, "user": {
                    "@odata.type": "#Microsoft.Teams.GraphSvc.teamworkUserIdentity", "id": org["aadObjectId"],
                    "displayName": None, "userIdentityType": "aadUser", "tenantId": TENANT_ID}}}

    # ---------------------------------------------------------- handlers
    def _calendar_view(self, req: Req, uid: str) -> Resp:
        user, err = self._guard(req, uid, "Calendars.Read")
        if err:
            return err
        s, e = req.q("startDateTime"), req.q("endDateTime")
        if not s or not e:
            return self._err(400, "ErrorInvalidParameter", "This request requires a time window specified by the "
                                                           "query string parameters StartDateTime and EndDateTime.")
        try:
            smin, emax = _ms(s.rstrip("Z")[:19]), _ms(e.rstrip("Z")[:19])
        except ValueError:
            return self._err(400, "ErrorInvalidParameter", "Invalid StartDateTime or EndDateTime.")
        items = [self._event_json(m, user) for m in sorted(self.data.meetings.values(), key=lambda m: m["startMs"])
                 if (user == m["organizer"] or user in m["attendees"]) and m["endMs"] >= smin and m["startMs"] <= emax]
        return Resp.json(200, {"@odata.context": f"{self.root}/$metadata#users('{unquote(uid)}')/calendarView",
                               "value": items})

    def _event(self, req: Req, uid: str, eid: str) -> Resp:
        user, err = self._guard(req, uid, "Calendars.Read")
        if err:
            return err
        m = next((m for m in self.data.meetings.values() if m["eventId"] == unquote(eid)), None)
        if not m or (user != m["organizer"] and user not in m["attendees"]):
            return self._err(404, "ErrorItemNotFound", "The specified object was not found in the store.")
        return Resp.json(200, self._event_json(m, user))

    def _find_meeting(self, req: Req, uid: str) -> Resp:
        user, err = self._guard(req, uid, "OnlineMeetings.Read.All", policy=True)
        if err:
            return err
        f = req.q("$filter") or ""
        mm = re.match(r"\s*JoinWebUrl\s+eq\s+'(.+)'\s*$", f, re.IGNORECASE)
        if not mm:
            return self._err(400, "BadRequest", "Filter on JoinWebUrl or joinMeetingIdSettings/joinMeetingId is required.")
        want = unquote(mm.group(1))
        items = [self._meeting_json(m) for m in self.data.meetings.values()
                 if unquote(m["joinUrl"]) == want and (user == m["organizer"] or user in m["attendees"])]
        return Resp.json(200, {"@odata.context": f"{self.root}/$metadata#users('{unquote(uid)}')/onlineMeetings",
                               "value": items})

    def _meeting(self, req: Req, uid: str, mid: str) -> Resp:
        user, err = self._guard(req, uid, "OnlineMeetings.Read.All", policy=True)
        if err:
            return err
        m = self._meeting_for(user, mid)
        return Resp.json(200, self._meeting_json(m)) if m else self._err(404, "NotFound", "Meeting not found.")

    def _transcripts(self, req: Req, uid: str, mid: str) -> Resp:
        user, err = self._guard(req, uid, "OnlineMeetingTranscript.Read.All", policy=True, transcripts=True)
        if err:
            return err
        m = self._meeting_for(user, mid)
        if not m:
            return self._err(404, "NotFound", "Meeting not found.")
        value = [self._transcript_json(m, t) for t in m["transcripts"]]
        return Resp.json(200, {"@odata.context": f"{self.root}/$metadata#users('{unquote(uid)}')/onlineMeetings('{m['onlineMeetingId']}')/transcripts",
                               "@odata.count": len(value), "value": value})

    def _find_transcript(self, user, mid, tid):
        m = self._meeting_for(user, mid)
        t = next((t for t in (m or {}).get("transcripts", []) if t["id"] == unquote(tid)), None)
        return m, t

    def _transcript(self, req: Req, uid: str, mid: str, tid: str) -> Resp:
        user, err = self._guard(req, uid, "OnlineMeetingTranscript.Read.All", policy=True, transcripts=True)
        if err:
            return err
        m, t = self._find_transcript(user, mid, tid)
        return Resp.json(200, self._transcript_json(m, t)) if t else self._err(404, "NotFound", "Transcript not found.")

    def _content(self, req: Req, uid: str, mid: str, tid: str) -> Resp:
        user, err = self._guard(req, uid, "OnlineMeetingTranscript.Read.All", policy=True, transcripts=True)
        if err:
            return err
        m, t = self._find_transcript(user, mid, tid)
        if not t:
            return self._err(404, "NotFound", "Transcript not found.")
        return Resp(200, t["vtt"].encode("utf-8"), {"Content-Type": "text/vtt"})
