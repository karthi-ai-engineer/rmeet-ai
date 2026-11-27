"""
The simulated Teams data: people, departments (teams), channels, chats, messages. One SQLite file
(data/teams_sim.db). Plain SQL, no ORM. This plays the part of Microsoft's cloud: Max never reads it directly,
only through the fake Bot Framework service (bot_connector.py), the same way it would talk to real Teams.

  conn = connect(path)                         opens; creates and fills with the start set if new
  post(conn, author, kind, where, text, ...)   kind "channel" or "chat"; thread_id = reply in a channel thread
  channel_threads(conn, channel) / chat_messages(conn, chat)
  teams_for(conn, person) / chats_for(conn, person) / can_see(conn, person, kind, where)
  edit / delete / reset

Message ids are numbers that grow, like Teams ids (milliseconds since 1970).
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from teams_sim.cloud import seed

SCHEMA_VERSION = 2  # simulator data can always be rebuilt: a new version simply starts from the start set

SCHEMA = [
    "CREATE TABLE people (id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL, is_bot INTEGER NOT NULL DEFAULT 0)",
    "CREATE TABLE teams (id TEXT PRIMARY KEY, name TEXT NOT NULL, pos INTEGER NOT NULL)",
    "CREATE TABLE team_members (team_id TEXT NOT NULL, person_id TEXT NOT NULL, PRIMARY KEY (team_id, person_id))",
    """CREATE TABLE channels (id TEXT PRIMARY KEY, team_id TEXT NOT NULL, name TEXT NOT NULL,
        private INTEGER NOT NULL DEFAULT 0, pos INTEGER NOT NULL)""",
    "CREATE TABLE channel_members (channel_id TEXT NOT NULL, person_id TEXT NOT NULL, PRIMARY KEY (channel_id, person_id))",
    "CREATE TABLE chats (id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT)",  # kind: max, group, oneToOne
    "CREATE TABLE chat_members (chat_id TEXT NOT NULL, person_id TEXT NOT NULL, PRIMARY KEY (chat_id, person_id))",
    """CREATE TABLE messages (
        id          TEXT PRIMARY KEY,           -- Teams-like: milliseconds, always growing
        where_kind  TEXT NOT NULL,              -- channel | chat
        where_id    TEXT NOT NULL,
        thread_id   TEXT,                       -- channel replies: the root post's id
        author      TEXT NOT NULL,
        text        TEXT NOT NULL,
        mentions    TEXT NOT NULL DEFAULT '[]', -- person ids
        attachments TEXT NOT NULL DEFAULT '[]', -- cards etc., exactly as sent
        quote       TEXT,                       -- {"id", "author", "text"} of a quoted message
        created_at  TEXT NOT NULL,              -- UTC, ISO 8601
        edited_at   TEXT,
        deleted     INTEGER NOT NULL DEFAULT 0,
        ai_label    INTEGER NOT NULL DEFAULT 0, -- the bot marked it "AI generated" (Teams shows the label)
        feedback    INTEGER NOT NULL DEFAULT 0, -- the bot asked for 👍/👎 (Teams shows the buttons)
        pending     INTEGER NOT NULL DEFAULT 0  -- a bot answer still streaming: not shown in lists until final
    )""",
    "CREATE INDEX messages_by_place ON messages (where_kind, where_id, created_at)",
]
TABLES = ["people", "teams", "team_members", "channels", "channel_members", "chats", "chat_members", "messages"]


class NotAllowed(Exception):
    """The person can't do this (can't see the place, empty message, bad thread)."""


class NotFound(Exception):
    pass


# ---------------------------------------------------------------- open, create, reset

def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)  # autocommit; we use explicit BEGIN
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    if conn.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
        _rebuild(conn)
    return conn


def _rebuild(conn: sqlite3.Connection) -> None:
    conn.execute("BEGIN IMMEDIATE")
    try:
        for t in TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {t}")
        for statement in SCHEMA:
            conn.execute(statement)
        _fill(conn)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def drop_unfinished(conn: sqlite3.Connection) -> int:
    """Answers that were still streaming when the program stopped never finish: remove them (done at start)."""
    return conn.execute("DELETE FROM messages WHERE pending = 1").rowcount


def reset(conn: sqlite3.Connection) -> None:
    """Back to the start set (the simulator's Reset button)."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        for t in TABLES:
            conn.execute(f"DELETE FROM {t}")
        _fill(conn)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def _fill(conn: sqlite3.Connection) -> None:
    for pid, name, role in seed.PEOPLE:
        conn.execute("INSERT INTO people VALUES (?, ?, ?, 0)", (pid, name, role))
    conn.execute("INSERT INTO people VALUES (?, ?, ?, 1)", seed.MAX)
    for pos, (tid, name, members, channels) in enumerate(seed.TEAMS):
        conn.execute("INSERT INTO teams VALUES (?, ?, ?)", (tid, name, pos))
        for p in [*members, "max"]:  # Max is installed in every department
            conn.execute("INSERT INTO team_members VALUES (?, ?)", (tid, p))
        for cpos, (cid, cname, private_for) in enumerate(channels):
            conn.execute("INSERT INTO channels VALUES (?, ?, ?, ?, ?)", (cid, tid, cname, int(bool(private_for)), cpos))
            for p in private_for or []:
                conn.execute("INSERT INTO channel_members VALUES (?, ?)", (cid, p))
    for pid, *_ in seed.PEOPLE:
        _add_chat(conn, f"max-{pid}", "max", None, [pid, "max"])
    for cid, kind, title, members in seed.CHATS:
        _add_chat(conn, cid, kind, title, members)
    keys: dict[str, str] = {}
    for kind, where, root, key, author, at, text in seed.MESSAGES:
        mid = str(_ms(at))
        keys[key] = mid
        conn.execute(
            "INSERT INTO messages (id, where_kind, where_id, thread_id, author, text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (mid, kind, where, keys[root] if root else None, author, text, _iso(int(mid))),
        )


def _add_chat(conn, cid, kind, title, members):
    conn.execute("INSERT INTO chats VALUES (?, ?, ?)", (cid, kind, title))
    for p in members:
        conn.execute("INSERT INTO chat_members VALUES (?, ?)", (cid, p))


# ---------------------------------------------------------------- people and places

def people(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM people WHERE is_bot = 0 ORDER BY rowid")]


def person(conn, pid: str) -> dict:
    row = conn.execute("SELECT * FROM people WHERE id = ?", (pid,)).fetchone()
    if not row:
        raise NotFound(f"no person {pid!r}")
    return dict(row)


def teams_for(conn, pid: str) -> list[dict]:
    """The departments this person is in, each with the channels they can see."""
    out = []
    for t in conn.execute(
        "SELECT t.* FROM teams t JOIN team_members m ON m.team_id = t.id WHERE m.person_id = ? ORDER BY t.pos", (pid,)
    ):
        chans = [
            dict(c) for c in conn.execute("SELECT * FROM channels WHERE team_id = ? ORDER BY pos", (t["id"],))
            if _channel_visible(conn, pid, c)
        ]
        members = [r[0] for r in conn.execute("SELECT person_id FROM team_members WHERE team_id = ?", (t["id"],))]
        out.append({**dict(t), "channels": chans, "members": members})
    return out


def channel(conn, cid: str) -> dict:
    row = conn.execute("SELECT * FROM channels WHERE id = ?", (cid,)).fetchone()
    if not row:
        raise NotFound(f"no channel {cid!r}")
    return dict(row)


def chat(conn, cid: str) -> dict:
    row = conn.execute("SELECT * FROM chats WHERE id = ?", (cid,)).fetchone()
    if not row:
        raise NotFound(f"no chat {cid!r}")
    members = [r[0] for r in conn.execute("SELECT person_id FROM chat_members WHERE chat_id = ?", (cid,))]
    return {**dict(row), "members": members}


def chats_for(conn, pid: str) -> list[dict]:
    ids = [r[0] for r in conn.execute("SELECT chat_id FROM chat_members WHERE person_id = ?", (pid,))]
    return [chat(conn, c) for c in ids]


def max_chat_for(conn, pid: str) -> dict:
    return chat(conn, f"max-{pid}")


def members_of(conn, kind: str, where: str) -> list[str]:
    """Everyone who can see this place (bot included)."""
    if kind == "chat":
        return chat(conn, where)["members"]
    c = channel(conn, where)
    team = [r[0] for r in conn.execute("SELECT person_id FROM team_members WHERE team_id = ?", (c["team_id"],))]
    return [p for p in team if _channel_visible(conn, p, c)]


def _channel_visible(conn, pid: str, c) -> bool:
    if not conn.execute("SELECT 1 FROM team_members WHERE team_id = ? AND person_id = ?", (c["team_id"], pid)).fetchone():
        return False
    if not c["private"]:
        return True
    return bool(conn.execute("SELECT 1 FROM channel_members WHERE channel_id = ? AND person_id = ?", (c["id"], pid)).fetchone())


def find_mentions(conn, text: str, kind: str, where: str) -> list[str]:
    """People (and Max) tagged as @Name in the text, if they are in this place."""
    found = []
    for pid in members_of(conn, kind, where):
        name = person(conn, pid)["name"]
        if re.search(rf"(?<!\w)@{re.escape(name)}(?!\w)", text, flags=re.IGNORECASE):
            found.append(pid)
    return found


def can_see(conn, pid: str, kind: str, where: str) -> bool:
    try:
        if kind == "channel":
            return _channel_visible(conn, pid, channel(conn, where))
        if kind == "chat":
            return pid in chat(conn, where)["members"]
    except NotFound:
        return False
    return False


# ---------------------------------------------------------------- messages

def post(conn, author: str, kind: str, where: str, text: str, *, thread_id: str | None = None,
         quote_id: str | None = None, mentions: list[str] | None = None, attachments: list[dict] | None = None,
         ai_label: bool = False, feedback: bool = False, pending: bool = False) -> dict:
    """A new message. In a channel: a new post, or a reply when thread_id is the root post's id.
    pending=True: a bot answer that is still streaming (finish() makes it visible)."""
    if not can_see(conn, author, kind, where):
        raise NotAllowed(f"{author} can't post in {kind} {where}")
    if not pending and not text.strip() and not attachments:
        raise NotAllowed("empty message")
    if thread_id is not None:
        root = _row(conn, thread_id)
        if kind != "channel" or root["where_kind"] != "channel" or root["where_id"] != where or root["thread_id"]                 or root["deleted"]:
            raise NotAllowed("replies go to a root post (not deleted) in the same channel")
    quote = _quote(conn, quote_id, kind, where)
    conn.execute("BEGIN IMMEDIATE")
    try:
        mid = str(max(int(time.time() * 1000), _last_id(conn) + 1))
        conn.execute(
            """INSERT INTO messages (id, where_kind, where_id, thread_id, author, text, mentions, attachments, quote,
                                     created_at, ai_label, feedback, pending)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (mid, kind, where, thread_id, author, text, json.dumps(mentions or []), json.dumps(attachments or []),
             json.dumps(quote) if quote else None, _now(), int(ai_label), int(feedback), int(pending)),
        )
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return get_message(conn, mid)


def _quote(conn, quote_id: str | None, kind: str, where: str) -> dict | None:
    if quote_id is None:
        return None
    q = _row(conn, quote_id)
    if (q["where_kind"], q["where_id"]) != (kind, where) or q["deleted"] or q["pending"]:
        raise NotAllowed("can only quote a (not deleted) message from the same place")
    return {"id": q["id"], "author": q["author"], "text": q["text"]}


def finish(conn, mid: str, text: str, *, attachments: list[dict] | None = None, quote_id: str | None = None,
           mentions: list[str] | None = None, ai_label: bool = False, feedback: bool = False) -> dict:
    """The final version of a streamed answer: now it is a normal message (its time = when it was finished)."""
    row = _row(conn, mid)
    if not row["pending"]:
        raise NotAllowed("this message is not streaming")
    if not text.strip() and not attachments:
        raise NotAllowed("empty message")
    quote = _quote(conn, quote_id, row["where_kind"], row["where_id"])
    conn.execute(
        """UPDATE messages SET text = ?, attachments = ?, quote = ?, mentions = ?, ai_label = ?, feedback = ?,
                               pending = 0, created_at = ? WHERE id = ?""",
        (text, json.dumps(attachments or []), json.dumps(quote) if quote else None, json.dumps(mentions or []),
         int(ai_label), int(feedback), _now(), mid))
    return get_message(conn, mid)


def edit(conn, mid: str, text: str, attachments: list[dict] | None = None) -> dict:
    row = _row(conn, mid)
    if row["deleted"]:
        raise NotFound(f"message {mid} was deleted")
    if not text.strip() and not attachments:
        raise NotAllowed("empty message")
    if attachments is None:
        conn.execute("UPDATE messages SET text = ?, edited_at = ? WHERE id = ?", (text, _now(), mid))
    else:
        conn.execute("UPDATE messages SET text = ?, attachments = ?, edited_at = ? WHERE id = ?",
                     (text, json.dumps(attachments), _now(), mid))
    return get_message(conn, mid)


def delete(conn, mid: str) -> dict:
    _row(conn, mid)
    conn.execute("UPDATE messages SET deleted = 1, edited_at = ? WHERE id = ?", (_now(), mid))
    return get_message(conn, mid)


def get_message(conn, mid: str) -> dict:
    return _to_dict(_row(conn, mid))


def channel_threads(conn, cid: str) -> list[dict]:
    """Root posts (oldest first), each with its replies (oldest first). Deleted messages are left out."""
    rows = [_to_dict(r) for r in conn.execute(
        "SELECT * FROM messages WHERE where_kind = 'channel' AND where_id = ? AND deleted = 0 AND pending = 0 "
        "ORDER BY created_at, id", (cid,))]
    roots = [{**m, "replies": []} for m in rows if not m["thread_id"]]
    by_id = {m["id"]: m for m in roots}
    for m in rows:
        if m["thread_id"] in by_id:
            by_id[m["thread_id"]]["replies"].append(m)
    return roots


def chat_messages(conn, cid: str) -> list[dict]:
    return [_to_dict(r) for r in conn.execute(
        "SELECT * FROM messages WHERE where_kind = 'chat' AND where_id = ? AND deleted = 0 AND pending = 0 "
        "ORDER BY created_at, id", (cid,))]


def _row(conn, mid: str):
    row = conn.execute("SELECT * FROM messages WHERE id = ?", (mid,)).fetchone()
    if not row:
        raise NotFound(f"no message {mid!r}")
    return row


def _to_dict(row) -> dict:
    d = dict(row)
    d["mentions"] = json.loads(d["mentions"])
    d["attachments"] = json.loads(d["attachments"])
    d["quote"] = json.loads(d["quote"]) if d["quote"] else None
    return d


def _last_id(conn) -> int:
    return conn.execute("SELECT COALESCE(MAX(CAST(id AS INTEGER)), 0) FROM messages").fetchone()[0]


def _now() -> str:
    return _iso(int(time.time() * 1000))


def _iso(ms: int) -> str:
    """One time format everywhere (sorts correctly as text): 2026-11-27T05:32:00.000Z"""
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)
