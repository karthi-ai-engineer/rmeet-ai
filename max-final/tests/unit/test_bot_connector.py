"""Fake Microsoft bot service: what Max receives, and what Max can send back (real Bot Framework contract)."""

import pytest
from fastapi.testclient import TestClient
from microsoft_teams.api.activities import ActivityTypeAdapter

from teams_sim.cloud import bot_connector as bc
from teams_sim.cloud import store
from teams_sim.server import create_app

SU = "http://127.0.0.1:5100/"


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(db_path=tmp_path / "teams_sim.db", bot_url=None)) as c:
        yield c


@pytest.fixture
def db(client):
    return client.app.state.conn


# ---------------------------------------------------------------- who gets sent to Max

def test_max_gets_every_message_in_its_own_chat(db):
    msg = store.post(db, "prince", "chat", "max-prince", "hello")
    assert bc.should_deliver(db, msg)


def test_max_gets_channel_and_group_messages_only_when_mentioned(db):
    plain = store.post(db, "prince", "channel", "pp-models", "no mention")
    tagged = store.post(db, "prince", "channel", "pp-models", "@Max hi", mentions=["max"])
    group = store.post(db, "prince", "chat", "sync", "@Max hi", mentions=["max"])
    group_plain = store.post(db, "prince", "chat", "sync", "hi all")
    assert not bc.should_deliver(db, plain) and bc.should_deliver(db, tagged)
    assert bc.should_deliver(db, group) and not bc.should_deliver(db, group_plain)


def test_max_never_gets_its_own_messages(db):
    msg = store.post(db, "max", "chat", "max-prince", "Hi Prince")
    assert not bc.should_deliver(db, msg)


def test_max_not_sent_messages_from_chats_it_is_not_in(db):
    msg = store.post(db, "prince", "chat", "prince-praga", "@Max hi", mentions=["max"])
    assert not bc.should_deliver(db, msg)


# ---------------------------------------------------------------- the activity Max receives

def test_channel_mention_activity_matches_the_teams_schema(db):
    root = store.post(db, "prince", "channel", "pp-models", "Launch moved")
    msg = store.post(db, "rachitaa", "channel", "pp-models", "@Max does Northwind know?", thread_id=root["id"], mentions=["max"])
    a = bc.build_activity(db, msg, SU)
    assert a["type"] == "message" and a["id"] == msg["id"] and a["channelId"] == "msteams"
    assert a["serviceUrl"] == SU
    assert a["conversation"]["conversationType"] == "channel"
    assert a["conversation"]["id"] == f"19:pp-models@thread.tacv2;messageid={root['id']}"   # replies go into the thread
    assert a["text"] == "<at>Max</at> does Northwind know?"
    assert a["entities"][0] == {"type": "mention", "text": "<at>Max</at>",
                                "mentioned": {"id": a["recipient"]["id"], "name": "Max"}}
    assert a["channelData"]["channel"]["id"] == "19:pp-models@thread.tacv2"
    assert a["channelData"]["team"]["name"] == "Product Planning"
    assert a["from"]["name"] == "Rachitaa" and a["from"]["aadObjectId"]
    parsed = ActivityTypeAdapter.validate_python(a)                    # the SDK's own model accepts it
    assert parsed.is_recipient_mentioned()


def test_personal_chat_activity(db):
    msg = store.post(db, "praga", "chat", "max-praga", "hello")
    a = bc.build_activity(db, msg, SU)
    assert a["conversation"]["conversationType"] == "personal"
    assert a["conversation"]["id"] == "a:max-praga"
    assert a["text"] == "hello" and a.get("entities", []) == []
    ActivityTypeAdapter.validate_python(a)


def test_group_chat_activity(db):
    msg = store.post(db, "prince", "chat", "sync", "@Max when is launch?", mentions=["max"])
    a = bc.build_activity(db, msg, SU)
    assert a["conversation"]["conversationType"] == "groupChat" and a["conversation"]["isGroup"] is True
    assert a["conversation"]["id"] == "19:sync@thread.v2"
    ActivityTypeAdapter.validate_python(a)


