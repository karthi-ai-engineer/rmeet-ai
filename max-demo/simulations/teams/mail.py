"""
Fake Exchange Online through Microsoft Graph: the company directory and mailboxes (Phase 4).

  GET    /users?$filter=...                         directory lookup            role User.ReadBasic.All
  GET    /users/{id}                                one person                  role User.ReadBasic.All
  POST   /users/{id}/messages                       create a draft              role Mail.ReadWrite
  GET    /users/{id}/messages/{mid}                 read a message              role Mail.ReadWrite or Mail.Read
  DELETE /users/{id}/messages/{mid}                 delete a draft              role Mail.ReadWrite
  POST   /users/{id}/messages/{mid}/attachments     add a file (<= 3 MB)        role Mail.ReadWrite
  POST   /users/{id}/messages/{mid}/send            send a draft (only once)    role Mail.Send
  POST   /users/{id}/sendMail                       send directly               role Mail.Send
  GET    /users/{id}/mailFolders/{folder}/messages  drafts | sentitems | inbox  role Mail.Read or Mail.ReadWrite

Exchange "RBAC for Applications" is modelled by admin["mailboxScope"] (default: only Max's own mailbox): any other
mailbox answers 403 ErrorAccessDenied, like a scoped app in a real tenant. Delivery: recipients in the tenant get
the message in their inbox; outside addresses are recorded as "left the company" (shown in the UI).
State persists in simulations/teams/state/mail.json; the channel reset clears it.
"""

import base64
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

from httpx_types import Req, Resp, Router
from identity import GRAPH_AUDIENCE, Identity
from store import TeamsStore

FOLDERS = ("drafts", "sentitems", "inbox")
MAX_ATTACHMENT = 3 * 1024 * 1024


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class MailData:
    def __init__(self, store: TeamsStore, state_dir: Path):
        self.store, self.file = store, state_dir / "mail.json"
        self.lock = threading.RLock()
        self.listeners = []
        self.boxes: dict[str, dict[str, dict]] = {}
        self.outbound: list[dict] = []          # messages that went to addresses outside the company
        if self.file.exists():
            try:
                saved = json.loads(self.file.read_text(encoding="utf-8"))
                self.boxes, self.outbound = saved.get("boxes", {}), saved.get("outbound", [])
            except ValueError:
                pass

    def box(self, key: str) -> dict:
        return self.boxes.setdefault(key, {f: {} for f in FOLDERS})

    def save(self) -> None:
        with self.lock:
            self.file.parent.mkdir(parents=True, exist_ok=True)
            self.file.write_text(json.dumps({"boxes": self.boxes, "outbound": self.outbound}), encoding="utf-8")

    def reset(self) -> None:
        with self.lock:
            self.boxes, self.outbound = {}, []
            self.save()

    def emit(self, event: dict) -> None:
        for fn in self.listeners:
            try:
                fn(event)
            except Exception:  # noqa: BLE001
                pass

    def find(self, key: str, mid: str) -> tuple[str, dict] | tuple[None, None]:
        for folder, msgs in self.box(key).items():
            if mid in msgs:
                return folder, msgs[mid]
        return None, None

    def ui(self, key: str) -> dict:
        """One person's mailbox for the rmeet-ai UI (no attachment bytes)."""
        def slim(m):
            return {**{k: v for k, v in m.items() if k != "attachments"},
                    "attachments": [{"name": a["name"], "size": a["size"]} for a in m.get("attachments", [])]}
        b = self.box(key)
        return {f: sorted((slim(m) for m in b[f].values()), key=lambda m: m["createdDateTime"], reverse=True)
                for f in FOLDERS}


