"""Simulated Teams store: posts, replies, chats, who can see what, reset."""

import pytest

from teams_sim.cloud import store


@pytest.fixture
def db(tmp_path):
    conn = store.connect(tmp_path / "teams_sim.db")
    yield conn
    conn.close()


def test_starts_with_the_seed_set(db):
    names = {p["id"] for p in store.people(db)}
    assert {"karthi", "prince", "praga", "rachitaa"} <= names
    assert store.person(db, "max")["is_bot"] == 1
    teams = {t["id"]: t for t in store.teams_for(db, "prince")}
    assert "planning" in teams and "procurement" not in teams       # Prince is not in Procurement
    assert [c["id"] for c in teams["planning"]["channels"]][:1] == ["pp-general"]


def test_private_channel_only_for_its_members(db):
    def channel_ids(person):
        return {c["id"] for t in store.teams_for(db, person) for c in t["channels"]}

    assert "pp-budget" in channel_ids("prince")
    assert "pp-budget" not in channel_ids("rachitaa")               # in the team, not in the private channel
    assert store.can_see(db, "prince", "channel", "pp-budget")
    assert not store.can_see(db, "rachitaa", "channel", "pp-budget")
    assert not store.can_see(db, "praga", "channel", "pp-pricing")  # not in the team at all


def test_post_and_reply_make_a_thread(db):
    root = store.post(db, "prince", "channel", "pp-models", "Launch moves to 15 Jan")
    r1 = store.post(db, "rachitaa", "channel", "pp-models", "Does Northwind know?", thread_id=root["id"])
    threads = store.channel_threads(db, "pp-models")
    mine = next(t for t in threads if t["id"] == root["id"])
    assert [r["id"] for r in mine["replies"]] == [r1["id"]]
    assert r1["thread_id"] == root["id"]
    assert int(r1["id"]) > int(root["id"])                         # Teams-like ids: numbers that grow


def test_reply_must_go_to_a_root_post_in_the_same_channel(db):
    root = store.post(db, "prince", "channel", "pp-models", "root")
    reply = store.post(db, "rachitaa", "channel", "pp-models", "reply", thread_id=root["id"])
    with pytest.raises(store.NotAllowed):
        store.post(db, "rachitaa", "channel", "pp-models", "x", thread_id=reply["id"])   # no replies to replies
    with pytest.raises(store.NotAllowed):
        store.post(db, "rachitaa", "channel", "pp-pricing", "x", thread_id=root["id"])  # other channel


def test_cannot_post_where_you_cannot_see(db):
    with pytest.raises(store.NotAllowed):
        store.post(db, "rachitaa", "channel", "pp-budget", "hi")
    with pytest.raises(store.NotAllowed):
        store.post(db, "praga", "chat", "prince-rachitaa", "hi")
    with pytest.raises(store.NotAllowed):
        store.post(db, "prince", "chat", "max-praga", "hi")         # someone else's chat with Max


def test_empty_message_refused(db):
    with pytest.raises(store.NotAllowed):
        store.post(db, "prince", "channel", "pp-models", "   ")


def test_quote_reply_keeps_the_quoted_text(db):
    first = store.post(db, "praga", "chat", "sync", "Supplier B is 6% cheaper")
    second = store.post(db, "prince", "chat", "sync", "Too late for launch", quote_id=first["id"])
    assert second["quote"] == {"id": first["id"], "author": "praga", "text": "Supplier B is 6% cheaper"}


def test_every_person_has_a_chat_with_max(db):
    for person in ("karthi", "prince", "praga", "rachitaa"):
        chat = store.max_chat_for(db, person)
        assert chat["kind"] == "max"
        assert {m for m in chat["members"]} == {person, "max"}
    chats = {c["id"] for c in store.chats_for(db, "prince")}
    assert "max-prince" in chats and "max-praga" not in chats


def test_mentions_are_stored(db):
    msg = store.post(db, "prince", "channel", "pp-models", "@Max hello", mentions=["max"])
    assert msg["mentions"] == ["max"]
    assert store.get_message(db, msg["id"])["mentions"] == ["max"]