def test_conversation_ids_round_trip():
    assert bc.parse_conversation("19:pp-models@thread.tacv2;messageid=123") == ("channel", "pp-models", "123")
    assert bc.parse_conversation("19:pp-models@thread.tacv2") == ("channel", "pp-models", None)
    assert bc.parse_conversation("19:sync@thread.v2") == ("chat", "sync", None)
    assert bc.parse_conversation("a:max-prince") == ("chat", "max-prince", None)
    with pytest.raises(ValueError):
        bc.parse_conversation("garbage")


# ---------------------------------------------------------------- what Max sends back

def bot_send(client, conv, body):
    return client.post(f"/v3/conversations/{conv}/activities", json={"type": "message", **body})


def test_reply_lands_in_the_right_thread_and_goes_live(client, db):
    root = store.post(db, "prince", "channel", "pp-models", "@Max hi", mentions=["max"])
    with client.websocket_connect("/api/live?as=rachitaa") as ws:
        r = bot_send(client, f"19:pp-models@thread.tacv2;messageid={root['id']}", {"text": "Hi Prince 👋"})
        assert r.status_code in (200, 201)
        new_id = r.json()["id"]
        event = ws.receive_json()
    assert event["type"] == "message" and event["message"]["id"] == new_id
    thread = next(t for t in store.channel_threads(db, "pp-models") if t["id"] == root["id"])
    assert thread["replies"][-1]["author"] == "max" and thread["replies"][-1]["text"] == "Hi Prince 👋"


def test_reply_in_personal_chat(client, db):
    r = bot_send(client, "a:max-prince", {"text": "Hi Prince"})
    assert store.chat_messages(db, "max-prince")[-1]["id"] == r.json()["id"]


def test_quoted_reply_is_understood(client, db):
    msg = store.post(db, "prince", "chat", "max-prince", "hello")
    r = bot_send(client, "a:max-prince", {"text": f'<quoted messageId="{msg["id"]}"/> Hi!',
                                          "entities": [{"type": "quotedReply", "quotedReply": {"messageId": msg["id"]}}]})
    saved = store.get_message(db, r.json()["id"])
    assert saved["text"] == "Hi!" and saved["quote"]["id"] == msg["id"]


def test_cards_are_kept(client, db):
    card = {"contentType": "application/vnd.microsoft.card.adaptive", "content": {"type": "AdaptiveCard", "version": "1.5", "body": []}}
    r = bot_send(client, "a:max-prince", {"attachments": [card]})
    assert store.get_message(db, r.json()["id"])["attachments"] == [card]


def test_update_and_delete_own_message(client, db):
    mid = bot_send(client, "a:max-prince", {"text": "Working…"}).json()["id"]
    r = client.put(f"/v3/conversations/a:max-prince/activities/{mid}", json={"type": "message", "id": mid, "text": "Done ✅"})
    assert r.status_code == 200 and r.json()["id"] == mid
    assert store.get_message(db, mid)["text"] == "Done ✅"
    assert client.delete(f"/v3/conversations/a:max-prince/activities/{mid}").status_code == 200
    assert store.get_message(db, mid)["deleted"] == 1


def test_cannot_change_someone_elses_message(client, db):
    msg = store.post(db, "prince", "chat", "max-prince", "mine")
    assert client.put(f"/v3/conversations/a:max-prince/activities/{msg['id']}",
                      json={"type": "message", "text": "hacked"}).status_code == 403
    assert client.delete(f"/v3/conversations/a:max-prince/activities/{msg['id']}").status_code == 403


def test_cannot_post_where_max_is_not(client):
    assert bot_send(client, "19:prince-praga@thread.v2", {"text": "hi"}).status_code == 403
    assert bot_send(client, "19:nope@thread.tacv2", {"text": "hi"}).status_code == 404


