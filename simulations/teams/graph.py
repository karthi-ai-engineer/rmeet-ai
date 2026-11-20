"""
Fake Microsoft Graph (v1.0 subset Max needs in Phase 1), base <sim>/graph/v1.0 :

  GET /teams/{team-id}
  GET /teams/{team-id}/channels | /channels/{channel-id}
  GET /teams/{team-id}/members
  GET /teams/{team-id}/channels/{channel-id}/messages            ($top<=50, $expand=replies, paging)
  GET /teams/{team-id}/channels/{channel-id}/messages/{id}
  GET /teams/{team-id}/channels/{channel-id}/messages/{id}/replies ($top<=50, paging)
  GET /teams/{team-id}/channels/{channel-id}/messages/{id}/replies/{reply-id}
  GET /teams/{team-id}/channels/{channel-id}/filesFolder
  GET /drives/{drive-id}/items/{item-id} | /children | /content (302 to a pre-authenticated download URL)

App-only tokens from the fake token endpoint (aud https://graph.microsoft.com).
Permissions are checked like resource-specific consent (RSC) granted at install.
Contract source: docs/research/teams/02-graph-knowledge-apis.md §2-4, §8-10.
"""

import base64
import hashlib
import hmac
import json
import time
import uuid
from pathlib import Path
from urllib.parse import quote, unquote

from httpx_types import Req, Resp, Router
from identity import GRAPH_AUDIENCE, Identity
from store import (CHANNEL_ID, DRIVE_ID, FOLDER_ID, SITE_URL, TEAM_GROUP_ID, TEAM_THREAD_ID, TENANT_ID, TeamsStore,
                   iso)

PAGE_MAX = 50
PAGE_DEFAULT = 20


