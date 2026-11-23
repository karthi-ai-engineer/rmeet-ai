"""
Microsoft Graph change notifications (webhooks) for the fake tenant.

  POST   /subscriptions                    create (validation handshake to notificationUrl)
  GET    /subscriptions | /subscriptions/{id}
  PATCH  /subscriptions/{id}               renew (expirationDateTime)
  DELETE /subscriptions/{id}
  POST   /subscriptions/{id}/reauthorize

Supported resources (what Max needs):
  /teams/{team-id}/channels/{channel-id}/messages            created,updated,deleted   RSC ChannelMessage.Read.Group
  /drives/{drive-id}/root                                    updated                   RSC File.Read.Group
  communications/onlineMeetings/{meeting-id}/transcripts     created                   OnlineMeetingTranscript.Read.All
  users/{user-id}/onlineMeetings/getAllTranscripts           created                   OnlineMeetingTranscript.Read.All

Notifications are sent without resource data (the subscriber GETs the resource).
Rules follow docs/research/teams/02-graph-knowledge-apis.md §7: 45-minute minimum,
max lifetimes, lifecycleNotificationUrl required beyond 1 hour for Teams resources,
clientState echo, 409 on duplicates, reauthorizationRequired / subscriptionRemoved.
"""

import json
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

from httpx_types import Req, Resp, Router
from identity import GRAPH_AUDIENCE, Identity
from store import CHANNEL_ID, DRIVE_ID, FOLDER_ID, STATE_DIR, TEAM_GROUP_ID, TENANT_ID, TeamsStore

SUBS_FILE = STATE_DIR / "subscriptions.json"
TEAMS_MAX_MIN = 4320          # 3 days
DRIVE_MAX_MIN = 42300         # ~29 days
MIN_MIN = 45


def iso_utc(ms: float) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "0000Z"


def parse_iso(s: str) -> float:
    s = s.strip().replace("Z", "+00:00")
    m = re.match(r"^(.*\.\d{6})\d*(.*)$", s)       # Python accepts max 6 fractional digits
    if m:
        s = m.group(1) + m.group(2)
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp() * 1000


