"""
The fake Teams tenant's data: one team (Planning Department), its General channel,
members, channel messages (roots + replies), channel files (SharePoint document
library) and the installation state of apps (Max).

Seeded from simulations/planning-department (thread.json, documents, past meetings).
Messages added at runtime (people posting, Max replying) are persisted in
state/channel_state.json so they survive restarts. IDs follow the real formats
(see docs/research/teams/01-bot-messaging.md §2.3 and 02-graph-knowledge-apis.md §1).
"""

import base64
import hashlib
import html
import json
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import yaml

STATE_DIR = Path(__file__).resolve().parent / "state"
STATE_FILE = STATE_DIR / "channel_state.json"
WORLD = Path(__file__).resolve().parents[1] / "planning-department"

NS = uuid.NAMESPACE_URL
DOMAIN = "kestrelhomegoods"
TENANT_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{DOMAIN}.onmicrosoft.com"))
TEAM_GROUP_ID = str(uuid.uuid5(NS, "kestrel/teams/planning-department"))           # Graph team id (= M365 group id)
TEAM_THREAD_ID = f"19:{uuid.uuid5(NS, 'kestrel/thread/planning').hex}@thread.tacv2"  # Bot team id; General channel id == team id
CHANNEL_ID = TEAM_THREAD_ID
SITE_URL = f"https://{DOMAIN}.sharepoint.com/sites/PlanningDepartment"
DRIVE_ID = "b!" + base64.urlsafe_b64encode(hashlib.sha256(b"kestrel-planning-drive").digest()).decode().rstrip("=")[:64]
FOLDER_ID = "01" + base64.b32encode(hashlib.sha1(b"general-folder").digest()).decode()[:32]

MIME = {
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pdf": "application/pdf",
    ".md": "text/markdown",
}


