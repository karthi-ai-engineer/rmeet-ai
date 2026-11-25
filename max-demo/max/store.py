"""
Max's database: max/data/max.db (SQLite).

One file for everything Max remembers, written row by row (the old design rewrote one JSON file per team on
every message). WAL mode so reads never wait for writes; all writes go through one lock (one writer).
The schema is versioned (PRAGMA user_version): later steps add tables with new MIGRATIONS entries.

Tables (step 4.1):
  teams              team-level facts: channel, drive + delta token, time zone, meeting access, ...
  conversation_refs  where Max may post in each team (channel id + service URL)
  people             everyone Max has seen in a team (name, AAD id, kind: person / app / max)
  messages           channel posts and replies (root_id NULL = a post); deletes are soft and wipe the text
  files              channel files with their extracted text
  meetings, transcripts, transcript_lines   Teams meetings and their official transcripts
  subscriptions      Graph change-notification subscriptions
  inbound_events     (source, event id) seen once: every channel message reaches Max twice (bot + Graph)
  runs, audit        one row per piece of work; append-only log of what Max did
"""

import json
import re
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

MIGRATIONS: list[str] = [
    # 1 (step 4.1)
    """
    CREATE TABLE teams (
        team_id TEXT PRIMARY KEY, name TEXT, channel_id TEXT, drive_id TEXT, drive_delta TEXT, built_at TEXT,
        time_zone TEXT NOT NULL DEFAULT 'UTC', meeting_access TEXT NOT NULL DEFAULT '{}',
        announced_problems TEXT NOT NULL DEFAULT '[]', extra TEXT NOT NULL DEFAULT '{}');
    CREATE TABLE conversation_refs (
        team_id TEXT PRIMARY KEY, channel_id TEXT NOT NULL, service_url TEXT NOT NULL, updated_at REAL NOT NULL);
    CREATE TABLE people (
        team_id TEXT NOT NULL, name TEXT NOT NULL, aad_id TEXT, email TEXT, kind TEXT NOT NULL DEFAULT 'person',
        role TEXT, first_seen REAL NOT NULL, PRIMARY KEY (team_id, name));
    CREATE TABLE messages (
        seq INTEGER PRIMARY KEY AUTOINCREMENT, team_id TEXT NOT NULL, id TEXT NOT NULL, root_id TEXT,
        author TEXT, author_id TEXT, time TEXT, text TEXT NOT NULL DEFAULT '', attachments TEXT NOT NULL DEFAULT '[]',
        edited INTEGER NOT NULL DEFAULT 0, deleted_at REAL, UNIQUE (team_id, id));
    CREATE INDEX messages_root ON messages (team_id, root_id);
    CREATE TABLE files (
        seq INTEGER PRIMARY KEY AUTOINCREMENT, team_id TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL,
        author TEXT, time TEXT, text TEXT NOT NULL DEFAULT '', UNIQUE (team_id, id));
    CREATE TABLE meetings (
        seq INTEGER PRIMARY KEY AUTOINCREMENT, team_id TEXT NOT NULL, online_meeting_id TEXT, data TEXT NOT NULL);
    CREATE INDEX meetings_team ON meetings (team_id);
    CREATE TABLE transcripts (
        seq INTEGER PRIMARY KEY AUTOINCREMENT, team_id TEXT NOT NULL, meeting_seq INTEGER NOT NULL,
        transcript_id TEXT NOT NULL, created TEXT, UNIQUE (team_id, transcript_id));
    CREATE TABLE transcript_lines (
        transcript_seq INTEGER NOT NULL, n INTEGER NOT NULL, start REAL, speaker TEXT, text TEXT,
        PRIMARY KEY (transcript_seq, n));
    CREATE TABLE subscriptions (id TEXT PRIMARY KEY, team_id TEXT, data TEXT NOT NULL);
    CREATE TABLE inbound_events (
        source TEXT NOT NULL, event_id TEXT NOT NULL, seen_at REAL NOT NULL, PRIMARY KEY (source, event_id));
    CREATE TABLE runs (
        id TEXT PRIMARY KEY, team_id TEXT, trigger TEXT NOT NULL, requester TEXT, thread_id TEXT,
        status TEXT NOT NULL, started_at REAL NOT NULL, finished_at REAL, model_calls INTEGER NOT NULL DEFAULT 0,
        tokens INTEGER NOT NULL DEFAULT 0, cost_usd REAL NOT NULL DEFAULT 0, summary TEXT);
    CREATE INDEX runs_team ON runs (team_id, started_at);
    CREATE TABLE audit (
        seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, team_id TEXT, at REAL NOT NULL, kind TEXT NOT NULL,
        detail TEXT NOT NULL DEFAULT '{}');
    CREATE INDEX audit_run ON audit (run_id);
    CREATE TRIGGER audit_append_only BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;
    """,
    # 2 (step 4.2): action items as tasks, and the job runner's queue
    """
    CREATE TABLE tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, team_id TEXT NOT NULL, title TEXT NOT NULL, owner TEXT,
        owner_aad TEXT, due TEXT, status TEXT NOT NULL DEFAULT 'open', source_kind TEXT NOT NULL,
        source_ref TEXT, thread_root TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL,
        UNIQUE (team_id, source_ref, owner, title));
    CREATE INDEX tasks_team ON tasks (team_id, status);
    CREATE TABLE jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, team_id TEXT, kind TEXT NOT NULL, run_at REAL NOT NULL,
        payload TEXT NOT NULL DEFAULT '{}', status TEXT NOT NULL DEFAULT 'pending', locked_until REAL,
        attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT, dedupe_key TEXT UNIQUE, created_at REAL NOT NULL,
        done_at REAL);
    CREATE INDEX jobs_due ON jobs (status, run_at);
    """,
    # 3 (step 4.3): keyword search over the team's memory (SQLite FTS5, no embedding model)
    """
    CREATE VIRTUAL TABLE chunks USING fts5(
        team_id UNINDEXED, kind UNINDEXED, ref UNINDEXED, title, body, tokenize = 'porter unicode61');
    CREATE TABLE search_meta (team_id TEXT PRIMARY KEY, signature TEXT NOT NULL, built_at REAL NOT NULL);
    """,
    # 4 (step 4.4): approval requests. status: pending -> approved -> executing -> done | failed,
    # or pending -> cancelled | expired | superseded (a Change). Each step is claimed with a conditional UPDATE.
    """
    CREATE TABLE pending_actions (
        id TEXT PRIMARY KEY, team_id TEXT NOT NULL, run_id TEXT NOT NULL, tool TEXT NOT NULL, call_id TEXT NOT NULL,
        payload TEXT NOT NULL, payload_hash TEXT NOT NULL, preview TEXT NOT NULL, requester TEXT, requester_aad TEXT,
        thread_root TEXT, card_message_id TEXT, status TEXT NOT NULL DEFAULT 'pending',
        version INTEGER NOT NULL DEFAULT 1, graph_id TEXT, result TEXT, read_outside INTEGER NOT NULL DEFAULT 0,
        created_at REAL NOT NULL, expires_at REAL NOT NULL, decided_by TEXT, decided_at REAL, done_at REAL);
    CREATE INDEX pending_team ON pending_actions (team_id, status);
    """,
    # 5 (step 4.7): per-team policies (RBAC). who: everyone | owners | nobody; approvers: requester_or_owner | owners
    """
    CREATE TABLE policies (
        team_id TEXT NOT NULL, tag TEXT NOT NULL, who TEXT NOT NULL DEFAULT 'everyone',
        approvers TEXT NOT NULL DEFAULT 'requester_or_owner', updated_by TEXT, updated_at REAL,
        PRIMARY KEY (team_id, tag));
    """,
    # 6 (Phase 5.1): structured notes of each meeting Max attended (for "last time…" in the pre-meeting brief)
    """
    CREATE TABLE meeting_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, team_id TEXT NOT NULL, title TEXT NOT NULL, thread_root TEXT,
        join_url TEXT, held_at REAL NOT NULL, notes TEXT NOT NULL);
    CREATE INDEX meeting_notes_team ON meeting_notes (team_id, held_at);
    """,
]
POLICY_WHO = ("everyone", "owners", "nobody")
POLICY_APPROVERS = ("requester_or_owner", "owners")

