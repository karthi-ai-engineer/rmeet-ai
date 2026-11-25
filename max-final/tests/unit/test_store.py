"""Database: creates from empty, upgrades safely, raw items are never duplicated."""

import sqlite3

import pytest

from max.store import connect, content_hash, latest_raw, migrate, put_raw, schema_version
from max.store.db import MIGRATIONS


def test_creates_from_empty(tmp_path):
    conn = connect(tmp_path / "sub" / "max.db")
    assert schema_version(conn) == len(MIGRATIONS)
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_migrate_is_safe_to_rerun(tmp_path):
    path = tmp_path / "max.db"
    connect(path).close()
    conn = connect(path)
    assert migrate(conn) == len(MIGRATIONS)


def test_refuses_newer_schema(tmp_path):
    path = tmp_path / "max.db"
    conn = connect(path)
    conn.execute(f"PRAGMA user_version = {len(MIGRATIONS) + 1}")
    conn.close()
    with pytest.raises(RuntimeError):
        connect(path)


def test_same_raw_item_twice_is_stored_once(tmp_path):
    conn = connect(tmp_path / "max.db")
    msg = {"id": "m1", "body": {"content": "hello"}, "from": {"user": {"displayName": "Karthi"}}}
    assert put_raw(conn, "message", "m1", msg) is True
    assert put_raw(conn, "message", "m1", dict(reversed(list(msg.items())))) is False   # key order doesn't matter
    assert conn.execute("SELECT COUNT(*) FROM raw_items").fetchone()[0] == 1


def test_edit_and_delete_add_new_versions(tmp_path):
    conn = connect(tmp_path / "max.db")
    put_raw(conn, "message", "m1", {"id": "m1", "body": "v1"})
    put_raw(conn, "message", "m1", {"id": "m1", "body": "v2"})
    put_raw(conn, "message", "m1", {"id": "m1", "deletedDateTime": "2026-11-25T10:00:00Z"}, deleted=True)
    assert conn.execute("SELECT COUNT(*) FROM raw_items WHERE item_id='m1'").fetchone()[0] == 3
    latest = latest_raw(conn, "message", "m1")
    assert latest["deleted"] is True and "deletedDateTime" in latest["payload"]
    assert latest_raw(conn, "message", "nope") is None


def test_unicode_survives(tmp_path):
    conn = connect(tmp_path / "max.db")
    put_raw(conn, "message", "jp", {"text": "会議は明日です 🎉"})
    assert latest_raw(conn, "message", "jp")["payload"]["text"] == "会議は明日です 🎉"


def test_requires_kind_and_id(tmp_path):
    conn = connect(tmp_path / "max.db")
    with pytest.raises(ValueError):
        put_raw(conn, "", "x", {})


def test_hash_is_stable():
    assert content_hash({"a": 1, "b": 2}) == content_hash({"b": 2, "a": 1})


def test_failed_migration_keeps_old_version(tmp_path, monkeypatch):
    path = tmp_path / "max.db"
    connect(path).close()
    # second statement fails after the first one already ran: the whole step must be undone
    monkeypatch.setattr("max.store.db.MIGRATIONS", MIGRATIONS + [["CREATE TABLE half_done (x)", "CREATE TABLE broken (;"]])
    with pytest.raises(sqlite3.Error):
        connect(path)
    conn = sqlite3.connect(path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)
    assert conn.execute("SELECT name FROM sqlite_master WHERE name = 'half_done'").fetchone() is None


def test_delete_with_same_payload_is_kept(tmp_path):
    conn = connect(tmp_path / "max.db")
    msg = {"id": "m1", "body": "hello"}
    assert put_raw(conn, "message", "m1", msg) is True
    assert put_raw(conn, "message", "m1", msg, deleted=True) is True
    assert latest_raw(conn, "message", "m1")["deleted"] is True


def test_edit_back_to_old_text_is_kept(tmp_path):
    conn = connect(tmp_path / "max.db")
    for body in ("A", "B", "A"):
        assert put_raw(conn, "message", "m1", {"id": "m1", "body": body}) is True
    assert latest_raw(conn, "message", "m1")["payload"]["body"] == "A"
    assert put_raw(conn, "message", "m1", {"id": "m1", "body": "A"}) is False   # repeat of the latest: skipped


def test_two_programs_create_the_database_at_once(tmp_path):
    import threading
    path, errors, start = tmp_path / "max.db", [], threading.Barrier(4)

    def open_db():
        try:
            start.wait()
            connect(path).close()
        except Exception as e:  # noqa: BLE001 - collected for the assert
            errors.append(repr(e))

    threads = [threading.Thread(target=open_db) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert schema_version(connect(path)) == len(MIGRATIONS)