class Graph:
    def __init__(self, base_url: str, identity: Identity, store: TeamsStore):
        self.root = base_url.rstrip("/") + "/graph/v1.0"
        self.identity = identity
        self.store = store
        self._dl_secret = hashlib.sha256(identity.kid.encode() + b"download").digest()

    # =========================================================== plumbing
    def routes(self, r: Router) -> None:
        t, c = r"/graph/v1\.0/teams/([^/?]+)", r"/channels/([^/?]+)"
        r.add("GET", t, self._team)
        r.add("GET", t + r"/channels", self._channels)
        r.add("GET", t + c, self._channel)
        r.add("GET", t + r"/members", self._members)
        r.add("GET", t + c + r"/messages", self._messages)
        r.add("GET", t + c + r"/messages/([^/?]+)", self._message)
        r.add("GET", t + c + r"/messages/([^/?]+)/replies", self._replies)
        r.add("GET", t + c + r"/messages/([^/?]+)/replies/([^/?]+)", self._reply)
        r.add("GET", t + c + r"/filesFolder", self._files_folder)
        r.add("GET", r"/graph/v1\.0/drives/([^/?]+)/root/delta", self._delta)
        d = r"/graph/v1\.0/drives/([^/?]+)/items/([^/?]+)"
        r.add("GET", d, self._item)
        r.add("GET", d + r"/children", self._children)
        r.add("GET", d + r"/content", self._content)
        r.add("GET", r"/graph/_download/([^/?]+)", self._download)

    @staticmethod
    def _err(status: int, code: str, message: str) -> Resp:
        return Resp.json(status, {"error": {"code": code, "message": message, "innerError": {
            "date": time.strftime("%Y-%m-%dT%H:%M:%S"), "request-id": str(uuid.uuid4()),
            "client-request-id": str(uuid.uuid4())}}}, {"request-id": str(uuid.uuid4())})

    def _guard(self, req: Req, team_id: str | None, perm: str) -> Resp | None:
        if not self.identity.verify_app_token(req.bearer(), GRAPH_AUDIENCE):
            return self._err(401, "InvalidAuthenticationToken", "Access token validation failure. Invalid audience.")
        if team_id is not None and unquote(team_id) != TEAM_GROUP_ID:
            return self._err(404, "NotFound", "No team found with Group Id " + unquote(team_id))
        if not self.store.has_rsc(perm):
            return self._err(403, "Forbidden", f"Missing role permissions on the request. API requires one of "
                                               f"'{perm}'. Roles on the request ''.")
        return None

    @staticmethod
    def _chan_ok(channel_id: str) -> bool:
        return unquote(channel_id) == CHANNEL_ID

    def _page(self, req: Req, items: list, self_path: str) -> dict:
        try:
            top = max(1, min(PAGE_MAX, int(req.q("$top", PAGE_DEFAULT))))
        except ValueError:
            top = PAGE_DEFAULT
        try:
            skip = int(base64.urlsafe_b64decode((req.q("$skiptoken") or "MA==").encode()).decode())
        except Exception:
            skip = 0
        page = items[skip:skip + top]
        out = {"@odata.context": f"{self.root}/$metadata#{self_path}", "@odata.count": len(page), "value": page}
        if skip + top < len(items):
            token = base64.urlsafe_b64encode(str(skip + top).encode()).decode()
            out["@odata.nextLink"] = f"{self.root}/{self_path}?$top={top}&$skiptoken={quote(token)}"
        return out

    # ========================================================== resources
    def _identity_user(self, key: str) -> dict:
        u = self.store.users[key]
        return {"@odata.type": "#microsoft.graph.teamworkUserIdentity", "id": u["aadObjectId"],
                "displayName": u["name"], "userIdentityType": "aadUser", "tenantId": TENANT_ID}

    def _identity_app(self, app_id: str, name: str) -> dict:
        return {"@odata.type": "#microsoft.graph.teamworkApplicationIdentity", "id": app_id, "displayName": name,
                "applicationIdentityType": "bot"}

    def _chat_message(self, msg: dict) -> dict:
        a = msg["author"]
        frm = {"application": None, "device": None, "user": None}
        if "user" in a:
            frm["user"] = self._identity_user(a["user"])
        else:
            frm["application"] = self._identity_app(a["app"], a.get("name", "Max"))
        mentions = []
        for m in msg["mentions"]:
            mentioned = {"application": None, "device": None, "conversation": None, "user": None}
            if "app" in m:
                mentioned["application"] = self._identity_app(m["app"], m["mentionText"])
            else:
                mentioned["user"] = self._identity_user(m["user"])
            mentions.append({"id": m["id"], "mentionText": m["mentionText"], "mentioned": mentioned})
        body = self.store.render_text(msg, "html")
        attachments = [{k: v for k, v in at.items() if not k.startswith("_")} for at in msg["attachments"]]
        for at in attachments:
            body += f'<attachment id="{at["id"]}"></attachment>'
        for card in msg.get("cards") or []:
            cid = str(uuid.uuid5(uuid.NAMESPACE_URL, msg["id"] + str(len(attachments))))
            attachments.append({"id": cid, "contentType": "application/vnd.microsoft.card.adaptive",
                                "contentUrl": None, "content": json.dumps(card), "name": None,
                                "thumbnailUrl": None, "teamsAppId": None})
            body += f'<attachment id="{cid}"></attachment>'
        root_id = msg["replyToId"] or msg["id"]
        return {
            "id": msg["id"], "replyToId": msg["replyToId"], "etag": str(msg["lastModifiedMs"]),
            "messageType": "message", "createdDateTime": iso(msg["createdMs"]),
            "lastModifiedDateTime": iso(msg["lastModifiedMs"]),
            "lastEditedDateTime": iso(msg["lastModifiedMs"]) if msg.get("edited") else None,
            "deletedDateTime": iso(msg["lastModifiedMs"]) if msg.get("deleted") else None,
            "subject": None, "summary": None, "chatId": None, "importance": "normal", "locale": "en-us",
            "webUrl": (f"https://teams.microsoft.com/l/message/{quote(CHANNEL_ID, safe='')}/{msg['id']}"
                       f"?groupId={TEAM_GROUP_ID}&tenantId={TENANT_ID}&createdTime={msg['id']}"
                       f"&parentMessageId={root_id}"),
            "policyViolation": None, "eventDetail": None, "from": frm,
            "body": {"contentType": "html", "content": "" if msg.get("deleted") else f"<p>{body}</p>"},
            "channelIdentity": {"teamId": TEAM_GROUP_ID, "channelId": CHANNEL_ID},
            "attachments": [] if msg.get("deleted") else attachments,
            "mentions": mentions,
            "reactions": [{"reactionType": r["reactionType"], "displayName": None, "reactionContentUrl": None,
                           "createdDateTime": iso(r["createdMs"]),
                           "user": {"application": None, "device": None, "user": {
                               **self._identity_user(r["user"]), "displayName": None}}} for r in msg["reactions"]],
            "messageHistory": [],
        }

    def _drive_item(self, rec: dict) -> dict:
        author = self.store.users.get(rec["author"], {})
        user = {"email": author.get("email"), "id": author.get("aadObjectId"), "displayName": author.get("name")}
        when = iso(rec["createdMs"]).replace(".000Z", "Z")
        modified = iso(rec.get("modifiedMs", rec["createdMs"])).replace(".000Z", "Z")
        ver = rec.get("version", 1)
        return {
            "@microsoft.graph.downloadUrl": self._download_url(rec["id"]),
            "createdDateTime": when, "lastModifiedDateTime": modified,
            "eTag": f'"{{{rec["etagGuid"]}}},{ver}"', "cTag": f'"c:{{{rec["etagGuid"]}}},{ver}"',
            "id": rec["id"], "name": rec["name"], "webUrl": rec["webUrl"], "size": rec["size"],
            "createdBy": {"user": user}, "lastModifiedBy": {"user": user},
            "parentReference": {"driveType": "documentLibrary", "driveId": DRIVE_ID, "id": FOLDER_ID,
                                "name": "General", "path": f"/drives/{DRIVE_ID}/root:/General"},
            "file": {"mimeType": rec["mime"],
                     "hashes": {"quickXorHash": base64.b64encode(hashlib.sha1(rec["id"].encode()).digest()[:20]).decode()}},
            "fileSystemInfo": {"createdDateTime": when, "lastModifiedDateTime": modified},
            "shared": {"scope": "users"},
        }

    def _download_url(self, iid: str) -> str:
        exp = int(time.time()) + 3600
        sig = hmac.new(self._dl_secret, f"{iid}.{exp}".encode(), hashlib.sha256).hexdigest()[:32]
        return f"{self.root.rsplit('/v1.0', 1)[0]}/_download/{iid}?tempauth={exp}.{sig}&ApiVersion=2.0"

    # ============================================================ handlers
    def _team(self, req: Req, team_id: str) -> Resp:
        if (g := self._guard(req, team_id, "TeamSettings.Read.Group")):
            return g
        return Resp.json(200, {"@odata.context": f"{self.root}/$metadata#teams/$entity", "id": TEAM_GROUP_ID,
                               "createdDateTime": "2026-01-12T08:00:00Z", "displayName": self.store.team_name,
                               "description": "Plans and protects the operating budget.",
                               "internalId": TEAM_THREAD_ID, "classification": None, "specialization": "none",
                               "visibility": "private", "isArchived": False, "tenantId": TENANT_ID,
                               "webUrl": f"https://teams.microsoft.com/l/team/{quote(TEAM_THREAD_ID, safe='')}/conversations?groupId={TEAM_GROUP_ID}&tenantId={TENANT_ID}"})

    def _channel_resource(self) -> dict:
        return {"id": CHANNEL_ID, "createdDateTime": "2026-01-12T08:00:00Z", "displayName": "General",
                "description": f"{self.store.team_name} general channel", "isFavoriteByDefault": None,
                "email": "", "tenantId": TENANT_ID, "membershipType": "standard",
                "webUrl": f"https://teams.microsoft.com/l/channel/{quote(CHANNEL_ID, safe='')}/General?groupId={TEAM_GROUP_ID}&tenantId={TENANT_ID}"}

    def _channels(self, req: Req, team_id: str) -> Resp:
        if (g := self._guard(req, team_id, "ChannelSettings.Read.Group")):
            return g
        return Resp.json(200, {"@odata.context": f"{self.root}/$metadata#teams('{TEAM_GROUP_ID}')/channels",
                               "@odata.count": 1, "value": [self._channel_resource()]})

    def _channel(self, req: Req, team_id: str, channel_id: str) -> Resp:
        if (g := self._guard(req, team_id, "ChannelSettings.Read.Group")):
            return g
        if not self._chan_ok(channel_id):
            return self._err(404, "NotFound", "Channel not found.")
        return Resp.json(200, self._channel_resource())

    def _members(self, req: Req, team_id: str) -> Resp:
        if (g := self._guard(req, team_id, "TeamMember.Read.Group")):
            return g
        value = [{"@odata.type": "#microsoft.graph.aadUserConversationMember",
                  "id": base64.b64encode(f"{TEAM_THREAD_ID}##{u['aadObjectId']}".encode()).decode(),
                  "roles": ["owner"] if u["userRole"] == "owner" else [], "displayName": u["name"],
                  "visibleHistoryStartDateTime": "0001-01-01T00:00:00Z", "userId": u["aadObjectId"],
                  "email": u["email"], "tenantId": TENANT_ID} for u in self.store.users.values()]
        return Resp.json(200, {"@odata.context": f"{self.root}/$metadata#teams('{TEAM_GROUP_ID}')/members",
                               "@odata.count": len(value), "value": value})

    def _messages(self, req: Req, team_id: str, channel_id: str) -> Resp:
        if (g := self._guard(req, team_id, "ChannelMessage.Read.Group")):
            return g
        if not self._chan_ok(channel_id):
            return self._err(404, "NotFound", "Channel not found.")
        expand = (req.q("$expand") or "").lower() == "replies"
        items = []
        for r in self.store.sorted_roots():
            item = self._chat_message(r["msg"])
            if expand:
                reps = sorted(r["replies"], key=lambda m: m["createdMs"], reverse=True)[:200]
                item["replies@odata.count"] = len(reps)
                item["replies"] = [self._chat_message(m) for m in reps]
            items.append(item)
        return Resp.json(200, self._page(req, items, f"teams/{TEAM_GROUP_ID}/channels/{quote(CHANNEL_ID)}/messages"))

    def _root(self, message_id: str):
        r = self.store.roots.get(unquote(message_id))
        return r

    def _message(self, req: Req, team_id: str, channel_id: str, message_id: str) -> Resp:
        if (g := self._guard(req, team_id, "ChannelMessage.Read.Group")):
            return g
        r = self._root(message_id)
        if not self._chan_ok(channel_id) or not r:
            return self._err(404, "NotFound", "Message not found.")
        return Resp.json(200, self._chat_message(r["msg"]))

    def _replies(self, req: Req, team_id: str, channel_id: str, message_id: str) -> Resp:
        if (g := self._guard(req, team_id, "ChannelMessage.Read.Group")):
            return g
        r = self._root(message_id)
        if not self._chan_ok(channel_id) or not r:
            return self._err(404, "NotFound", "Message not found.")
        items = [self._chat_message(m) for m in sorted(r["replies"], key=lambda m: m["createdMs"], reverse=True)]
        return Resp.json(200, self._page(req, items, f"teams/{TEAM_GROUP_ID}/channels/{quote(CHANNEL_ID)}/messages/{r['msg']['id']}/replies"))

    def _reply(self, req: Req, team_id: str, channel_id: str, message_id: str, reply_id: str) -> Resp:
        if (g := self._guard(req, team_id, "ChannelMessage.Read.Group")):
            return g
        r = self._root(message_id)
        rep = next((m for m in (r or {}).get("replies", []) if m["id"] == unquote(reply_id)), None)
        if not self._chan_ok(channel_id) or not rep:
            return self._err(404, "NotFound", "Message not found.")
        return Resp.json(200, self._chat_message(rep))

    def _files_folder(self, req: Req, team_id: str, channel_id: str) -> Resp:
        if (g := self._guard(req, team_id, "File.Read.Group")):
            return g
        if not self._chan_ok(channel_id):
            return self._err(404, "NotFound", "Channel not found.")
        return Resp.json(200, {
            "@odata.context": f"{self.root}/$metadata#teams('{TEAM_GROUP_ID}')/channels('{quote(CHANNEL_ID)}')/filesFolder/$entity",
            "id": FOLDER_ID, "createdDateTime": "0001-01-01T00:00:00Z", "lastModifiedDateTime": "2026-11-12T18:15:00Z",
            "name": "General", "webUrl": f"{SITE_URL}/Shared%20Documents/General",
            "size": sum(f["size"] for f in self.store.files.values()),
            "parentReference": {"driveId": DRIVE_ID, "driveType": "documentLibrary"},
            "fileSystemInfo": {"createdDateTime": "2026-01-12T08:00:00Z", "lastModifiedDateTime": "2026-11-12T18:15:00Z"},
            "folder": {"childCount": len(self.store.files)}})

    def _drive_guard(self, req: Req, drive_id: str) -> Resp | None:
        if (g := self._guard(req, None, "File.Read.Group")):
            return g
        if unquote(drive_id) != DRIVE_ID:
            return self._err(404, "itemNotFound", "The resource could not be found.")
        return None

    def _delta(self, req: Req, drive_id: str) -> Resp:
        """GET /drives/{id}/root/delta[?token=...]: items changed since the token (full list without one)."""
        if (g := self._drive_guard(req, drive_id)):
            return g
        token = req.q("token")
        if token == "latest":
            changed = []
        elif token:
            try:
                since = int(base64.urlsafe_b64decode(token.encode() + b"==").decode())
            except Exception:
                return Resp.json(410, {"error": {"code": "resyncRequired",
                                                 "message": "The delta token is invalid; resync with a full enumeration.",
                                                 "innerError": {"code": "resyncChangesApplyDifferences"}}})
            changed = self.store.files_changed_since(since)
        else:
            changed = [f for f in self.store.files.values() if not f.get("deleted")]
        value = []
        for f in changed:
            item = self._drive_item(f)
            item["parentReference"].pop("path", None)       # delta omits the path
            if f.get("deleted"):
                item = {"id": f["id"], "deleted": {}, "parentReference": item["parentReference"]}
            value.append(item)
        next_token = base64.urlsafe_b64encode(str(self.store.seq).encode()).decode().rstrip("=")
        return Resp.json(200, {"@odata.context": f"{self.root}/$metadata#Collection(driveItem)", "value": value,
                               "@odata.deltaLink": f"{self.root}/drives/{DRIVE_ID}/root/delta?token={next_token}"})

    def _item(self, req: Req, drive_id: str, iid: str) -> Resp:
        if (g := self._drive_guard(req, drive_id)):
            return g
        rec = self.store.files.get(unquote(iid))
        return Resp.json(200, self._drive_item(rec)) if rec else self._err(404, "itemNotFound", "The resource could not be found.")

    def _children(self, req: Req, drive_id: str, iid: str) -> Resp:
        if (g := self._drive_guard(req, drive_id)):
            return g
        if unquote(iid) != FOLDER_ID:
            return self._err(404, "itemNotFound", "The resource could not be found.")
        items = [self._drive_item(f) for f in sorted(self.store.files.values(), key=lambda f: f["name"])]
        return Resp.json(200, {"@odata.context": f"{self.root}/$metadata#drives('{DRIVE_ID}')/items('{FOLDER_ID}')/children",
                               "value": items})

    def _content(self, req: Req, drive_id: str, iid: str) -> Resp:
        if (g := self._drive_guard(req, drive_id)):
            return g
        rec = self.store.files.get(unquote(iid))
        if not rec:
            return self._err(404, "itemNotFound", "The resource could not be found.")
        return Resp(302, b"", {"Location": self._download_url(rec["id"])})

    def _download(self, req: Req, iid: str) -> Resp:
        """Pre-authenticated download URL (no bearer token, short-lived tempauth)."""
        rec = self.store.files.get(unquote(iid))
        try:
            exp, sig = (req.q("tempauth") or ".").split(".", 1)
            good = hmac.compare_digest(sig, hmac.new(self._dl_secret, f"{unquote(iid)}.{exp}".encode(),
                                                     hashlib.sha256).hexdigest()[:32]) and int(exp) > time.time()
        except ValueError:
            good = False
        if not rec or not good:
            return self._err(401, "accessDenied", "The download link is invalid or has expired.")
        return Resp(200, Path(rec["local"]).read_bytes(), {"Content-Type": rec["mime"],
                                                          "Content-Disposition": f'attachment; filename="{rec["name"]}"'})