STOPWORDS = set("""a an and are as at be been but by can could did do does for from had has have how i if in into is
it its me my of on or our over she so than that the their them then there these they this to us was we were what
when where which who whom why will with would you your about any did does max please tell know""".split())
FILE_CHUNK = 1200          # characters per file chunk
TRANSCRIPT_WINDOW = 12     # transcript lines per chunk

TEAM_COLUMNS = {"teamName": "name", "channelId": "channel_id", "driveId": "drive_id", "driveDelta": "drive_delta",
                "builtAt": "built_at", "timeZone": "time_zone"}
TEAM_JSON_COLUMNS = {"meetingAccess": "meeting_access", "announcedProblems": "announced_problems"}
TEAM_CONTENT_KEYS = {"teamId", "posts", "files", "meetings"}


class Store:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        for pragma in ("journal_mode=WAL", "busy_timeout=5000", "synchronous=NORMAL", "foreign_keys=ON"):
            self.db.execute(f"PRAGMA {pragma}")
        self._migrate()

    # ------------------------------------------------------------------ plumbing
    def _migrate(self) -> None:
        with self.lock:
            version = self.db.execute("PRAGMA user_version").fetchone()[0]
            for n, sql in enumerate(MIGRATIONS[version:], start=version + 1):
                self.db.executescript("BEGIN;\n" + sql + f"\nPRAGMA user_version = {n};\nCOMMIT;")

    @property
    def version(self) -> int:
        return self.db.execute("PRAGMA user_version").fetchone()[0]

    @contextmanager
    def tx(self):
        """One write transaction (BEGIN IMMEDIATE: takes the write lock at once, no deadlocks)."""
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield self.db
            except BaseException:
                self.db.execute("ROLLBACK")
                raise
            self.db.execute("COMMIT")

    def q(self, sql: str, args: tuple | dict = ()) -> list[sqlite3.Row]:
        with self.lock:
            return self.db.execute(sql, args).fetchall()

    def q1(self, sql: str, args: tuple | dict = ()) -> sqlite3.Row | None:
        with self.lock:
            return self.db.execute(sql, args).fetchone()

    def close(self) -> None:
        with self.lock:
            self.db.close()

    # ------------------------------------------------------------------ teams
    def team_ids(self) -> list[str]:
        return [r["team_id"] for r in self.q("SELECT team_id FROM teams ORDER BY team_id")]

    def team(self, team_id: str) -> dict | None:
        r = self.q1("SELECT * FROM teams WHERE team_id = ?", (team_id,))
        if r is None:
            return None
        out = {"teamId": r["team_id"], **json.loads(r["extra"] or "{}")}
        for key, col in TEAM_COLUMNS.items():
            out[key] = r[col]
        for key, col in TEAM_JSON_COLUMNS.items():
            out[key] = json.loads(r[col] or ("{}" if key == "meetingAccess" else "[]"))
        return out

    def save_team(self, data: dict) -> None:
        """Team-level fields of a knowledge dict (not posts/files/meetings)."""
        cols = {col: data.get(key) for key, col in TEAM_COLUMNS.items() if key in data}
        cols.update({col: json.dumps(data.get(key)) for key, col in TEAM_JSON_COLUMNS.items() if key in data})
        known = set(TEAM_COLUMNS) | set(TEAM_JSON_COLUMNS) | TEAM_CONTENT_KEYS
        cols["extra"] = json.dumps({k: v for k, v in data.items() if k not in known}, ensure_ascii=False)
        if cols.get("time_zone") is None:
            cols.pop("time_zone", None)
        names = ", ".join(cols)
        marks = ", ".join(f":{c}" for c in cols)
        updates = ", ".join(f"{c} = excluded.{c}" for c in cols)
        with self.tx() as db:
            db.execute(f"INSERT INTO teams (team_id, {names}) VALUES (:team_id, {marks}) "
                       f"ON CONFLICT (team_id) DO UPDATE SET {updates}", {"team_id": data["teamId"], **cols})

    def delete_team(self, team_id: str) -> None:
        """Removed from a team: forget everything about it (content, people, runs, audit, refs, subscriptions)."""
        with self.tx() as db:
            db.execute("DELETE FROM transcript_lines WHERE transcript_seq IN "
                       "(SELECT seq FROM transcripts WHERE team_id = ?)", (team_id,))
            for table in ("transcripts", "meetings", "messages", "files", "people", "runs", "audit",
                          "conversation_refs", "subscriptions", "tasks", "jobs", "chunks", "search_meta",
                          "pending_actions", "policies", "meeting_notes", "teams"):
                db.execute(f"DELETE FROM {table} WHERE team_id = ?", (team_id,))

    # ------------------------------------------------------------------ whole team content (build / import)
    def replace_team_content(self, data: dict) -> None:
        """Write a full knowledge dict (after a full Graph read, or a JSON import) in one transaction."""
        team_id = data["teamId"]
        with self.tx() as db:
            db.execute("DELETE FROM transcript_lines WHERE transcript_seq IN "
                       "(SELECT seq FROM transcripts WHERE team_id = ?)", (team_id,))
            for table in ("transcripts", "meetings", "messages", "files"):
                db.execute(f"DELETE FROM {table} WHERE team_id = ?", (team_id,))
            for p in data.get("posts", []):
                self._insert_message(db, team_id, p, None)
                for r in p.get("replies", []):
                    self._insert_message(db, team_id, r, p["id"])
            for f in data.get("files", []):
                self._upsert_file(db, team_id, f)
            for m in data.get("meetings", []):
                self._insert_meeting(db, team_id, m)
        self.save_team(data)

    # ------------------------------------------------------------------ messages
    def _insert_message(self, db, team_id: str, m: dict, root_id: str | None) -> bool:
        cur = db.execute(
            "INSERT OR IGNORE INTO messages (team_id, id, root_id, author, author_id, time, text, attachments, edited) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (team_id, m["id"], root_id, m.get("author"), m.get("authorId"), m.get("time"), m.get("text") or "",
             json.dumps(m.get("attachments") or []), int(bool(m.get("edited")))))
        if m.get("author"):
            self._touch_person(db, team_id, m["author"], m.get("authorId"), m.get("authorKind"))
        return cur.rowcount == 1

    def add_message(self, team_id: str, m: dict, root_id: str | None) -> bool:
        with self.tx() as db:
            return self._insert_message(db, team_id, m, root_id)

    def update_message(self, team_id: str, msg_id: str, text: str) -> bool:
        with self.tx() as db:
            return db.execute("UPDATE messages SET text = ?, edited = 1 WHERE team_id = ? AND id = ? "
                              "AND deleted_at IS NULL", (text, team_id, msg_id)).rowcount == 1

    def delete_message(self, team_id: str, msg_id: str) -> bool:
        """Soft delete: the row stays (so the id is known) but the text is wiped; a post takes its replies along."""
        now = time.time()
        with self.tx() as db:
            n = db.execute("UPDATE messages SET text = '', attachments = '[]', deleted_at = ? "
                           "WHERE team_id = ? AND id = ? AND deleted_at IS NULL", (now, team_id, msg_id)).rowcount
            db.execute("UPDATE messages SET text = '', attachments = '[]', deleted_at = ? "
                       "WHERE team_id = ? AND root_id = ? AND deleted_at IS NULL", (now, team_id, msg_id))
            return n == 1

    def messages(self, team_id: str) -> list[sqlite3.Row]:
        return self.q("SELECT * FROM messages WHERE team_id = ? AND deleted_at IS NULL ORDER BY seq", (team_id,))

    # ------------------------------------------------------------------ files
    def _upsert_file(self, db, team_id: str, f: dict) -> None:
        db.execute("INSERT INTO files (team_id, id, name, author, time, text) VALUES (?, ?, ?, ?, ?, ?) "
                   "ON CONFLICT (team_id, id) DO UPDATE SET name = excluded.name, author = excluded.author, "
                   "time = excluded.time, text = excluded.text",
                   (team_id, f["id"], f["name"], f.get("author"), f.get("time"), f.get("text") or ""))

    def upsert_file(self, team_id: str, f: dict, replaces_id: str | None = None) -> None:
        with self.tx() as db:
            if replaces_id and replaces_id != f["id"]:
                db.execute("DELETE FROM files WHERE team_id = ? AND id = ?", (team_id, replaces_id))
            self._upsert_file(db, team_id, f)

    def remove_file(self, team_id: str, file_id: str) -> None:
        with self.tx() as db:
            db.execute("DELETE FROM files WHERE team_id = ? AND id = ?", (team_id, file_id))

    def files(self, team_id: str) -> list[sqlite3.Row]:
        return self.q("SELECT * FROM files WHERE team_id = ? ORDER BY seq", (team_id,))

    # ------------------------------------------------------------------ meetings + transcripts
    @staticmethod
    def _meeting_json(m: dict) -> str:
        return json.dumps({k: v for k, v in m.items() if k != "transcripts" and not k.startswith("_")},
                          ensure_ascii=False)

    def _insert_meeting(self, db, team_id: str, m: dict) -> int:
        seq = db.execute("INSERT INTO meetings (team_id, online_meeting_id, data) VALUES (?, ?, ?)",
                         (team_id, m.get("onlineMeetingId"), self._meeting_json(m))).lastrowid
        m["_seq"] = seq
        for t in m.get("transcripts") or []:
            self._insert_transcript(db, team_id, seq, t)
        return seq

    def _insert_transcript(self, db, team_id: str, meeting_seq: int, t: dict) -> None:
        cur = db.execute("INSERT OR IGNORE INTO transcripts (team_id, meeting_seq, transcript_id, created) "
                         "VALUES (?, ?, ?, ?)", (team_id, meeting_seq, t["id"], t.get("created")))
        if cur.rowcount != 1:
            return
        db.executemany("INSERT INTO transcript_lines (transcript_seq, n, start, speaker, text) VALUES (?, ?, ?, ?, ?)",
                       [(cur.lastrowid, n, c.get("start"), c.get("speaker"), c.get("text"))
                        for n, c in enumerate(t.get("cues") or [])])

    def replace_meetings(self, team_id: str, meetings: list[dict], access: dict) -> None:
        with self.tx() as db:
            db.execute("DELETE FROM transcript_lines WHERE transcript_seq IN "
                       "(SELECT seq FROM transcripts WHERE team_id = ?)", (team_id,))
            db.execute("DELETE FROM transcripts WHERE team_id = ?", (team_id,))
            db.execute("DELETE FROM meetings WHERE team_id = ?", (team_id,))
            for m in meetings:
                self._insert_meeting(db, team_id, m)
            db.execute("UPDATE teams SET meeting_access = ? WHERE team_id = ?", (json.dumps(access), team_id))

    def add_meeting(self, team_id: str, m: dict) -> int:
        with self.tx() as db:
            return self._insert_meeting(db, team_id, m)

    def update_meeting(self, team_id: str, m: dict) -> None:
        with self.tx() as db:
            db.execute("UPDATE meetings SET data = ?, online_meeting_id = ? WHERE seq = ? AND team_id = ?",
                       (self._meeting_json(m), m.get("onlineMeetingId"), m["_seq"], team_id))

    def add_transcript(self, team_id: str, meeting_seq: int, t: dict) -> None:
        with self.tx() as db:
            self._insert_transcript(db, team_id, meeting_seq, t)

    def meetings(self, team_id: str) -> list[dict]:
        out = []
        for r in self.q("SELECT * FROM meetings WHERE team_id = ? ORDER BY seq", (team_id,)):
            m = json.loads(r["data"])
            m["_seq"] = r["seq"]
            m["transcripts"] = []
            for t in self.q("SELECT * FROM transcripts WHERE meeting_seq = ? ORDER BY seq", (r["seq"],)):
                cues = [{"start": c["start"], "speaker": c["speaker"], "text": c["text"]}
                        for c in self.q("SELECT * FROM transcript_lines WHERE transcript_seq = ? ORDER BY n",
                                        (t["seq"],))]
                m["transcripts"].append({"id": t["transcript_id"], "created": t["created"], "cues": cues})
            out.append(m)
        return out

    # ------------------------------------------------------------------ people
    def _touch_person(self, db, team_id: str, name: str, aad_id: str | None = None, kind: str | None = None) -> None:
        kind = kind or ("max" if name.lower() in ("max", "max (ai)") else "person")
        db.execute("INSERT INTO people (team_id, name, aad_id, kind, first_seen) VALUES (?, ?, ?, ?, ?) "
                   "ON CONFLICT (team_id, name) DO UPDATE SET aad_id = COALESCE(excluded.aad_id, people.aad_id)",
                   (team_id, name, aad_id, kind, time.time()))

    def touch_person(self, team_id: str, name: str, aad_id: str | None = None, kind: str | None = None,
                     email: str | None = None, role: str | None = None) -> None:
        with self.tx() as db:
            self._touch_person(db, team_id, name, aad_id, kind)
            if email or role:
                db.execute("UPDATE people SET email = COALESCE(?, email), role = COALESCE(?, role) "
                           "WHERE team_id = ? AND name = ?", (email, role, team_id, name))

    def people(self, team_id: str) -> list[sqlite3.Row]:
        return self.q("SELECT * FROM people WHERE team_id = ? ORDER BY name", (team_id,))

    # ------------------------------------------------------------------ conversation refs
    def save_ref(self, team_id: str, channel_id: str, service_url: str) -> None:
        with self.tx() as db:
            db.execute("INSERT INTO conversation_refs VALUES (?, ?, ?, ?) ON CONFLICT (team_id) DO UPDATE SET "
                       "channel_id = excluded.channel_id, service_url = excluded.service_url, "
                       "updated_at = excluded.updated_at", (team_id, channel_id, service_url, time.time()))

    def refs(self) -> dict[str, dict]:
        return {r["team_id"]: {"channelId": r["channel_id"], "serviceUrl": r["service_url"]}
                for r in self.q("SELECT * FROM conversation_refs")}

    def delete_ref(self, team_id: str) -> None:
        with self.tx() as db:
            db.execute("DELETE FROM conversation_refs WHERE team_id = ?", (team_id,))

    # ------------------------------------------------------------------ subscriptions
    def subscriptions(self) -> dict[str, dict]:
        return {r["id"]: json.loads(r["data"]) for r in self.q("SELECT * FROM subscriptions")}

    def save_subscriptions(self, subs: dict[str, dict]) -> None:
        with self.tx() as db:
            db.execute("DELETE FROM subscriptions")
            db.executemany("INSERT INTO subscriptions (id, team_id, data) VALUES (?, ?, ?)",
                           [(s["id"], s.get("teamId"), json.dumps(s)) for s in subs.values()])

    # ------------------------------------------------------------------ inbound gate
    def first_seen(self, source: str, event_id: str) -> bool:
        """True the first time (source, event_id) is seen, False for every repeat."""
        with self.tx() as db:
            return db.execute("INSERT OR IGNORE INTO inbound_events VALUES (?, ?, ?)",
                              (source, event_id, time.time())).rowcount == 1

    def prune_inbound(self, older_than_s: float = 7 * 86400) -> int:
        with self.tx() as db:
            return db.execute("DELETE FROM inbound_events WHERE seen_at < ?", (time.time() - older_than_s,)).rowcount

    # ------------------------------------------------------------------ runs + audit
    def start_run(self, team_id: str | None, trigger: str, requester: str | None = None,
                  thread_id: str | None = None) -> str:
        run_id = uuid.uuid4().hex
        with self.tx() as db:
            db.execute("INSERT INTO runs (id, team_id, trigger, requester, thread_id, status, started_at) "
                       "VALUES (?, ?, ?, ?, ?, 'running', ?)", (run_id, team_id, trigger, requester, thread_id, time.time()))
        return run_id

    def finish_run(self, run_id: str, status: str, summary: str = "", model_calls: int = 0, tokens: int = 0,
                   cost_usd: float = 0.0) -> None:
        with self.tx() as db:
            db.execute("UPDATE runs SET status = ?, finished_at = ?, summary = ?, model_calls = model_calls + ?, "
                       "tokens = tokens + ?, cost_usd = cost_usd + ? WHERE id = ?",
                       (status, time.time(), summary[:500], model_calls, tokens, cost_usd, run_id))

    def audit(self, run_id: str | None, team_id: str | None, kind: str, detail: dict | None = None) -> None:
        with self.tx() as db:
            db.execute("INSERT INTO audit (run_id, team_id, at, kind, detail) VALUES (?, ?, ?, ?, ?)",
                       (run_id, team_id, time.time(), kind, json.dumps(detail or {}, ensure_ascii=False, default=str)))

    def runs(self, team_id: str | None = None, limit: int = 50) -> list[sqlite3.Row]:
        if team_id:
            return self.q("SELECT * FROM runs WHERE team_id = ? ORDER BY started_at DESC LIMIT ?", (team_id, limit))
        return self.q("SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,))

    def audit_for(self, run_id: str) -> list[sqlite3.Row]:
        return self.q("SELECT * FROM audit WHERE run_id = ? ORDER BY seq", (run_id,))

    # ------------------------------------------------------------------ tasks (step 4.2)
    # ------------------------------------------------------------------ meeting notes (Phase 5.1)
    def add_meeting_notes(self, team_id: str, title: str, thread_root: str | None, join_url: str | None,
                          held_at: float, notes: dict) -> int:
        with self.tx() as db:
            return db.execute("INSERT INTO meeting_notes (team_id, title, thread_root, join_url, held_at, notes) "
                              "VALUES (?, ?, ?, ?, ?, ?)", (team_id, title, thread_root, join_url, held_at,
                                                             json.dumps(notes))).lastrowid

    def previous_meeting_notes(self, team_id: str, before: float, join_url: str | None = None,
                               thread_root: str | None = None, title: str | None = None) -> dict | None:
        """Notes of the meeting this one follows on from: the same Teams meeting (series), else the same thread,
        else the same title (ignoring 'Follow-up:'). None if nothing matches: never someone else's meeting."""
        rows = self.q("SELECT * FROM meeting_notes WHERE team_id = ? AND held_at < ? ORDER BY held_at DESC, id DESC",
                      (team_id, before))
        base = lambda t: re.sub(r"^\s*(?:re|follow[- ]?up|fu)\s*:\s*", "", t or "", flags=re.I).strip().lower()  # noqa: E731
        for match in (lambda r: join_url and r["join_url"] == join_url,
                      lambda r: thread_root and r["thread_root"] == thread_root,
                      lambda r: title and base(r["title"]) == base(title)):
            for r in rows:
                if match(r):
                    return {**dict(r), "notes": json.loads(r["notes"])}
        return None

    def add_task(self, team_id: str, title: str, owner: str | None, due: str | None, source_kind: str,
                 source_ref: str | None, thread_root: str | None, owner_aad: str | None = None) -> int | None:
        """Returns the new task id, or None if the same task from the same source already exists."""
        now = time.time()
        with self.tx() as db:
            cur = db.execute("INSERT OR IGNORE INTO tasks (team_id, title, owner, owner_aad, due, source_kind, "
                             "source_ref, thread_root, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                             (team_id, title, owner, owner_aad, due, source_kind, source_ref, thread_root, now, now))
            return cur.lastrowid if cur.rowcount == 1 else None

    def task(self, task_id: int) -> sqlite3.Row | None:
        return self.q1("SELECT * FROM tasks WHERE id = ?", (task_id,))

    def tasks(self, team_id: str, status: str | None = "open", owner: str | None = None) -> list[sqlite3.Row]:
        sql, args = "SELECT * FROM tasks WHERE team_id = ?", [team_id]
        if status:
            sql += " AND status = ?"
            args.append(status)
        if owner:
            sql += " AND owner = ?"
            args.append(owner)
        return self.q(sql + " ORDER BY COALESCE(due, '9999'), id", tuple(args))

    def update_task(self, task_id: int, **fields) -> bool:
        allowed = {k: v for k, v in fields.items() if k in ("title", "owner", "owner_aad", "due", "status")}
        if not allowed:
            return False
        sets = ", ".join(f"{k} = :{k}" for k in allowed)
        with self.tx() as db:
            return db.execute(f"UPDATE tasks SET {sets}, updated_at = :now WHERE id = :id",
                              {**allowed, "now": time.time(), "id": task_id}).rowcount == 1

    # ------------------------------------------------------------------ jobs (step 4.2)
    def add_job(self, team_id: str | None, kind: str, run_at: float, payload: dict | None = None,
                dedupe_key: str | None = None) -> int | None:
        """Schedule work. With a dedupe_key the same job is only ever scheduled once (returns None then)."""
        with self.tx() as db:
            cur = db.execute("INSERT OR IGNORE INTO jobs (team_id, kind, run_at, payload, dedupe_key, created_at) "
                             "VALUES (?, ?, ?, ?, ?, ?)",
                             (team_id, kind, run_at, json.dumps(payload or {}), dedupe_key, time.time()))
            return cur.lastrowid if cur.rowcount == 1 else None

    def claim_jobs(self, now: float, lock_s: float = 120, limit: int = 20) -> list[sqlite3.Row]:
        """Atomically take due jobs: pending ones whose time has come. Each job is handed out once."""
        with self.tx() as db:
            return db.execute("UPDATE jobs SET status = 'running', locked_until = ?, attempts = attempts + 1 "
                              "WHERE id IN (SELECT id FROM jobs WHERE status = 'pending' AND run_at <= ? "
                              "ORDER BY run_at LIMIT ?) RETURNING *", (now + lock_s, now, limit)).fetchall()

    def stale_running_jobs(self, now: float) -> list[sqlite3.Row]:
        """Jobs whose lock ran out while 'running' (Max stopped in the middle)."""
        return self.q("SELECT * FROM jobs WHERE status = 'running' AND locked_until < ?", (now,))

    def finish_job(self, job_id: int, status: str, error: str | None = None, retry_at: float | None = None) -> None:
        with self.tx() as db:
            if retry_at is not None:
                db.execute("UPDATE jobs SET status = 'pending', run_at = ?, locked_until = NULL, last_error = ? "
                           "WHERE id = ?", (retry_at, error, job_id))
            else:
                db.execute("UPDATE jobs SET status = ?, last_error = ?, done_at = ?, locked_until = NULL "
                           "WHERE id = ?", (status, error, time.time(), job_id))

    def cancel_jobs(self, dedupe_prefix: str) -> int:
        """Cancel pending jobs whose dedupe key starts with a prefix (e.g. a task that was closed)."""
        with self.tx() as db:
            return db.execute("UPDATE jobs SET status = 'cancelled', done_at = ? WHERE status = 'pending' "
                              "AND dedupe_key LIKE ?", (time.time(), dedupe_prefix + "%")).rowcount

    def jobs(self, team_id: str | None = None, status: str | None = None) -> list[sqlite3.Row]:
        sql, args = "SELECT * FROM jobs WHERE 1 = 1", []
        if team_id:
            sql += " AND team_id = ?"
            args.append(team_id)
        if status:
            sql += " AND status = ?"
            args.append(status)
        return self.q(sql + " ORDER BY run_at", tuple(args))

    def person(self, team_id: str, name: str) -> sqlite3.Row | None:
        r = self.q1("SELECT * FROM people WHERE team_id = ? AND name = ?", (team_id, name))
        if r is None:   # "Prince" -> "Prince Alex"
            r = self.q1("SELECT * FROM people WHERE team_id = ? AND kind = 'person' AND name LIKE ? ORDER BY name",
                        (team_id, name.strip() + " %"))
        return r

    # ------------------------------------------------------------------ search (step 4.3)
    def _content_signature(self, team_id: str) -> str:
        m = self.q1("SELECT COALESCE(MAX(seq),0), COUNT(*), COALESCE(SUM(LENGTH(text)),0), "
                    "SUM(deleted_at IS NOT NULL) FROM messages WHERE team_id = ?", (team_id,))
        f = self.q1("SELECT COALESCE(MAX(seq),0), COUNT(*), COALESCE(SUM(LENGTH(text)),0), "
                    "COALESCE(SUM(LENGTH(name)),0) FROM files WHERE team_id = ?", (team_id,))
        t = self.q1("SELECT COUNT(*), COALESCE(MAX(seq),0) FROM transcripts WHERE team_id = ?", (team_id,))
        mt = self.q1("SELECT COUNT(*), COALESCE(MAX(seq),0) FROM meetings WHERE team_id = ?", (team_id,))
        return "|".join(str(x) for x in (*m, *f, *t, *mt))

    @staticmethod
    def _split_text(text: str, size: int = FILE_CHUNK) -> list[str]:
        """Split at paragraph / line boundaries into pieces of about `size` characters."""
        out, cur = [], ""
        for para in text.replace("\r", "").split("\n"):
            if len(cur) + len(para) + 1 > size and cur:
                out.append(cur)
                cur = ""
            while len(para) > size:
                out.append(para[:size])
                para = para[size:]
            cur = f"{cur}\n{para}" if cur else para
        if cur.strip():
            out.append(cur)
        return out

    def rebuild_search(self, team_id: str) -> int:
        """(Re)build the team's search chunks: posts, replies, file sections, transcript windows, meetings."""
        rows = []
        msgs = self.messages(team_id)
        roots = {m["id"]: m for m in msgs if not m["root_id"]}
        for m in msgs:
            if not (m["text"] or "").strip():
                continue
            if m["root_id"] and m["root_id"] in roots:
                title = f"reply by {m['author']} {m['time']} (thread: {roots[m['root_id']]['text'][:70]})"
                rows.append((team_id, "reply", m["id"], title, m["text"]))
            else:
                rows.append((team_id, "post", m["id"], f"post by {m['author']} {m['time']}", m["text"]))
        for f in self.files(team_id):
            for n, part in enumerate(self._split_text(f["text"] or "")):
                rows.append((team_id, "file", f"{f['id']}#{n}", f"file {f['name']} (by {f['author']}, {f['time']})",
                             part))
        for m in self.meetings(team_id):
            head = f"meeting '{m.get('subject')}' {m.get('start')}"
            rows.append((team_id, "meeting", f"{m['_seq']}", head,
                         f"{head} to {m.get('end')}, organizer {m.get('organizer')}"))
            for t in m.get("transcripts") or []:
                cues = t.get("cues") or []
                for n in range(0, len(cues), TRANSCRIPT_WINDOW):
                    body = "\n".join(f"{c['speaker']}: {c['text']}" for c in cues[n:n + TRANSCRIPT_WINDOW])
                    rows.append((team_id, "transcript", f"{m['_seq']}#{n}", f"{head} official transcript", body))
        sig = self._content_signature(team_id)
        with self.tx() as db:
            db.execute("DELETE FROM chunks WHERE team_id = ?", (team_id,))
            db.executemany("INSERT INTO chunks (team_id, kind, ref, title, body) VALUES (?, ?, ?, ?, ?)", rows)
            db.execute("INSERT INTO search_meta VALUES (?, ?, ?) ON CONFLICT (team_id) DO UPDATE SET "
                       "signature = excluded.signature, built_at = excluded.built_at", (team_id, sig, time.time()))
        return len(rows)

    @staticmethod
    def match_query(query: str) -> str:
        """User words -> a safe FTS5 query: each word quoted (no operators can leak in), OR-ed."""
        import re as _re
        words = [w.strip("-.%") for w in _re.findall(r"[\w][\w\-.%]*", query.lower())]
        words = [w for w in dict.fromkeys(words) if w and w not in STOPWORDS and len(w) > 1 or w.isdigit()]
        return " OR ".join('"' + w.replace('"', "") + '"' for w in words[:24])

    def search(self, team_id: str, query: str, limit: int = 8, kinds: tuple[str, ...] | None = None) -> list[dict]:
        meta = self.q1("SELECT signature FROM search_meta WHERE team_id = ?", (team_id,))
        if meta is None or meta["signature"] != self._content_signature(team_id):
            self.rebuild_search(team_id)
        fts = self.match_query(query)
        if not fts:
            return []
        sql = ("SELECT kind, ref, title, body, bm25(chunks, 0, 0, 0, 2.0, 1.0) AS score FROM chunks "
               "WHERE chunks MATCH ? AND team_id = ?")
        args: list = [fts, team_id]
        if kinds:
            sql += f" AND kind IN ({','.join('?' * len(kinds))})"
            args += list(kinds)
        try:
            rows = self.q(sql + " ORDER BY score LIMIT ?", tuple(args + [limit]))
        except sqlite3.OperationalError:
            return []
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ approvals (step 4.4)
    def add_pending(self, row: dict) -> None:
        cols = ", ".join(row)
        with self.tx() as db:
            db.execute(f"INSERT INTO pending_actions ({cols}) VALUES ({', '.join(':' + c for c in row)})", row)

    def pending(self, pending_id: str) -> sqlite3.Row | None:
        return self.q1("SELECT * FROM pending_actions WHERE id = ?", (pending_id,))

    def claim_pending(self, pending_id: str, from_status: str, to_status: str, by: str | None = None,
                      now: float | None = None) -> bool:
        """Move one approval from one status to the next. Only one caller can win (double clicks, retries)."""
        with self.tx() as db:
            return db.execute("UPDATE pending_actions SET status = ?, decided_by = COALESCE(?, decided_by), "
                              "decided_at = COALESCE(?, decided_at) WHERE id = ? AND status = ?",
                              (to_status, by, now if by else None, pending_id, from_status)).rowcount == 1

    def set_pending(self, pending_id: str, **fields) -> None:
        allowed = {k: v for k, v in fields.items() if k in ("card_message_id", "graph_id", "result", "done_at",
                                                              "status", "version")}
        if allowed:
            with self.tx() as db:
                db.execute(f"UPDATE pending_actions SET {', '.join(f'{k} = :{k}' for k in allowed)} WHERE id = :id",
                           {**allowed, "id": pending_id})

    def pendings(self, team_id: str | None = None, status: str | None = None) -> list[sqlite3.Row]:
        sql, args = "SELECT * FROM pending_actions WHERE 1 = 1", []
        if team_id:
            sql += " AND team_id = ?"
            args.append(team_id)
        if status:
            sql += " AND status = ?"
            args.append(status)
        return self.q(sql + " ORDER BY created_at, rowid", tuple(args))

    # ------------------------------------------------------------------ policies / RBAC (step 4.7)
    def policy(self, team_id: str, tag: str) -> dict:
        r = self.q1("SELECT * FROM policies WHERE team_id = ? AND tag = ?", (team_id, tag))
        return {"tag": tag, "who": r["who"] if r else "everyone",
                "approvers": r["approvers"] if r else "requester_or_owner",
                "updatedBy": r["updated_by"] if r else None}

    def set_policy(self, team_id: str, tag: str, who: str | None = None, approvers: str | None = None,
                   by: str | None = None) -> dict:
        cur = self.policy(team_id, tag)
        who = who or cur["who"]
        approvers = approvers or cur["approvers"]
        if who not in POLICY_WHO or approvers not in POLICY_APPROVERS:
            raise ValueError(f"who must be one of {POLICY_WHO}, approvers one of {POLICY_APPROVERS}")
        with self.tx() as db:
            db.execute("INSERT INTO policies VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (team_id, tag) DO UPDATE SET "
                       "who = excluded.who, approvers = excluded.approvers, updated_by = excluded.updated_by, "
                       "updated_at = excluded.updated_at", (team_id, tag, who, approvers, by, time.time()))
        self.audit(None, team_id, "policy-changed", {"tag": tag, "who": who, "approvers": approvers, "by": by})
        return self.policy(team_id, tag)

    def is_owner(self, team_id: str, aad_id: str | None) -> bool:
        return bool(aad_id) and self.q1("SELECT 1 FROM people WHERE team_id = ? AND aad_id = ? AND role = 'owner'",
                                        (team_id, aad_id)) is not None

    def owners(self, team_id: str) -> list[sqlite3.Row]:
        return self.q("SELECT * FROM people WHERE team_id = ? AND role = 'owner'", (team_id,))

    def set_team_time_zone(self, team_id: str, tz: str) -> None:
        with self.tx() as db:
            db.execute("UPDATE teams SET time_zone = ? WHERE team_id = ?", (tz, team_id))