def test_edit_and_delete(db):
    msg = store.post(db, "max", "chat", "max-prince", "Thinking…")
    edited = store.edit(db, msg["id"], "Hi Prince 👋")
    assert edited["text"] == "Hi Prince 👋" and edited["edited_at"]
    store.delete(db, msg["id"])
    assert store.get_message(db, msg["id"])["deleted"] == 1
    assert msg["id"] not in {m["id"] for m in store.chat_messages(db, "max-prince")}


def test_cards_are_kept_as_json(db):
    card = {"type": "AdaptiveCard", "version": "1.5", "body": [{"type": "TextBlock", "text": "hi"}]}
    msg = store.post(db, "max", "chat", "max-prince", "", attachments=[{"contentType": "application/vnd.microsoft.card.adaptive", "content": card}])
    assert store.get_message(db, msg["id"])["attachments"][0]["content"] == card


def test_reset_goes_back_to_the_start_set(db):
    before = len(store.channel_threads(db, "pp-pricing"))
    store.post(db, "prince", "channel", "pp-pricing", "temporary")
    store.reset(db)
    assert len(store.channel_threads(db, "pp-pricing")) == before


def test_reopening_keeps_data(tmp_path):
    path = tmp_path / "teams_sim.db"
    conn = store.connect(path)
    msg = store.post(conn, "prince", "channel", "pp-models", "keep me")
    conn.close()
    conn = store.connect(path)
    assert store.get_message(conn, msg["id"])["text"] == "keep me"


def test_mentions_found_in_text(db):
    assert store.find_mentions(db, "@Max when is launch?", "channel", "pp-models") == ["max"]
    assert store.find_mentions(db, "hey @max and @Rachitaa", "channel", "pp-models") == ["rachitaa", "max"] or \
        set(store.find_mentions(db, "hey @max and @Rachitaa", "channel", "pp-models")) == {"max", "rachitaa"}
    assert store.find_mentions(db, "@Maxwell is not Max", "channel", "pp-models") == []
    assert store.find_mentions(db, "mail me at a@max.com", "channel", "pp-models") == []
    assert store.find_mentions(db, "@Praga hi", "channel", "pp-models") == []          # Praga is not in this team


def test_people_listed_in_team_order(db):
    assert [p["id"] for p in store.people(db)] == ["prince", "praga", "rachitaa", "karthi"]


def test_deleted_messages_cannot_be_quoted_replied_to_or_edited(db):
    root = store.post(db, "prince", "channel", "pp-models", "root")
    store.delete(db, root["id"])
    with pytest.raises(store.NotAllowed):
        store.post(db, "rachitaa", "channel", "pp-models", "reply", thread_id=root["id"])
    with pytest.raises(store.NotAllowed):
        store.post(db, "rachitaa", "channel", "pp-models", "quoting", quote_id=root["id"])
    with pytest.raises(store.NotFound):
        store.edit(db, root["id"], "back again")


def test_empty_edit_refused(db):
    msg = store.post(db, "max", "chat", "max-prince", "hi")
    with pytest.raises(store.NotAllowed):
        store.edit(db, msg["id"], "  ")


def test_streamed_answer_is_hidden_until_finished(db):
    draft = store.post(db, "max", "chat", "max-prince", "", pending=True)
    assert draft["id"] not in {m["id"] for m in store.chat_messages(db, "max-prince")}
    done = store.finish(db, draft["id"], "Hi Prince", ai_label=True, feedback=True)
    assert done["id"] == draft["id"] and done["pending"] == 0 and done["ai_label"] == 1 and done["feedback"] == 1
    assert store.chat_messages(db, "max-prince")[-1]["id"] == draft["id"]
    with pytest.raises(store.NotAllowed):
        store.finish(db, draft["id"], "again")                       # only once


def test_plain_messages_have_no_ai_label(db):
    msg = store.post(db, "max", "chat", "max-prince", "Hi")
    assert msg["ai_label"] == 0 and msg["feedback"] == 0