class Subscriptions:
    def __init__(self, base_url: str, identity: Identity, store: TeamsStore, meetings, err, notify_ui):
        self.root = base_url.rstrip("/") + "/graph/v1.0"
        self.identity, self.store, self.meetings, self._err, self.notify_ui = identity, store, meetings, err, notify_ui
        self.lock = threading.RLock()
        self.subs: dict[str, dict] = json.loads(SUBS_FILE.read_text("utf-8")) if SUBS_FILE.exists() else {}
        self.log: list[dict] = []
        store.on_change(self._on_store_event)
        meetings.on_change(self._on_meeting_event)
        threading.Thread(target=self._lifecycle_loop, daemon=True).start()

    # ============================================================ plumbing
    def _save(self) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        SUBS_FILE.write_text(json.dumps(self.subs, indent=1), "utf-8")

    def routes(self, r: Router) -> None:
        r.add("POST", r"/graph/v1\.0/subscriptions", self._create)
        r.add("GET", r"/graph/v1\.0/subscriptions", self._list)
        r.add("GET", r"/graph/v1\.0/subscriptions/([^/?]+)", self._get)
        r.add("PATCH", r"/graph/v1\.0/subscriptions/([^/?]+)", self._update)
        r.add("DELETE", r"/graph/v1\.0/subscriptions/([^/?]+)", self._delete)
        r.add("POST", r"/graph/v1\.0/subscriptions/([^/?]+)/reauthorize", self._reauthorize)

    def public(self) -> list:
        now = time.time() * 1000
        return [{"id": s["id"], "resource": s["resource"], "changeType": s["changeType"],
                 "expires": iso_utc(s["expirationMs"]), "minutesLeft": int((s["expirationMs"] - now) / 60000)}
                for s in self.subs.values()]

    def _json(self, s: dict) -> dict:
        return {"@odata.context": f"{self.root}/$metadata#subscriptions/$entity", "id": s["id"],
                "resource": s["resource"], "applicationId": s["appId"], "changeType": s["changeType"],
                "clientState": s.get("clientState"), "notificationUrl": s["notificationUrl"],
                "lifecycleNotificationUrl": s.get("lifecycleNotificationUrl"),
                "expirationDateTime": iso_utc(s["expirationMs"]), "creatorId": s["appId"],
                "includeResourceData": False, "latestSupportedTlsVersion": "v1_2",
                "notificationContentType": "application/json"}

    def _claims(self, req: Req):
        return self.identity.verify_app_token(req.bearer(), GRAPH_AUDIENCE)

    # ====================================================== resource rules
    def _classify(self, resource: str, roles: list) -> tuple[dict | None, Resp | None]:
        res = unquote(resource).strip()
        res_n = res.lstrip("/")
        m = re.fullmatch(r"teams/([^/]+)/channels/([^/]+)/messages", res_n)
        if m:
            if m.group(1) != TEAM_GROUP_ID or m.group(2) != CHANNEL_ID:
                return None, self._err(404, "NotFound", "The team or channel was not found.")
            if not (self.store.has_rsc("ChannelMessage.Read.Group") or "ChannelMessage.Read.All" in roles):
                return None, self._err(403, "Forbidden", "Missing permission ChannelMessage.Read.Group (RSC) or ChannelMessage.Read.All.")
            return {"kind": "messages", "max": TEAMS_MAX_MIN, "types": ["created", "deleted", "updated"], "teams": True}, None
        m = re.fullmatch(r"drives/([^/]+)/root", res_n)
        if m:
            if m.group(1) != DRIVE_ID:
                return None, self._err(404, "itemNotFound", "The drive was not found.")
            if not (self.store.has_rsc("File.Read.Group") or "Files.Read.All" in roles):
                return None, self._err(403, "Forbidden", "Missing permission File.Read.Group (RSC) or Files.Read.All.")
            return {"kind": "drive", "max": DRIVE_MAX_MIN, "types": ["updated"], "teams": False}, None
        m = re.fullmatch(r"communications/onlineMeetings/([^/]+)/transcripts", res_n)
        u = re.fullmatch(r"users/([^/]+)/onlineMeetings/getAllTranscripts(?:\(.*\))?", res_n)
        if m or u:
            if "OnlineMeetingTranscript.Read.All" not in roles:
                return None, self._err(403, "Forbidden", "Missing role permissions on the request. API requires one of 'OnlineMeetingTranscript.Read.All'.")
            if not self.store.admin.get("accessPolicy"):
                return None, self._err(403, "Forbidden", "No application access policy found for this app")
            if m and not self.meetings.by_online_id(unquote(m.group(1))):
                return None, self._err(404, "NotFound", "Online meeting not found.")
            key = {"meetingId": unquote(m.group(1))} if m else {"organizer": unquote(u.group(1)).lower()}
            return {"kind": "transcripts", "max": TEAMS_MAX_MIN, "types": ["created"], "teams": True, **key}, None
        return None, self._err(400, "InvalidRequest", f"Resource '{res}' is not supported for change notifications.")

    def _validate_url(self, url: str) -> bool:
        """Graph's validation handshake: POST ?validationToken=... must echo the token within 10 s."""
        token = f"Validation: Testing client application reachability for subscription Request-Id: {uuid.uuid4()}"
        sep = "&" if "?" in url else "?"
        req = urllib.request.Request(f"{url}{sep}validationToken={urllib.parse.quote(token)}", data=b"", method="POST",
                                     headers={"Content-Type": "text/plain; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode("utf-8", "replace")
                return resp.status == 200 and body == token
        except Exception:
            return False

    def _expiry(self, value: str | None, max_min: int) -> tuple[float | None, Resp | None]:
        if not value:
            return None, self._err(400, "ValidationError", "expirationDateTime is required.")
        try:
            exp = parse_iso(value)
        except ValueError:
            return None, self._err(400, "ValidationError", "expirationDateTime is not a valid date.")
        now = time.time() * 1000
        if exp > now + max_min * 60000 + 60000:
            return None, self._err(400, "ExtensionError",
                                   f"Subscription expiration can only be {max_min} minutes in the future.")
        return max(exp, now + MIN_MIN * 60000), None

    # ============================================================ handlers
    def _create(self, req: Req) -> Resp:
        claims = self._claims(req)
        if not claims:
            return self._err(401, "InvalidAuthenticationToken", "Access token validation failure.")
        b = req.json()
        for k in ("changeType", "notificationUrl", "resource", "expirationDateTime"):
            if not b.get(k):
                return self._err(400, "ValidationError", f"The '{k}' property is required.")
        if len(b.get("clientState") or "") > 128:
            return self._err(400, "ValidationError", "clientState must be 128 characters or fewer.")
        if b.get("includeResourceData"):
            return self._err(400, "ValidationError", "includeResourceData with encrypted content is not supported by "
                                                     "this simulator; subscribe without resource data and GET the resource.")
        info, err = self._classify(b["resource"], claims.get("roles", []))
        if err:
            return err
        types = {t.strip() for t in b["changeType"].split(",") if t.strip()}
        if not types or not types <= set(info["types"]):
            return self._err(400, "ValidationError", f"changeType '{b['changeType']}' is not supported for this resource "
                                                     f"(allowed: {','.join(sorted(info['types']))}).")
        exp, err = self._expiry(b["expirationDateTime"], info["max"])
        if err:
            return err
        if info["teams"] and exp > time.time() * 1000 + 3600_000 and not b.get("lifecycleNotificationUrl"):
            return self._err(400, "ValidationError", "lifecycleNotificationUrl is a required property for subscription "
                                                     "creation on this resource when the expirationDateTime value is set "
                                                     "to greater than 1 hour")
        with self.lock:
            dup = next((s for s in self.subs.values() if s["appId"] == claims["appid"]
                        and s["resource"].lstrip("/") == unquote(b["resource"]).lstrip("/")), None)
        if dup:
            return self._err(409, "Conflict", f"Subscription Id {dup['id']} already exists for the requested combination")
        if not self._validate_url(b["notificationUrl"]):
            return self._err(400, "ValidationError", "Subscription validation request failed. Notification endpoint "
                                                     "must respond with 200 OK to validation request.")
        lc = b.get("lifecycleNotificationUrl")
        if lc and lc != b["notificationUrl"] and not self._validate_url(lc):
            return self._err(400, "ValidationError", "Subscription validation request failed for lifecycleNotificationUrl.")
        sub = {"id": str(uuid.uuid4()), "resource": unquote(b["resource"]), "changeType": ",".join(sorted(types)),
               "notificationUrl": b["notificationUrl"], "lifecycleNotificationUrl": lc,
               "clientState": b.get("clientState"), "expirationMs": exp, "appId": claims["appid"],
               "info": info, "warned": False}
        with self.lock:
            # Check again under the lock: two concurrent creates must not both succeed.
            dup = next((s for s in self.subs.values() if s["appId"] == claims["appid"]
                        and s["resource"].lstrip("/") == sub["resource"].lstrip("/")), None)
            if dup:
                return self._err(409, "Conflict", f"Subscription Id {dup['id']} already exists for the requested combination")
            self.subs[sub["id"]] = sub
            self._save()
        self.notify_ui({"type": "subscriptions", "subscriptions": self.public()})
        return Resp.json(201, self._json(sub))

    def _list(self, req: Req) -> Resp:
        claims = self._claims(req)
        if not claims:
            return self._err(401, "InvalidAuthenticationToken", "Access token validation failure.")
        mine = [self._json(s) for s in self.subs.values() if s["appId"] == claims["appid"]]
        return Resp.json(200, {"@odata.context": f"{self.root}/$metadata#subscriptions", "value": mine})

    def _own(self, req: Req, sid: str):
        claims = self._claims(req)
        if not claims:
            return None, self._err(401, "InvalidAuthenticationToken", "Access token validation failure.")
        s = self.subs.get(unquote(sid))
        if not s or s["appId"] != claims["appid"]:
            return None, self._err(404, "ResourceNotFound", "The object was not found.")
        return s, None

    def _get(self, req: Req, sid: str) -> Resp:
        s, err = self._own(req, sid)
        return err or Resp.json(200, self._json(s))

    def _update(self, req: Req, sid: str) -> Resp:
        s, err = self._own(req, sid)
        if err:
            return err
        exp, err = self._expiry(req.json().get("expirationDateTime"), s["info"]["max"])
        if err:
            return err
        with self.lock:
            s["expirationMs"], s["warned"] = exp, False
            self._save()
        self.notify_ui({"type": "subscriptions", "subscriptions": self.public()})
        return Resp.json(200, self._json(s))

    def _delete(self, req: Req, sid: str) -> Resp:
        s, err = self._own(req, sid)
        if err:
            return err
        with self.lock:
            self.subs.pop(s["id"], None)
            self._save()
        self.notify_ui({"type": "subscriptions", "subscriptions": self.public()})
        return Resp(204, b"", {})

    def _reauthorize(self, req: Req, sid: str) -> Resp:
        s, err = self._own(req, sid)
        if err:
            return err
        s["warned"] = False
        return Resp(204, b"", {})

    # ============================================================ delivery
    def _post(self, url: str, payload: dict, label: str) -> None:
        body = json.dumps(payload).encode("utf-8")
        status = "failed"
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, data=body, method="POST",
                                             headers={"Content-Type": "application/json; charset=utf-8"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    status = str(r.status)
                    if 200 <= r.status < 300:
                        break
            except urllib.error.HTTPError as e:
                status = str(e.code)
            except Exception:
                status = "unreachable"
            time.sleep(2 * (attempt + 1))
        entry = {"time": time.strftime("%H:%M:%S"), "what": label, "status": status}
        with self.lock:
            self.log = (self.log + [entry])[-100:]
        self.notify_ui({"type": "notification_log", "entry": entry})

    def _send(self, sub: dict, items: list[dict], label: str) -> None:
        if time.time() * 1000 > sub["expirationMs"]:
            return
        for it in items:
            it.update({"subscriptionId": sub["id"], "tenantId": TENANT_ID, "clientState": sub.get("clientState"),
                       "subscriptionExpirationDateTime": iso_utc(sub["expirationMs"])})
        threading.Thread(target=self._post, args=(sub["notificationUrl"], {"value": items}, label), daemon=True).start()

    def _on_store_event(self, ev: dict) -> None:
        t = ev.get("type")
        if t in ("message", "message_updated", "message_deleted"):
            mid = ev["message"]["id"] if "message" in ev else ev["id"]
            root = (ev.get("message") or {}).get("rootId")
            if t == "message_deleted":
                msg = self.store.find(mid)
                root = msg["replyToId"] if msg else None
            change = {"message": "created", "message_updated": "updated", "message_deleted": "deleted"}[t]
            path = f"teams('{TEAM_GROUP_ID}')/channels('{CHANNEL_ID}')/messages('{root or mid}')"
            if root:
                path += f"/replies('{mid}')"
            for s in list(self.subs.values()):
                if s["info"]["kind"] == "messages" and change in s["changeType"]:
                    self._send(s, [{"changeType": change, "resource": path, "resourceData": {
                        "id": mid, "@odata.type": "#Microsoft.Graph.chatMessage", "@odata.id": path}}],
                        f"chatMessage {change}")
        elif t == "file":
            for s in list(self.subs.values()):
                if s["info"]["kind"] == "drive":
                    self._send(s, [{"changeType": "updated", "resource": f"drives('{DRIVE_ID}')/root", "resourceData": {
                        "id": FOLDER_ID, "@odata.type": "#Microsoft.Graph.DriveItem",
                        "@odata.id": f"drives('{DRIVE_ID}')/root"}}], f"driveItem updated ({ev.get('name')})")
        elif t == "install" and not ev["install"].get("installed"):
            self.remove_all("App was removed from the team (RSC consent revoked).", kinds={"messages", "drive"})
        elif t == "admin":
            if "OnlineMeetingTranscript.Read.All" not in ev["admin"].get("consented", []) or \
                    not ev["admin"].get("accessPolicy"):
                self.remove_all("Admin consent or access policy was revoked.", kinds={"transcripts"})

    def _on_meeting_event(self, ev: dict) -> None:
        if ev.get("type") != "transcript":
            return
        m, tr = ev["meeting"], ev["transcript"]
        org = self.store.users[m["organizer"]]
        path = f"users/{org['aadObjectId']}/onlineMeetings('{m['onlineMeetingId']}')/transcripts('{tr['id']}')"
        for s in list(self.subs.values()):
            info = s["info"]
            if info["kind"] != "transcripts":
                continue
            if info.get("meetingId") == m["onlineMeetingId"] or info.get("organizer") in (
                    org["aadObjectId"], org["email"].lower()):
                self._send(s, [{"changeType": "created", "resource": path, "resourceData": {
                    "id": tr["id"], "@odata.type": "#Microsoft.Graph.callTranscript", "@odata.id": path}}],
                    f"callTranscript created ({m['title']})")

    # =========================================================== lifecycle
    def _lifecycle(self, sub: dict, event: str) -> None:
        url = sub.get("lifecycleNotificationUrl")
        if not url:
            return
        item = {"subscriptionId": sub["id"], "subscriptionExpirationDateTime": iso_utc(sub["expirationMs"]),
                "tenantId": TENANT_ID, "clientState": sub.get("clientState"), "lifecycleEvent": event}
        threading.Thread(target=self._post, args=(url, {"value": [item]}, f"lifecycle {event}"), daemon=True).start()

    def remove_all(self, reason: str, kinds: set | None = None) -> int:
        with self.lock:
            gone = [s for s in self.subs.values() if not kinds or s["info"]["kind"] in kinds]
            for s in gone:
                self.subs.pop(s["id"], None)
            self._save()
        for s in gone:
            self._lifecycle(s, "subscriptionRemoved")
        if gone:
            self.notify_ui({"type": "subscriptions", "subscriptions": self.public(), "reason": reason})
        return len(gone)

    def _lifecycle_loop(self) -> None:
        while True:
            time.sleep(20)
            now = time.time() * 1000
            with self.lock:
                for s in list(self.subs.values()):
                    if now > s["expirationMs"]:
                        self.subs.pop(s["id"], None)          # expired: Graph silently stops delivering
                        self._save()
                    elif not s.get("warned") and s["expirationMs"] - now < 10 * 60000:
                        s["warned"] = True
                        self._lifecycle(s, "reauthorizationRequired")