def test_typing_and_streaming_go_live_only(client, db):
    before = len(store.chat_messages(db, "max-prince"))
    with client.websocket_connect("/api/live?as=prince") as ws:
        assert bot_send(client, "a:max-prince", {"type": "typing"}).status_code in (200, 201)
        assert ws.receive_json()["type"] == "typing"
        first = client.post("/v3/conversations/a:max-prince/activities", json={
            "type": "typing", "text": "Thinking",
            "entities": [{"type": "streaminfo", "streamType": "informative", "streamSequence": 1}]}).json()
        sid = first["id"]
        client.post("/v3/conversations/a:max-prince/activities", json={
            "type": "typing", "text": "Hi Pri", "id": sid,
            "entities": [{"type": "streaminfo", "streamId": sid, "streamType": "streaming", "streamSequence": 2}]})
        client.post("/v3/conversations/a:max-prince/activities", json={
            "type": "message", "text": "Hi Prince", "id": sid,
            "entities": [{"type": "streaminfo", "streamId": sid, "streamType": "final"}]})
        events = [ws.receive_json() for _ in range(3)]
    assert [e["type"] for e in events] == ["stream", "stream", "message"]
    assert events[1]["text"] == "Hi Pri"
    msgs = store.chat_messages(db, "max-prince")
    assert len(msgs) == before + 1 and msgs[-1]["text"] == "Hi Prince"          # one message, not one per chunk


# ---------------------------------------------------------------- review fixes (27 Nov 2026)

def test_cannot_change_a_message_through_another_conversation(client, db):
    mid = bot_send(client, "a:max-prince", {"text": "for Prince only"}).json()["id"]
    with client.websocket_connect("/api/live?as=rachitaa") as ws:
        assert client.put(f"/v3/conversations/a:max-rachitaa/activities/{mid}",
                          json={"type": "message", "text": "leak"}).status_code == 404
        assert client.delete(f"/v3/conversations/a:max-rachitaa/activities/{mid}").status_code == 404
        bot_send(client, "a:max-rachitaa", {"text": "marker"})
        assert ws.receive_json()["message"]["text"] == "marker"        # nothing about Prince's message came first
    assert store.get_message(db, mid)["text"] == "for Prince only"


def test_update_goes_to_the_people_of_that_place(client, db):
    mid = bot_send(client, "a:max-prince", {"text": "v1"}).json()["id"]
    with client.websocket_connect("/api/live?as=prince") as ws:
        client.put(f"/v3/conversations/a:max-prince/activities/{mid}", json={"type": "message", "text": "v2"})
        event = ws.receive_json()
    assert event["type"] == "update" and event["message"]["text"] == "v2"


def stream_post(client, conv, body):
    return client.post(f"/v3/conversations/{conv}/activities", json=body)


def test_streamed_answer_keeps_one_id_from_first_chunk_to_edit(client, db):
    first = stream_post(client, "a:max-prince", {"type": "typing", "text": "Thinking",
                        "entities": [{"type": "streaminfo", "streamType": "informative", "streamSequence": 1}]})
    sid = first.json()["id"]
    assert sid.isdigit()                                               # a real message id, like Teams
    final = stream_post(client, "a:max-prince", {"type": "message", "text": "Done", "id": sid,
                        "entities": [{"type": "streaminfo", "streamId": sid, "streamType": "final"}]})
    assert final.json()["id"] == sid
    assert client.put(f"/v3/conversations/a:max-prince/activities/{sid}",
                      json={"type": "message", "text": "Done ✅"}).status_code == 200
    assert store.get_message(db, sid)["text"] == "Done ✅"


def test_streaming_only_in_one_to_one_chats(client):
    for conv in ("19:sync@thread.v2", "19:pp-models@thread.tacv2"):
        r = stream_post(client, conv, {"type": "typing", "text": "x",
                        "entities": [{"type": "streaminfo", "streamType": "informative", "streamSequence": 1}]})
        assert r.status_code == 403


AI_ENTITY = {"type": "https://schema.org/Message", "@type": "Message", "@context": "https://schema.org",
             "additionalType": ["AIGeneratedContent"]}


def test_ai_label_and_feedback_only_when_the_bot_asks(client, db):
    plain = bot_send(client, "a:max-prince", {"text": "Hi"}).json()["id"]
    ai = bot_send(client, "a:max-prince", {"text": "Answer", "entities": [AI_ENTITY],
                                           "channelData": {"feedbackLoop": {"type": "default"}}}).json()["id"]
    legacy = bot_send(client, "a:max-prince", {"text": "Answer", "channelData": {"feedbackLoopEnabled": True}}).json()["id"]
    assert (store.get_message(db, plain)["ai_label"], store.get_message(db, plain)["feedback"]) == (0, 0)
    assert (store.get_message(db, ai)["ai_label"], store.get_message(db, ai)["feedback"]) == (1, 1)
    assert store.get_message(db, legacy)["feedback"] == 1


