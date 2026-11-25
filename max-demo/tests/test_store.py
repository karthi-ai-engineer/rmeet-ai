"""
Step 4.1 offline tests for Max's database (max/store.py + knowledge.py on top of it). No model calls, $0.
  .venv\\Scripts\\python tests\\test_store.py

The key check: today's JSON knowledge file imported into SQLite gives back exactly the same prompt text,
so Max's answers can't change because of the move.
"""

import copy
import glob
import json
import shutil
import sqlite3
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "max"))

from knowledge import TeamKnowledge  # noqa: E402
from store import MIGRATIONS, Store  # noqa: E402

fails = 0


def check(name: str, ok, detail="") -> None:
    global fails
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f"  [{detail}]" if detail != "" else ""))


def strip_seq(meetings: list) -> list:
    return [{k: v for k, v in m.items() if not k.startswith("_")} for m in meetings]


def same_content(a: dict, b: dict) -> bool:
    return (a["posts"] == b["posts"] and a["files"] == b["files"]
            and strip_seq(a["meetings"]) == strip_seq(b["meetings"]))


tmp = Path(tempfile.mkdtemp())
try:
    # ------------------------------------------------------------------ schema
    st = Store(tmp / "max.db")
    check("fresh database is migrated to the latest schema", st.version == len(MIGRATIONS), st.version)
    check("WAL mode (reads don't wait for writes)", st.q1("PRAGMA journal_mode")[0] == "wal")
    st.close()
    st = Store(tmp / "max.db")
    check("reopening keeps the schema (no re-migration)", st.version == len(MIGRATIONS))

    # ------------------------------------------------------------------ import of today's JSON
    src = sorted(glob.glob(str(ROOT / "max/data/teams/*.json*")))
    if not src:
        print("SKIP import check: no JSON knowledge file on this machine")
    else:
        original = json.loads(Path(src[0]).read_text(encoding="utf-8"))
        before = TeamKnowledge(copy.deepcopy(original), None)
        shutil.copy(src[0], tmp / "team.json")
        kb = TeamKnowledge.import_json(st, tmp / "team.json")
        check("import: same posts, replies, files, meetings and transcripts", same_content(kb.data, original),
              kb.stats)
        check("import: Max's prompt text is byte-for-byte identical", kb.prompt_text() == before.prompt_text(),
              f"{len(kb.prompt_text())} chars")
        check("import: team fields kept (drive delta, meeting access)",
              kb.data["driveDelta"] == original["driveDelta"] and kb.data["meetingAccess"] == original["meetingAccess"])
        check("people learned from authors", len(st.people(kb.team_id)) >= 4, [p["name"] for p in st.people(kb.team_id)])

    # ------------------------------------------------------------------ live changes, written through
    team = {"teamId": "T1", "teamName": "Planning", "channelId": "C1", "driveId": "D1", "driveDelta": "d0",
            "builtAt": "2026-11-21T09:00:00", "posts": [], "files": [], "meetings": [], "meetingAccess": {}}
    st.replace_team_content(team)
    kb = TeamKnowledge.load(st, "T1")
    kb.add_message("p1", "Prince Alex", "Budget v2 is up", None, "2026-11-21 09:01", author_id="aad-prince")
    kb.add_message("r1", "Daniel", "Thanks", "p1", "2026-11-21 09:02")
    kb.add_message("r1", "Daniel", "Thanks", "p1", "2026-11-21 09:02")        # duplicate delivery
    kb.add_message("r2", "Jacob Thomas", "Orphan reply", "missing-root", "2026-11-21 09:03")
    kb.update_message("p1", "Budget v2 is up (edited)")
    again = TeamKnowledge.load(st, "T1")
    check("messages: posts, replies, duplicate ignored, unknown root becomes a post",
          [p["id"] for p in again.data["posts"]] == ["p1", "r2"] and len(again.data["posts"][0]["replies"]) == 1)
    check("messages: memory and database agree after reload", same_content(again.data, kb.data))
    check("edits are saved", again.data["posts"][0]["text"].endswith("(edited)") and again.data["posts"][0].get("edited"))
    check("author AAD id kept for people", st.q1("SELECT aad_id FROM people WHERE team_id='T1' AND name='Prince Alex'")[0]
          == "aad-prince")

    kb.delete_message("p1")
    rows = st.q("SELECT id, text, deleted_at FROM messages WHERE team_id='T1' AND id IN ('p1','r1')")
    check("delete: post and its replies gone from memory", [p["id"] for p in kb.data["posts"]] == ["r2"])
    check("delete: rows kept but text wiped (soft delete)", all(r["text"] == "" and r["deleted_at"] for r in rows))
    check("delete: reload doesn't bring them back", [p["id"] for p in TeamKnowledge.load(st, "T1").data["posts"]] == ["r2"])

    kb.upsert_file({"id": "f1", "name": "Budget v2.xlsx", "author": "Prince Alex", "time": "t", "text": "v2"})
    kb.upsert_file({"id": "f1", "name": "Budget v2.xlsx", "author": "Prince Alex", "time": "t", "text": "v2b"})
    kb.upsert_file({"id": "f9", "name": "Budget v2.xlsx", "author": "Prince Alex", "time": "t", "text": "re-upload"})
    kb.upsert_file({"id": "f2", "name": "Notes.md", "author": "Karthi M", "time": "t", "text": "n"})
    kb.remove_file("f2")
    files = TeamKnowledge.load(st, "T1").data["files"]
    check("files: update by id, re-upload by name replaces, remove works",
          [(f["id"], f["text"]) for f in files] == [("f9", "re-upload")], files)

    kb.set_meetings({"meetings": [{"subject": "Q3 review", "start": "2026-10-01 10:00", "end": "2026-10-01 10:30",
                                   "joinUrl": "u1", "organizer": "Karthi M", "organizerId": "o", "onlineMeetingId": "m1",
                                   "transcripts": [{"id": "t1", "created": "c", "cues": [
                                       {"start": 1.0, "speaker": "Karthi M", "text": "Hi"}]}], "transcriptNote": None}],
                     "access": {"calendar": "ok"}})
    kb.add_transcript("m1", {"id": "t2", "created": "c2", "cues": [{"start": 2.0, "speaker": "Prince Alex", "text": "Yo"}]})
    kb.add_transcript("m2", {"id": "t3", "created": "c3", "cues": []}, {"subject": "New one", "start": "s", "end": "e"})
    kb.add_transcript("m1", {"id": "t2", "created": "c2", "cues": []})                 # duplicate
    again = TeamKnowledge.load(st, "T1")
    check("meetings + transcripts round-trip (incl. new meeting from a transcript, duplicate ignored)",
          strip_seq(again.data["meetings"]) == strip_seq(kb.data["meetings"]) and again.stats["transcripts"] == 3,
          again.stats)

    kb.data["driveDelta"], kb.data["announcedProblems"], kb.data["someNewKey"] = "d1", ["x"], {"a": 1}
    kb.save()
    t = st.team("T1")
    check("team fields saved (delta, announced problems, unknown keys kept)",
          t["driveDelta"] == "d1" and t["announcedProblems"] == ["x"] and t["someNewKey"] == {"a": 1})
    check("team time zone defaults to UTC", t["timeZone"] == "UTC")

    # ------------------------------------------------------------------ gate, runs, audit
    check("inbound gate: first time True, repeat False",
          st.first_seen("channel-message", "m-1") is True and st.first_seen("channel-message", "m-1") is False)
    check("inbound gate: different source is separate", st.first_seen("mention", "m-1") is True)
    run = st.start_run("T1", "mention", "Karthi M", "p1")
    st.audit(run, "T1", "question", {"text": "hi"})
    st.audit(run, "T1", "answer", {"text": "hello"})
    st.finish_run(run, "ok", "hello", model_calls=1, tokens=100, cost_usd=0.001)
    r = st.runs("T1")[0]
    check("runs: recorded with status, counts and cost",
          r["status"] == "ok" and r["model_calls"] == 1 and r["tokens"] == 100 and r["finished_at"])
    check("audit: entries in order", [a["kind"] for a in st.audit_for(run)] == ["question", "answer"])
    try:
        with st.tx() as db:
            db.execute("UPDATE audit SET kind = 'tampered'")
        check("audit is append-only", False)
    except sqlite3.DatabaseError:
        check("audit is append-only (updates refused)", [a["kind"] for a in st.audit_for(run)] == ["question", "answer"])

    # ------------------------------------------------------------------ refs + subscriptions
    st.save_ref("T1", "C1", "http://svc")
    st.save_ref("T1", "C1", "http://svc2")
    check("conversation refs saved and updated", st.refs() == {"T1": {"channelId": "C1", "serviceUrl": "http://svc2"}})

    from subscriptions import SubscriptionManager
    cfg = SimpleNamespace(data_dir=tmp / "cfg", public_url="http://localhost:3978")
    cfg.data_dir.mkdir()
    (cfg.data_dir / "subscriptions.json").write_text(json.dumps(
        {"s1": {"id": "s1", "teamId": "T1", "kind": "messages", "resource": "/r", "changeType": "created",
                "clientState": "secret", "expires": 9e9}}), "utf-8")
    sm = SubscriptionManager(graph=None, store=st, cfg=cfg)
    check("old subscriptions.json imported once and renamed",
          "s1" in sm.subs and not (cfg.data_dir / "subscriptions.json").exists()
          and (cfg.data_dir / "subscriptions.json.imported").exists())
    check("subscriptions survive a restart (read back from the database)",
          "s1" in SubscriptionManager(graph=None, store=st, cfg=cfg).subs)
    check("clientState still checked", sm.get("s1", "secret") and sm.get("s1", "wrong") is None)

    # ------------------------------------------------------------------ concurrency
    errors = []

    def writer(n: int) -> None:
        try:
            for i in range(50):
                kb2 = TeamKnowledge.load(st, "T1") if i == 0 else kb2
                st.add_message("T1", {"id": f"w{n}-{i}", "author": "Bot", "time": "t", "text": "x"}, None)
                st.first_seen("x", f"{n}-{i}")
        except Exception as e:  # noqa: BLE001
            errors.append(repr(e))
    threads = [threading.Thread(target=writer, args=(n,)) for n in range(8)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    n = st.q1("SELECT COUNT(*) FROM messages WHERE team_id='T1' AND id LIKE 'w%'")[0]
    check("8 threads writing at once: no errors, nothing lost", not errors and n == 400, errors[:1] or n)

    # ------------------------------------------------------------------ uninstall
    st.delete_team("T1")
    left = {t: st.q1(f"SELECT COUNT(*) FROM {t} WHERE team_id='T1'")[0]
            for t in ("teams", "messages", "files", "meetings", "transcripts", "people", "runs", "audit",
                      "conversation_refs", "subscriptions")}
    check("uninstall deletes everything about the team", sum(left.values()) == 0, left)
    check("transcript lines of the team are gone too",
          st.q1("SELECT COUNT(*) FROM transcript_lines WHERE transcript_seq NOT IN (SELECT seq FROM transcripts)")[0] == 0)
    st.close()
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\nSTORE: ALL PASS" if not fails else f"\nSTORE: {fails} FAILED")
sys.exit(1 if fails else 0)