def iso(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def ms_from_local(s: str) -> int:
    """thread.json times are local wall-clock; treat them as UTC for stable ids."""
    return int(datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp() * 1000)


def item_id(key: str) -> str:
    return "01" + base64.b32encode(hashlib.sha1(key.encode()).digest()).decode()[:32]


class TeamsStore:
    def __init__(self):
        self.lock = threading.RLock()
        self.listeners = []
        team = yaml.safe_load((WORLD / "team.yaml").read_text(encoding="utf-8"))
        self.company = team["company"]["name"]
        self.team_name = team["team"]["name"]
        self.users = {}
        for m in team["members"]:
            first = m["name"].split()[0]
            self.users[m["id"]] = {
                "key": m["id"], "name": m["name"], "givenName": first,
                "surname": " ".join(m["name"].split()[1:]),
                "aadObjectId": str(uuid.uuid5(NS, f"kestrel/user/{m['id']}")),
                "email": f"{first.lower()}@{DOMAIN}.com", "role": m.get("role", ""),
                "userRole": "owner" if m["id"] == "karthi" else "user",
            }
        self.files = {}          # itemId -> driveItem record (+ local path)
        self.roots = {}          # rootId -> {"msg": msg, "replies": [msg]}
        self.install = {"installed": False}
        self.admin = self.default_admin()
        self.uploads = []        # runtime file uploads (persisted)
        self.seq = 0             # change counter for drive delta
        self._seed()
        self._load_state()

    @staticmethod
    def default_admin() -> dict:
        """Tenant admin settings. Defaults mirror a fresh real tenant."""
        return {
            "consented": [],                 # tenant-wide Graph application permissions granted to the app
            "accessPolicy": False,           # CsApplicationAccessPolicy assigned (needed for onlineMeetings APIs)
            "transcriptApiAccess": False,    # Teams admin: "Graph API access to transcripts" (off by default)
        }

    def next_seq(self) -> int:
        with self.lock:
            self.seq += 1
            return self.seq

    # ------------------------------------------------------------- listeners
    def on_change(self, fn) -> None:
        self.listeners.append(fn)

    def _emit(self, event: dict) -> None:
        for fn in self.listeners:
            try:
                fn(event)
            except Exception:
                pass

    # ------------------------------------------------------------------ ids
    def pairwise_user_id(self, user_key: str, app_id: str) -> str:
        """29: ids are unique per bot+user (real Teams behaviour)."""
        h = hashlib.sha256(f"{app_id}/{self.users[user_key]['aadObjectId']}".encode()).digest()
        return "29:1" + base64.urlsafe_b64encode(h).decode().rstrip("=")[:46]

    def user_by_pairwise(self, pid: str, app_id: str):
        return next((k for k in self.users if self.pairwise_user_id(k, app_id) == pid), None)

    @staticmethod
    def now_ms() -> int:
        """Team wall-clock time stored 'as UTC' (same convention as the seeded thread times)."""
        return int((time.time() + time.localtime().tm_gmtoff) * 1000)

    def _new_message_id(self) -> str:
        with self.lock:
            ms = self.now_ms()
            existing = {r for r in self.roots} | {m["id"] for r in self.roots.values() for m in r["replies"]}
            while str(ms) in existing:
                ms += 1
            return str(ms)

    # ---------------------------------------------------------------- seeding
    def _add_file(self, local: Path, name: str, author: str, when_ms: int, world_rel: str) -> dict:
        iid = item_id(world_rel)
        etag_guid = str(uuid.uuid5(NS, "etag/" + world_rel)).upper()
        rec = {
            "id": iid, "name": name, "size": local.stat().st_size, "local": str(local), "worldPath": world_rel,
            "author": author, "createdMs": when_ms, "etagGuid": etag_guid,
            "webUrl": f"{SITE_URL}/Shared%20Documents/General/{quote(name)}",
            "mime": MIME.get(local.suffix.lower(), "application/octet-stream"),
            "modifiedMs": when_ms, "version": 1, "seq": self.next_seq(), "deleted": False,
        }
        self.files[iid] = rec
        return rec

    UPLOAD_DIR = STATE_DIR / "uploads"

    def _apply_upload(self, up: dict) -> dict:
        existing = next((f for f in self.files.values() if f["name"].lower() == up["name"].lower()), None)
        local = Path(up["local"])
        if existing:
            existing.update({"local": str(local), "size": local.stat().st_size, "modifiedMs": up["modifiedMs"],
                             "version": existing["version"] + 1, "seq": self.next_seq(), "deleted": False,
                             "worldPath": f"drive:{existing['id']}"})
            return existing
        rec = self._add_file(local, up["name"], up["author"], up["createdMs"], f"upload/{up['name']}")
        rec["worldPath"] = f"drive:{rec['id']}"
        return rec

    def upload_file(self, user_key: str, name: str, data: bytes) -> tuple[dict, str]:
        """A person uploads a file to the channel's Files (SharePoint document library)."""
        name = re.sub(r'[\\/:*?"<>|]+', "_", name).strip() or "file"
        with self.lock:
            self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            local = self.UPLOAD_DIR / name
            local.write_bytes(data)
            existed = any(f["name"].lower() == name.lower() for f in self.files.values())
            now = self.now_ms()
            up = {"name": name, "local": str(local), "author": user_key, "createdMs": now, "modifiedMs": now}
            self.uploads = [u for u in self.uploads if u["name"].lower() != name.lower()] + [up]
            rec = self._apply_upload(up)
            self._save_state()
        change = "updated" if existed else "created"
        self._emit({"type": "file", "change": change, "itemId": rec["id"], "name": rec["name"]})
        return rec, change

    def files_changed_since(self, seq: int) -> list:
        return sorted((f for f in self.files.values() if f["seq"] > seq), key=lambda f: f["seq"])

    # ------------------------------------------------------------------ admin
    def set_admin(self, **changes) -> dict:
        with self.lock:
            for k, v in changes.items():
                if k in self.admin and v is not None:
                    self.admin[k] = v
            self._save_state()
        self._emit({"type": "admin", "admin": self.admin})
        return self.admin

    def _seed(self) -> None:
        thread = json.loads((WORLD / "thread" / "thread.json").read_text(encoding="utf-8"))
        meetings = {d.name: d for d in (WORLD / "meetings").iterdir() if d.is_dir()}
        for post in thread["posts"]:
            ms = ms_from_local(post["time"])
            atts = []
            for a in post["attachments"]:
                if a.startswith("../meetings/"):
                    mdir, fname = a.split("/")[2], a.split("/")[3]
                    title = (meetings[mdir] / "transcript.md").read_text(encoding="utf-8").splitlines()[0]
                    title = title.lstrip("# ").replace("Transcript: ", "")
                    kind = "Minutes" if fname.startswith("minutes") else "Transcript"
                    name = f"{mdir[:10]} {title} - {kind}.md"
                    rec = self._add_file(meetings[mdir] / fname, name, post["author"], ms, f"meetings/{mdir}/{fname}")
                else:
                    rec = self._add_file(WORLD / "thread" / a, a.split("/")[-1], post["author"], ms, f"thread/{a}")
                atts.append(self._file_attachment(rec))
            root = self._make_msg(str(ms), None, ms, {"user": post["author"]}, post["text"],
                                  [], atts, self._reactions(post.get("reactions", {}), ms))
            self.roots[root["id"]] = {"msg": root, "replies": []}
            for r in post.get("replies", []):
                rms = ms_from_local(r["time"])
                rep = self._make_msg(str(rms), root["id"], rms, {"user": r["author"]}, r["text"], [], [], [])
                self.roots[root["id"]]["replies"].append(rep)
                root["lastModifiedMs"] = max(root["lastModifiedMs"], rms)

    def _reactions(self, reactions: dict, ms: int) -> list:
        out = []
        for emoji, who in reactions.items():
            for u in who:
                if u in self.users:
                    out.append({"reactionType": emoji, "user": u, "createdMs": ms + 60_000})
        return out

    def _file_attachment(self, rec: dict) -> dict:
        return {"id": rec["etagGuid"], "contentType": "reference", "contentUrl": rec["webUrl"].replace("%20", " "),
                "content": None, "name": rec["name"], "thumbnailUrl": None, "teamsAppId": None, "_itemId": rec["id"]}

    def _make_msg(self, mid, reply_to, ms, author: dict, text: str, mentions: list, attachments: list,
                  reactions: list, cards: list | None = None, text_format: str = "plain") -> dict:
        return {"id": mid, "replyToId": reply_to, "createdMs": ms, "lastModifiedMs": ms, "author": author,
                "text": text, "textFormat": text_format, "mentions": mentions, "attachments": attachments,
                "reactions": reactions, "cards": cards or [], "deleted": False}

    # ------------------------------------------------------------ persistence
    def _load_state(self) -> None:
        if not STATE_FILE.exists():
            return
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        self.install = state.get("install", {"installed": False})
        self.admin = {**self.default_admin(), **state.get("admin", {})}
        for up in state.get("uploads", []):
            if Path(up["local"]).exists():
                self.uploads.append(up)
                self._apply_upload(up)
        for m in state.get("messages", []):
            if m["replyToId"] is None:
                self.roots[m["id"]] = {"msg": m, "replies": []}
            elif m["replyToId"] in self.roots:
                self.roots[m["replyToId"]]["replies"].append(m)
                root = self.roots[m["replyToId"]]["msg"]
                root["lastModifiedMs"] = max(root["lastModifiedMs"], m["createdMs"])

    def _save_state(self) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        added = [m for r in self.roots.values() for m in [r["msg"], *r["replies"]] if m.get("runtime")]
        added.sort(key=lambda m: m["createdMs"])
        STATE_FILE.write_text(json.dumps({"install": self.install, "admin": self.admin, "uploads": self.uploads,
                                          "messages": added}, indent=1, ensure_ascii=False), encoding="utf-8")

    def reset(self) -> None:
        """Back to the seeded world (removes runtime posts/uploads, uninstalls Max, admin defaults)."""
        with self.lock:
            if STATE_FILE.exists():
                STATE_FILE.unlink()
            if self.UPLOAD_DIR.exists():
                for f in self.UPLOAD_DIR.iterdir():
                    f.unlink()
            self.files, self.roots, self.install = {}, {}, {"installed": False}
            self.admin, self.uploads, self.seq = self.default_admin(), [], 0
            self._seed()
        self._emit({"type": "reset"})

    # --------------------------------------------------------------- install
    def set_installed(self, installed: bool, app: dict | None = None, rsc: list | None = None) -> None:
        with self.lock:
            self.install = {"installed": installed, "appId": (app or {}).get("appId"), "name": (app or {}).get("name"),
                            "rsc": rsc or [], "time": int(time.time() * 1000)} if installed else {"installed": False}
            self._save_state()
        self._emit({"type": "install", "install": self.install})

    def has_rsc(self, perm: str) -> bool:
        return self.install.get("installed") and perm in self.install.get("rsc", [])

    # -------------------------------------------------------------- messages
    MENTION_RE = re.compile(r"@(Max|Karthi(?: M)?|Prince(?: Raj)?|Daniel(?: Ito)?|Jacob(?: Thomas)?)\b", re.IGNORECASE)

    def parse_user_text(self, text: str, app: dict | None):
        """Turn '@Max hello' typed in the UI into mentions like the Teams client does."""
        mentions = []

        def repl(m):
            word = m.group(1).lower()
            if word == "max":
                if not (app and self.install.get("installed")):
                    return m.group(0)       # app not in the team: plain text, no mention
                target = {"app": app["appId"], "name": app.get("name", "Max")}
            else:
                key = next(k for k in self.users if self.users[k]["name"].lower().startswith(word.split()[0]))
                target = {"user": key, "name": self.users[key]["name"]}
            mentions.append({"id": len(mentions), "mentionText": target["name"], **target})
            return f"\u0000{len(mentions) - 1}\u0000"

        marked = self.MENTION_RE.sub(repl, text)
        return marked, mentions

    def add_message(self, author: dict, marked_text: str, mentions: list, root_id: str | None,
                    attachments: list | None = None, cards: list | None = None, text_format: str = "plain") -> dict:
        with self.lock:
            if root_id and root_id not in self.roots:
                raise KeyError(root_id)
            mid = self._new_message_id()
            ms = int(mid)
            msg = self._make_msg(mid, root_id, ms, author, marked_text, mentions, attachments or [], [], cards,
                                 text_format)
            msg["runtime"] = True
            if root_id:
                self.roots[root_id]["replies"].append(msg)
                self.roots[root_id]["msg"]["lastModifiedMs"] = ms
            else:
                self.roots[mid] = {"msg": msg, "replies": []}
            self._save_state()
        self._emit({"type": "message", "message": self.ui_message(msg)})
        return msg

    def add_meeting_post(self, organizer: str, meeting: dict) -> dict:
        """Channel meetings create a channel post with a meetingReference attachment; the meeting chat is its thread."""
        org = self.users[organizer]
        att = {"id": str(uuid.uuid4()), "contentType": "meetingReference", "contentUrl": None, "name": None,
               "content": json.dumps({"exchangeId": meeting["eventId"], "organizerId": org["aadObjectId"]}),
               "thumbnailUrl": None, "teamsAppId": None}
        with self.lock:
            mid = self._new_message_id()
            msg = self._make_msg(mid, None, int(mid), {"user": organizer}, f"Meeting started: {meeting['title']}",
                                 [], [att], [])
            msg["runtime"] = True
            msg["meeting"] = {"title": meeting["title"], "state": "live"}
            self.roots[mid] = {"msg": msg, "replies": []}
            self._save_state()
        self._emit({"type": "message", "message": self.ui_message(msg)})
        return msg

    def end_meeting_post(self, mid: str) -> None:
        with self.lock:
            msg = self.find(mid)
            if not msg or not msg.get("meeting"):
                return
            msg["meeting"]["state"] = "ended"
            msg["text"] = f"Meeting ended: {msg['meeting']['title']}"
            self._save_state()
        self._emit({"type": "message_updated", "message": self.ui_message(msg)})

    def update_message(self, mid: str, text: str | None, cards: list | None) -> dict | None:
        with self.lock:
            msg = self.find(mid)
            if not msg:
                return None
            if text is not None:
                msg["text"] = text
            if cards is not None:
                msg["cards"] = cards
            msg["lastModifiedMs"] = self.now_ms()
            msg["edited"] = True
            self._save_state()
        self._emit({"type": "message_updated", "message": self.ui_message(msg)})
        return msg

    def delete_message(self, mid: str) -> bool:
        with self.lock:
            msg = self.find(mid)
            if not msg:
                return False
            msg["deleted"] = True
            msg["text"] = ""
            msg["cards"] = []
            self._save_state()
        self._emit({"type": "message_deleted", "id": mid})
        return True

    def find(self, mid: str) -> dict | None:
        if mid in self.roots:
            return self.roots[mid]["msg"]
        for r in self.roots.values():
            for m in r["replies"]:
                if m["id"] == mid:
                    return m
        return None

    def sorted_roots(self) -> list:
        """Graph order: by last activity in the reply chain, newest first."""
        return sorted(self.roots.values(), key=lambda r: r["msg"]["lastModifiedMs"], reverse=True)

    # ------------------------------------------------------------ renderers
    @staticmethod
    def render_text(msg: dict, style: str) -> str:
        """style: 'activity' (<at>Name</at>), 'html' (<at id="0">Name</at>), 'plain' (@Name)."""
        text = msg["text"]
        out = []
        for i, part in enumerate(re.split(r"\u0000(\d+)\u0000", text)):
            if i % 2 == 1:
                m = msg["mentions"][int(part)]
                name = m["mentionText"]
                out.append({"activity": f"<at>{name}</at>", "plain": f"@{name}",
                            "html": f'<at id="{m["id"]}">{html.escape(name)}</at>'}[style])
            else:
                out.append(html.escape(part).replace("\n", "<br>") if style == "html" else part)
        return "".join(out)

    def author_name(self, msg: dict) -> str:
        a = msg["author"]
        return self.users[a["user"]]["name"] if "user" in a else a.get("name", "Max")

    def ui_message(self, msg: dict) -> dict:
        a = msg["author"]
        return {
            "id": msg["id"], "rootId": msg["replyToId"], "time": iso(msg["createdMs"]),
            "author": a.get("user") or "max", "isBot": "app" in a, "authorName": self.author_name(msg),
            "text": self.render_text(msg, "plain"), "textFormat": msg.get("textFormat", "plain"),
            "mentions": [m["mentionText"] for m in msg["mentions"]], "edited": msg.get("edited", False),
            "deleted": msg.get("deleted", False), "cards": msg.get("cards", []), "meeting": msg.get("meeting"),
            "attachments": [{"name": at["name"], "path": self.files[at["_itemId"]]["worldPath"]}
                            for at in msg["attachments"] if at.get("_itemId") in self.files],
            "reactions": [{"emoji": r["reactionType"], "user": r["user"]} for r in msg["reactions"]],
        }

    def ui_channel(self) -> dict:
        roots = sorted(self.roots.values(), key=lambda r: r["msg"]["createdMs"])
        files = [{"id": f["id"], "name": f["name"], "author": f["author"], "time": iso(f["modifiedMs"]),
                  "path": f["worldPath"], "version": f["version"]}
                 for f in sorted(self.files.values(), key=lambda f: f["modifiedMs"]) if not f.get("deleted")]
        return {"posts": [{**self.ui_message(r["msg"]), "replies": [self.ui_message(m) for m in r["replies"]]}
                          for r in roots], "files": files, "admin": self.admin,
                "install": self.install, "ids": {"tenant": TENANT_ID, "team": TEAM_GROUP_ID, "channel": CHANNEL_ID}}
