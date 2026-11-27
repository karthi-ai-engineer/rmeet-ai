"""The simulated Teams starts from Thirdwave's world: history ending today, background people, edits and deletes,
files with versions, privacy, and the same world after every reset."""

from datetime import date, datetime, timezone

import pytest

from teams_sim.cloud import store

TODAY = date(2026, 11, 27)  # a Friday (TEAMS_SIM_TODAY is set in conftest for every test)


@pytest.fixture
def db(tmp_path):
    conn = store.connect(tmp_path / "teams_sim.db")
    yield conn
    conn.close()


def all_messages(db):
    return db.execute("SELECT * FROM messages ORDER BY created_at").fetchall()


def test_history_ends_today_and_starts_about_45_days_ago(db):
    rows = all_messages(db)
    first = datetime.fromisoformat(rows[0]["created_at"].rstrip("Z"))
    last = datetime.fromisoformat(rows[-1]["created_at"].rstrip("Z"))
    assert last.date() <= TODAY and (TODAY - last.date()).days <= 1
    assert 40 <= (TODAY - first.date()).days <= 50


def test_world_messages_are_in_their_places(db):
    kickoff = next(t for t in store.channel_threads(db, "pp-models") if "Kick-off for the Raptor X9" in t["text"])
    assert kickoff["author"] == "prince"
    assert {r["author"] for r in kickoff["replies"]} >= {"kenji", "sven", "rachitaa"}
    assert "Fri 8 Jan" in kickoff["text"]                                       # sliding date filled in
    assert any("piano recital" in m["text"] for m in store.chat_messages(db, "prince-praga"))


def test_background_people_have_names_but_cannot_be_played(db):
    assert [p["id"] for p in store.people(db)] == ["prince", "praga", "rachitaa", "karthi"]
    assert store.directory(db)["kenji"] == "Kenji Mori"


def test_edited_and_deleted_history(db):
    edited = next(m for t in store.channel_threads(db, "sa-accounts") for m in [t, *t["replies"]] if "Hannah Weiss, +81" in m["text"])
    assert "0142" in edited["text"] and edited["edited_at"]
    texts = [m["text"] for t in store.channel_threads(db, "pr-suppliers") for m in [t, *t["replies"]]]
    assert not any("52,000" in t for t in texts)                               # deleted: never shown


def test_private_channel_history_stays_private(db):
    assert store.can_see(db, "prince", "channel", "pp-budget")
    assert not store.can_see(db, "rachitaa", "channel", "pp-budget")
    assert any("BLUEHERON" in t["text"] for t in store.channel_threads(db, "pp-budget"))


def test_files_with_versions(db):
    files = {f["name"]: f for f in store.channel_files(db, "pr-suppliers")}
    pp = files["Parts prices.xlsx"]
    assert pp["version"] == 2 and [v["v"] for v in pp["versions"]] == [1, 2] and pp["size"] > 1000
    v1 = store.file_version(db, pp["id"], 1)
    assert v1["path"].exists() and v1["path"] != store.file_version(db, pp["id"], 2)["path"]


def test_private_files_only_for_members(db):
    budget = next(f for f in store.channel_files(db, "pp-budget") if f["name"] == "GPU budget BLUEHERON.xlsx")
    assert store.can_see_file(db, "prince", budget["id"]) and not store.can_see_file(db, "rachitaa", budget["id"])


def test_reset_gives_the_same_world(db):
    before = [(r["id"], r["text"]) for r in all_messages(db)]
    store.post(db, "prince", "channel", "pp-models", "temporary")
    store.reset(db)
    assert [(r["id"], r["text"]) for r in all_messages(db)] == before


def test_max_chats_start_empty(db):
    assert store.chat_messages(db, "max-prince") == []


def test_history_reaches_this_morning(db):
    assert any("coffee machine is fixed" in t["text"] for t in store.channel_threads(db, "pp-general"))


def test_nothing_from_the_future():
    from teams_sim.cloud.world import already_happened

    items = [{"at": "2026-11-27T00:00:00.000Z"}, {"at": "2026-11-27T05:00:00.000Z"}]
    assert already_happened(items, datetime(2026, 11, 27, 1, 0, tzinfo=timezone.utc)) == items[:1]
    assert already_happened(items, None) == items


def test_a_changed_world_is_loaded_fresh(tmp_path, monkeypatch):
    from teams_sim.cloud import world

    path = tmp_path / "teams_sim.db"
    conn = store.connect(path)
    store.post(conn, "prince", "channel", "pp-models", "played yesterday")
    conn.close()
    assert any("played yesterday" in t["text"] for t in store.channel_threads(store.connect(path), "pp-models"))  # same world: kept
    monkeypatch.setattr(world, "version", lambda: "something-new")
    conn = store.connect(path)
    assert not any("played yesterday" in t["text"] for t in store.channel_threads(conn, "pp-models"))      # new world: rebuilt


def test_missing_made_file_is_a_clear_not_found(db):
    f = store.file_version(db, "whiteboard")
    f["path"].rename(f["path"].with_suffix(".gone"))
    try:
        with pytest.raises(store.NotFound, match="Reset world"):
            store.file_version(db, "whiteboard")
    finally:
        f["path"].with_suffix(".gone").rename(f["path"])
