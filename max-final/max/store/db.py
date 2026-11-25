"""
Max's database: one SQLite file (data/max.db). All SQL lives in this package; plain SQL, no ORM.

Groups (docs/decisions.md section 4):
  Raw      exact data as received from Teams/Graph, only ever added to   (raw_items)
  Working  clean tables + search, rebuildable from Raw                   (Step 2)
  App      Max's own tasks, approvals, audit                             (later steps)

  conn = connect(path)                       opens and upgrades the schema
  put_raw(conn, kind, item_id, payload)      True if stored, False if it equals the item's latest version
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

# Each entry upgrades the schema by one version: a list of SQL statements.
# Never edit an entry once it is committed: add a new one.
MIGRATIONS: list[list[str]] = [
    # 1: raw layer
    [
        """CREATE TABLE raw_items (
            seq          INTEGER PRIMARY KEY AUTOINCREMENT,   -- arrival order
            kind         TEXT NOT NULL,                       -- message, reply, file, meeting, transcript, ...
            item_id      TEXT NOT NULL,                       -- id given by Microsoft
            content_hash TEXT NOT NULL,                       -- sha256 of payload + deleted flag
            payload      TEXT NOT NULL,                       -- exact JSON as received
            deleted      INTEGER NOT NULL DEFAULT 0,          -- 1 = this version says the item was deleted
            source       TEXT NOT NULL,                       -- graph, bot, sim, ...
            received_at  TEXT NOT NULL                        -- UTC, ISO 8601
        )""",
        "CREATE INDEX raw_items_by_item ON raw_items (kind, item_id, seq)",
    ],
]


def schema_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrate(conn: sqlite3.Connection) -> int:
    """Bring the schema up to date. Safe to run any number of times, and from several processes at once:
    each step runs inside a write lock and re-checks the version first."""
    target = len(MIGRATIONS)
    while True:
        conn.execute("BEGIN IMMEDIATE")  # write lock: a second process waits here (busy_timeout)
        try:
            current = schema_version(conn)
            if current > target:
                raise RuntimeError(f"database schema v{current} is newer than this code (v{target})")
            if current == target:
                conn.execute("COMMIT")
                return current
            for statement in MIGRATIONS[current]:
                conn.execute(statement)
            conn.execute(f"PRAGMA user_version = {current + 1}")
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")  # a failed step leaves the old version intact
            raise


def connect(path: Path | str) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)  # autocommit; transactions are explicit
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    _set_wal(conn)
    conn.execute("PRAGMA foreign_keys = ON")
    migrate(conn)
    return conn


def _set_wal(conn: sqlite3.Connection, tries: int = 100) -> None:
    """Switch to WAL (readers don't block the writer). SQLite skips the busy wait for this one step when
    several programs open a brand-new file at once, so retry briefly ourselves."""
    for attempt in range(tries):
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            return
        except sqlite3.OperationalError as e:
            if "locked" not in str(e) or attempt == tries - 1:
                raise
            time.sleep(0.05)


def content_hash(payload: dict, deleted: bool = False) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(f"{int(deleted)}|{canonical}".encode("utf-8")).hexdigest()


def put_raw(conn: sqlite3.Connection, kind: str, item_id: str, payload: dict, *, source: str = "graph",
            deleted: bool = False) -> bool:
    """Store a new version of an item. Skipped (returns False) only if it equals the item's LATEST version,
    so repeats are ignored but deletes and edits back to an older text are always kept."""
    if not kind or not item_id:
        raise ValueError("kind and item_id are required")
    digest = content_hash(payload, deleted)
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute("SELECT content_hash FROM raw_items WHERE kind = ? AND item_id = ?"
                           " ORDER BY seq DESC LIMIT 1", (kind, item_id)).fetchone()
        if row is not None and row["content_hash"] == digest:
            conn.execute("COMMIT")
            return False
        conn.execute(
            "INSERT INTO raw_items (kind, item_id, content_hash, payload, deleted, source, received_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (kind, item_id, digest, json.dumps(payload, ensure_ascii=False), int(deleted), source,
             datetime.now(timezone.utc).isoformat(timespec="milliseconds")))
        conn.execute("COMMIT")
        return True
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def latest_raw(conn: sqlite3.Connection, kind: str, item_id: str) -> dict | None:
    """The newest stored version of an item: {'payload', 'deleted', 'received_at'}, or None."""
    row = conn.execute("SELECT payload, deleted, received_at FROM raw_items WHERE kind = ? AND item_id = ?"
                       " ORDER BY seq DESC LIMIT 1", (kind, item_id)).fetchone()
    if row is None:
        return None
    return {"payload": json.loads(row["payload"]), "deleted": bool(row["deleted"]),
            "received_at": row["received_at"]}
