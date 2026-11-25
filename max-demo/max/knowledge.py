"""
Max's knowledge of a team's channel, built only through Microsoft Graph
(exactly what Max may read once installed with RSC permissions):

  posts + replies  <- GET /teams/{id}/channels/{id}/messages?$expand=replies
  files            <- filesFolder -> children -> content (download + text extraction)

Saved in Max's database (max/data/max.db, see store.py), one row per post / file / meeting, so Max
remembers after a restart. Kept up to date as new channel messages arrive (RSC delivers every message).
`data` holds the same dict in memory (posts with replies, files, meetings) for the prompt and stats;
every change is written through to the database at once.
"""

import asyncio
import html
import json
import re
import time
from datetime import datetime
from pathlib import Path

from docs import extract_text
from graph_client import GraphClient
from store import Store


def html_to_text(body: dict) -> str:
    content = (body or {}).get("content") or ""
    if (body or {}).get("contentType") == "text":
        return content
    t = re.sub(r'<at id="\d+">(.*?)</at>', r"@\1", content)
    t = re.sub(r"<attachment[^>]*></attachment>", "", t)
    t = re.sub(r"<br\s*/?>", "\n", t)
    t = re.sub(r"</p>\s*<p>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    return html.unescape(t).strip()


def author_of(msg: dict) -> str:
    frm = msg.get("from") or {}
    who = frm.get("user") or frm.get("application") or {}
    return who.get("displayName") or "Unknown"


def short_time(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso[:16]


async def read_file(graph: GraphClient, drive_id: str, item: dict) -> dict:
    data = await graph.download(drive_id, item["id"])
    text = await asyncio.to_thread(extract_text, item["name"], data)
    return {"id": item["id"], "name": item["name"],
            "author": ((item.get("createdBy") or {}).get("user") or {}).get("displayName"),
            "time": short_time(item.get("lastModifiedDateTime") or item.get("createdDateTime", "")), "text": text}


def author_id_of(msg: dict) -> str | None:
    frm = msg.get("from") or {}
    who = frm.get("user") or frm.get("application") or {}
    return who.get("id")


def author_kind_of(msg: dict) -> str:
    frm = msg.get("from") or {}
    return "person" if frm.get("user") else "app"


def to_post(msg: dict) -> dict:
    return {"id": msg["id"], "author": author_of(msg), "time": short_time(msg.get("createdDateTime", "")),
            "text": html_to_text(msg.get("body")),
            "attachments": [a.get("name") for a in msg.get("attachments", []) if a.get("contentType") == "reference"],
            "replies": [], "authorId": author_id_of(msg), "authorKind": author_kind_of(msg)}


class TeamKnowledge:
    def __init__(self, data: dict, store: Store):
        self.data = data
        self.store = store

    @property
    def team_id(self) -> str:
        return self.data["teamId"]

    # ------------------------------------------------------------------ build
    @classmethod
    async def build(cls, graph: GraphClient, team_id: str, channel_id: str, store: Store, extra: dict) -> "TeamKnowledge":
        team = await graph.team(team_id)
        roots = await graph.get_all(f"/teams/{team_id}/channels/{graph._q(channel_id)}/messages",
                                    {"$top": "50", "$expand": "replies"})
        posts = []
        for m in roots:
            if m.get("messageType") != "message" or m.get("deletedDateTime"):
                continue
            p = to_post(m)
            replies = m.get("replies") or []
            if m.get("replies@odata.nextLink") or len(replies) >= 200:
                replies = await graph.replies(team_id, channel_id, m["id"])
            p["replies"] = [to_post(r) for r in sorted(replies, key=lambda r: r.get("createdDateTime", ""))
                            if not r.get("deletedDateTime")]
            posts.append(p)
        posts.sort(key=lambda p: p["time"])

        folder = await graph.files_folder(team_id, channel_id)
        drive_id = folder["parentReference"]["driveId"]
        items = [i for i in await graph.children(drive_id, folder["id"]) if "file" in i]
        sem = asyncio.Semaphore(4)

        async def read(item):
            async with sem:
                return await read_file(graph, drive_id, item)

        files = await asyncio.gather(*(read(i) for i in items))
        # Baseline for change tracking: later file notifications ask "what changed since this token?"
        delta = await graph.get(f"/drives/{drive_id}/root/delta", {"token": "latest"})
        previous = store.team(team_id) or {}
        data = {"teamId": team_id, "teamName": team.get("displayName"), "channelId": channel_id,
                "driveId": drive_id, "driveDelta": delta.get("@odata.deltaLink"),
                "builtAt": time.strftime("%Y-%m-%dT%H:%M:%S"), "posts": posts, "files": list(files),
                "meetings": [], "meetingAccess": {}, "timeZone": previous.get("timeZone") or "UTC",
                "announcedProblems": previous.get("announcedProblems") or [], **extra}
        store.replace_team_content(data)
        return cls(data, store)

    @classmethod
    def load(cls, store: Store, team_id: str) -> "TeamKnowledge | None":
        """Rebuild the in-memory dict from the database (None if Max doesn't know this team)."""
        data = store.team(team_id)
        if data is None:
            return None
        posts, by_id = [], {}
        for r in store.messages(team_id):
            m = {"id": r["id"], "author": r["author"], "time": r["time"], "text": r["text"],
                 "attachments": json.loads(r["attachments"] or "[]"), "replies": []}
            if r["edited"]:
                m["edited"] = True
            root = by_id.get(r["root_id"]) if r["root_id"] else None
            if root is not None:
                root["replies"].append(m)
            else:
                posts.append(m)
                by_id[m["id"]] = m
        data["posts"] = posts
        data["files"] = [{"id": f["id"], "name": f["name"], "author": f["author"], "time": f["time"],
                          "text": f["text"]} for f in store.files(team_id)]
        data["meetings"] = store.meetings(team_id)
        return cls(data, store)

    @classmethod
    def import_json(cls, store: Store, path: Path) -> "TeamKnowledge":
        """One-time move of an old max/data/teams/<id>.json file into the database."""
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("timeZone", "UTC")
        store.replace_team_content(data)
        return cls.load(store, data["teamId"])

    def save(self) -> None:
        """Persist the team-level fields (drive delta, announced problems, ...). Content is written as it changes."""
        self.store.save_team(self.data)

    # ------------------------------------------------------------ live update
    def add_message(self, msg_id: str, author: str, text: str, root_id: str | None, when: str | None = None,
                    author_id: str | None = None) -> None:
        post = {"id": msg_id, "author": author, "time": when or time.strftime("%Y-%m-%d %H:%M"), "text": text,
                "attachments": [], "replies": []}
        row = {**post, "authorId": author_id}
        if root_id and root_id != msg_id:
            root = next((p for p in self.data["posts"] if p["id"] == root_id), None)
            if root is not None:
                if not any(r["id"] == msg_id for r in root["replies"]):
                    root["replies"].append(post)
                self.store.add_message(self.team_id, row, root_id)
                return
        if not any(p["id"] == msg_id for p in self.data["posts"]):
            self.data["posts"].append(post)
        self.store.add_message(self.team_id, row, None)

    def _find(self, msg_id: str):
        for p in self.data["posts"]:
            if p["id"] == msg_id:
                return p, None
            for r in p["replies"]:
                if r["id"] == msg_id:
                    return r, p
        return None, None

    def update_message(self, msg_id: str, text: str) -> bool:
        m, _ = self._find(msg_id)
        if m is None:
            return False
        m["text"], m["edited"] = text, True
        self.store.update_message(self.team_id, msg_id, text)
        return True

    def delete_message(self, msg_id: str) -> bool:
        m, parent = self._find(msg_id)
        if m is None:
            return False
        if parent:
            parent["replies"] = [r for r in parent["replies"] if r["id"] != msg_id]
        else:
            self.data["posts"] = [p for p in self.data["posts"] if p["id"] != msg_id]
        self.store.delete_message(self.team_id, msg_id)     # soft delete: the text is wiped
        return True

    def upsert_file(self, rec: dict) -> str:
        """Match by id first; a different id with the same name replaces that file (re-upload)."""
        files = self.data["files"]
        i = next((n for n, f in enumerate(files) if f.get("id") == rec["id"]), None)
        if i is None:
            i = next((n for n, f in enumerate(files) if f["name"] == rec["name"]), None)
        replaced = files[i]["id"] if i is not None else None
        if i is None:
            files.append(rec)
            change = "new"
        else:
            files[i] = rec
            change = "updated"
        self.store.upsert_file(self.team_id, rec, replaces_id=replaced)
        return change

    def remove_file(self, item_id: str) -> None:
        self.data["files"] = [f for f in self.data["files"] if f.get("id") != item_id]
        self.store.remove_file(self.team_id, item_id)

    def set_meetings(self, result: dict) -> None:
        self.data["meetings"] = result["meetings"]
        self.data["meetingAccess"] = result["access"]
        self.store.replace_meetings(self.team_id, self.data["meetings"], self.data["meetingAccess"])

    def add_transcript(self, online_meeting_id: str, transcript: dict, meeting_info: dict | None = None) -> dict:
        m = next((m for m in self.data.get("meetings", []) if m.get("onlineMeetingId") == online_meeting_id), None)
        if m is None:
            m = {**(meeting_info or {}), "onlineMeetingId": online_meeting_id, "transcripts": [], "transcriptNote": None}
            self.data.setdefault("meetings", []).append(m)
            self.store.add_meeting(self.team_id, m)            # sets m["_seq"]
        if not any(t["id"] == transcript["id"] for t in m["transcripts"]):
            m["transcripts"].append(transcript)
            self.store.add_transcript(self.team_id, m["_seq"], transcript)
        m["transcriptNote"] = None
        self.store.update_meeting(self.team_id, m)
        return m

    # ---------------------------------------------------------------- views
    @property
    def stats(self) -> dict:
        meetings = self.data.get("meetings", [])
        return {"posts": len(self.data["posts"]),
                "replies": sum(len(p["replies"]) for p in self.data["posts"]),
                "files": len(self.data["files"]), "meetings": len(meetings),
                "transcripts": sum(len(m.get("transcripts", [])) for m in meetings)}

    def access_problems(self) -> list[str]:
        return sorted({v for v in (self.data.get("meetingAccess") or {}).values() if v and v != "ok"})

    def prompt_text(self) -> str:
        parts = [f"# TEAM '{self.data.get('teamName')}': CHANNEL 'General' (posts and replies, oldest first)"]
        for p in self.data["posts"]:
            parts.append(f"\n[{p['time']}] {p['author']}: {p['text']}")
            for a in p["attachments"]:
                parts.append(f"  (attached: {a})")
            for r in p["replies"]:
                parts.append(f"  ↳ [{r['time']}] {r['author']}: {r['text']}")
        parts.append("\n\n# FILES IN THE CHANNEL (documents and meeting minutes)")
        for f in sorted(self.data["files"], key=lambda f: f["name"]):
            parts.append(f"\n=== {f['name']} (uploaded by {f['author']}, last changed {f['time']}) ===")
            parts.append(f["text"])
        parts.append("\n\n# TEAMS MEETINGS (from the team's calendars and official meeting transcripts)")
        for p in self.access_problems():
            parts.append(f"(Access note: {p})")
        for m in sorted(self.data.get("meetings", []), key=lambda m: m.get("start") or ""):
            parts.append(f"\n=== Meeting: {m.get('subject')} ({m.get('start')} to {m.get('end', '?')}, "
                         f"organizer {m.get('organizer')}) ===")
            if not m.get("transcripts"):
                parts.append(f"(No transcript available: {m.get('transcriptNote') or 'not recorded yet'})")
            for t in m.get("transcripts", []):
                parts.append(f"[Official transcript, created {t.get('created')}]")
                parts.extend(f"{c['speaker']}: {c['text']}" for c in t["cues"])
        return "\n".join(parts)