class GraphMail:
    def __init__(self, base_url: str, identity: Identity, store: TeamsStore, data: MailData, err):
        self.root = base_url.rstrip("/") + "/graph/v1.0"
        self.identity, self.store, self.data, self._err = identity, store, data, err

    def routes(self, r: Router) -> None:
        u = r"/graph/v1\.0/users/([^/?]+)"
        r.add("GET", r"/graph/v1\.0/users", self._list_users)
        r.add("GET", u, self._get_user)
        r.add("POST", u + r"/messages", self._create_draft)
        r.add("GET", u + r"/messages/([^/?]+)", self._get_message)
        r.add("DELETE", u + r"/messages/([^/?]+)", self._delete_message)
        r.add("POST", u + r"/messages/([^/?]+)/attachments", self._add_attachment)
        r.add("POST", u + r"/messages/([^/?]+)/send", self._send_draft)
        r.add("POST", u + r"/sendMail", self._send_mail)
        r.add("GET", u + r"/mailFolders/([^/?]+)/messages", self._folder)

    # ------------------------------------------------------------------ guards
    def _claims(self, req: Req):
        return self.identity.verify_app_token(req.bearer(), GRAPH_AUDIENCE)

    def _guard(self, req: Req, uid: str, roles: tuple[str, ...], mailbox: bool = True):
        claims = self._claims(req)
        if not claims:
            return None, self._err(401, "InvalidAuthenticationToken", "Access token validation failure.")
        have = claims.get("roles", [])
        if not any(r in have for r in roles):
            return None, self._err(403, "Forbidden", f"Missing role permissions on the request. API requires one of "
                                                     f"'{', '.join(roles)}'. Roles on the request '{','.join(have)}'.")
        key = self.store.tenant_user(unquote(uid))
        if not key:
            return None, self._err(404, "ErrorInvalidUser", f"The requested user '{unquote(uid)}' is invalid.")
        if mailbox and key not in self.store.admin.get("mailboxScope", ["max"]):
            # Exchange RBAC for Applications: the app is only allowed into the mailboxes in its scope.
            return None, self._err(403, "ErrorAccessDenied", "Access is denied. Check credentials and try again.")
        return key, None

    def _addr(self, key: str) -> dict:
        u = self.store.tenant_users()[key]
        return {"emailAddress": {"name": u["name"], "address": u["email"]}}

    @staticmethod
    def _recipients(lst) -> list[dict]:
        out = []
        for r in lst or []:
            e = (r or {}).get("emailAddress") or {}
            if e.get("address"):
                out.append({"emailAddress": {"name": e.get("name") or e["address"], "address": e["address"]}})
        return out

    def _user_json(self, key: str) -> dict:
        u = self.store.tenant_users()[key]
        return {"id": u["aadObjectId"], "displayName": u["name"], "givenName": u["givenName"], "surname": u["surname"],
                "mail": u["email"], "userPrincipalName": u["email"], "jobTitle": u.get("role") or None}

    # ------------------------------------------------------------------ directory
    def _list_users(self, req: Req) -> Resp:
        claims = self._claims(req)
        if not claims:
            return self._err(401, "InvalidAuthenticationToken", "Access token validation failure.")
        if not {"User.ReadBasic.All", "User.Read.All"} & set(claims.get("roles", [])):
            return self._err(403, "Forbidden", "Missing role permissions on the request. API requires one of "
                                               "'User.ReadBasic.All, User.Read.All'.")
        flt = (req.q("$filter") or "").lower()
        people = [self._user_json(k) for k in self.store.tenant_users()]
        if "eq '" in flt:
            want = flt.split("eq '", 1)[1].rstrip("')")
            people = [p for p in people if want in (p["mail"].lower(), p["displayName"].lower())]
        elif "startswith(" in flt:
            want = flt.split("'", 2)[1]
            people = [p for p in people if p["displayName"].lower().startswith(want) or p["mail"].lower().startswith(want)]
        return Resp.json(200, {"@odata.context": f"{self.root}/$metadata#users", "value": people})

    def _get_user(self, req: Req, uid: str) -> Resp:
        key, err = self._guard(req, uid, ("User.ReadBasic.All", "User.Read.All"), mailbox=False)
        return err or Resp.json(200, self._user_json(key))

    # ------------------------------------------------------------------ messages
    def _create_draft(self, req: Req, uid: str) -> Resp:
        key, err = self._guard(req, uid, ("Mail.ReadWrite",))
        if err:
            return err
        b = req.json()
        mid = "AAMkAD" + uuid.uuid4().hex
        msg = {"id": mid, "createdDateTime": _now(), "lastModifiedDateTime": _now(), "isDraft": True,
               "subject": b.get("subject") or "", "body": b.get("body") or {"contentType": "text", "content": ""},
               "from": self._addr(key), "sender": self._addr(key),
               "toRecipients": self._recipients(b.get("toRecipients")),
               "ccRecipients": self._recipients(b.get("ccRecipients")),
               "bccRecipients": self._recipients(b.get("bccRecipients")),
               "replyTo": self._recipients(b.get("replyTo")),
               "conversationId": "AAQkAD" + uuid.uuid4().hex, "internetMessageId": f"<{uuid.uuid4().hex}@thirdwave.co.jp>",
               "hasAttachments": False, "attachments": [], "parentFolderId": "drafts"}
        with self.data.lock:
            self.data.box(key)["drafts"][mid] = msg
            self.data.save()
        self.data.emit({"type": "mail", "change": "draft", "user": key})
        return Resp.json(201, {k: v for k, v in msg.items() if k != "attachments"})

    def _get_message(self, req: Req, uid: str, mid: str) -> Resp:
        key, err = self._guard(req, uid, ("Mail.ReadWrite", "Mail.Read"))
        if err:
            return err
        _, msg = self.data.find(key, unquote(mid))
        if not msg:
            return self._err(404, "ErrorItemNotFound", "The specified object was not found in the store.")
        return Resp.json(200, {k: v for k, v in msg.items() if k != "attachments"})

    def _delete_message(self, req: Req, uid: str, mid: str) -> Resp:
        key, err = self._guard(req, uid, ("Mail.ReadWrite",))
        if err:
            return err
        with self.data.lock:
            folder, msg = self.data.find(key, unquote(mid))
            if not msg:
                return self._err(404, "ErrorItemNotFound", "The specified object was not found in the store.")
            del self.data.box(key)[folder][msg["id"]]
            self.data.save()
        return Resp(204)

    def _add_attachment(self, req: Req, uid: str, mid: str) -> Resp:
        key, err = self._guard(req, uid, ("Mail.ReadWrite",))
        if err:
            return err
        b = req.json()
        try:
            raw = base64.b64decode(b.get("contentBytes") or "")
        except ValueError:
            return self._err(400, "ErrorInvalidRequest", "contentBytes is not valid base64.")
        if len(raw) > MAX_ATTACHMENT:
            return self._err(413, "ErrorRequestEntityTooLarge", "Use an upload session for attachments over 3 MB.")
        with self.data.lock:
            folder, msg = self.data.find(key, unquote(mid))
            if not msg or not msg.get("isDraft"):
                return self._err(404, "ErrorItemNotFound", "The specified draft was not found.")
            att = {"id": "AAMkAtt" + uuid.uuid4().hex[:16], "@odata.type": "#microsoft.graph.fileAttachment",
                   "name": b.get("name") or "file", "contentType": b.get("contentType") or "application/octet-stream",
                   "size": len(raw), "contentBytes": base64.b64encode(raw).decode()}
            msg["attachments"].append(att)
            msg["hasAttachments"] = True
            self.data.save()
        return Resp.json(201, {k: v for k, v in att.items() if k != "contentBytes"})

    def _deliver(self, sender: str, msg: dict) -> None:
        """Sent: a copy in the sender's Sent Items, one in each tenant recipient's inbox, the rest go out."""
        sent = {**msg, "isDraft": False, "parentFolderId": "sentitems", "sentDateTime": _now()}
        self.data.box(sender)["sentitems"][msg["id"]] = sent
        outside = []
        for r in sent["toRecipients"] + sent["ccRecipients"] + sent["bccRecipients"]:
            to = self.store.tenant_user(r["emailAddress"]["address"])
            if to:
                copy = {**sent, "id": "AAMkAD" + uuid.uuid4().hex, "parentFolderId": "inbox", "isRead": False,
                        "receivedDateTime": _now(), "bccRecipients": []}
                self.data.box(to)["inbox"][copy["id"]] = copy
            else:
                outside.append(r["emailAddress"]["address"])
        if outside:
            self.data.outbound.append({"from": sender, "to": outside, "subject": sent["subject"], "at": _now()})
        self.data.save()

    def _send_draft(self, req: Req, uid: str, mid: str) -> Resp:
        key, err = self._guard(req, uid, ("Mail.Send",))
        if err:
            return err
        with self.data.lock:
            folder, msg = self.data.find(key, unquote(mid))
            if not msg or folder != "drafts":           # a draft can be sent only once
                return self._err(404, "ErrorItemNotFound", "The specified draft was not found (already sent?).")
            if not (msg["toRecipients"] or msg["ccRecipients"] or msg["bccRecipients"]):
                return self._err(400, "ErrorInvalidRecipients", "At least one recipient is not valid.")
            del self.data.box(key)["drafts"][msg["id"]]
            self._deliver(key, msg)
        self.data.emit({"type": "mail", "change": "sent", "user": key, "subject": msg["subject"]})
        return Resp(202)

    def _send_mail(self, req: Req, uid: str) -> Resp:
        key, err = self._guard(req, uid, ("Mail.Send",))
        if err:
            return err
        m = (req.json().get("message") or {})
        msg = {"id": "AAMkAD" + uuid.uuid4().hex, "createdDateTime": _now(), "subject": m.get("subject") or "",
               "body": m.get("body") or {"contentType": "text", "content": ""}, "from": self._addr(key),
               "sender": self._addr(key), "toRecipients": self._recipients(m.get("toRecipients")),
               "ccRecipients": self._recipients(m.get("ccRecipients")), "bccRecipients": self._recipients(m.get("bccRecipients")),
               "replyTo": [], "conversationId": "AAQkAD" + uuid.uuid4().hex, "attachments": [], "hasAttachments": False}
        with self.data.lock:
            self._deliver(key, msg)
        self.data.emit({"type": "mail", "change": "sent", "user": key, "subject": msg["subject"]})
        return Resp(202)

    def _folder(self, req: Req, uid: str, folder: str) -> Resp:
        key, err = self._guard(req, uid, ("Mail.Read", "Mail.ReadWrite"))
        if err:
            return err
        folder = unquote(folder).lower()
        if folder not in FOLDERS:
            return self._err(404, "ErrorItemNotFound", "The specified folder could not be found in the store.")
        msgs = sorted(self.data.box(key)[folder].values(), key=lambda m: m["createdDateTime"], reverse=True)
        return Resp.json(200, {"value": [{k: v for k, v in m.items() if k != "attachments"} for m in msgs]})