def test_max_can_only_mention_people_in_the_place(client, db):
    praga = bc.user_id("praga")
    mid = bot_send(client, "a:max-prince", {"text": "<at>Praga</at> hi",
                                            "entities": [{"type": "mention", "text": "<at>Praga</at>",
                                                          "mentioned": {"id": praga, "name": "Praga"}}]}).json()["id"]
    assert store.get_message(db, mid)["mentions"] == []


def test_team_id_is_the_general_channel(client, db):
    msg = store.post(db, "prince", "channel", "pp-models", "@Max hi", mentions=["max"])
    team_id = bc.build_activity(db, msg, SU)["channelData"]["team"]["id"]
    assert team_id == "19:pp-general@thread.tacv2"                     # in Teams the team id is General's id
    r = bot_send(client, team_id, {"text": "Hello General"})
    assert store.get_message(db, r.json()["id"])["where_id"] == "pp-general"


def test_reply_to_a_channel_message_goes_into_its_thread(client, db):
    root = store.post(db, "prince", "channel", "pp-models", "root")
    reply = store.post(db, "rachitaa", "channel", "pp-models", "reply", thread_id=root["id"])
    a = client.post(f"/v3/conversations/19:pp-models@thread.tacv2/activities/{reply['id']}",
                    json={"type": "message", "text": "via path"}).json()["id"]
    b = bot_send(client, "19:pp-models@thread.tacv2", {"text": "via replyToId", "replyToId": root["id"]}).json()["id"]
    assert store.get_message(db, a)["thread_id"] == root["id"]
    assert store.get_message(db, b)["thread_id"] == root["id"]


def test_conversation_ids_are_strict(client):
    assert bot_send(client, "a:sync", {"text": "x"}).status_code == 404            # a group chat isn't "a:"
    assert bot_send(client, "19:max-prince@thread.v2", {"text": "x"}).status_code == 404


def test_only_json_requests(client):
    r = client.post("/v3/conversations/a:max-prince/activities", content='{"type":"message","text":"x"}',
                    headers={"content-type": "text/plain"})
    assert r.status_code == 415


def test_stream_timeout_fallback_finishes_the_answer(client, db):
    """The SDK's fallback after a stream times out: PUT the final text onto the stream id (no streaminfo)."""
    sid = stream_post(client, "a:max-prince", {"type": "typing", "text": "Thinking",
                      "entities": [{"type": "streaminfo", "streamType": "informative", "streamSequence": 1}]}).json()["id"]
    with client.websocket_connect("/api/live?as=prince") as ws:
        r = client.put(f"/v3/conversations/a:max-prince/activities/{sid}",
                       json={"type": "message", "id": sid, "text": "Final answer", "entities": [AI_ENTITY]})
        event = ws.receive_json()
    assert r.status_code == 200
    assert event["type"] == "message" and event["stream_id"] == sid
    saved = store.get_message(db, sid)
    assert saved["pending"] == 0 and saved["edited_at"] is None and saved["ai_label"] == 1
    assert store.chat_messages(db, "max-prince")[-1]["id"] == sid


def test_typing_ignores_reply_to(client):
    r = bot_send(client, "19:pp-models@thread.tacv2", {"type": "typing", "replyToId": "999"})
    assert r.status_code in (200, 201)


def test_half_streamed_answers_are_cleared_on_start(tmp_path):
    from teams_sim.server import create_app

    path = tmp_path / "teams_sim.db"
    conn = store.connect(path)
    draft = store.post(conn, "max", "chat", "max-prince", "", pending=True)
    conn.close()
    with TestClient(create_app(db_path=path, bot_url=None)) as c:
        with pytest.raises(store.NotFound):
            store.get_message(c.app.state.conn, draft["id"])
