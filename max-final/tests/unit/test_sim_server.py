"""Simulator server API for the screens: load, post, live updates, privacy rules, reset."""

import pytest
from fastapi.testclient import TestClient

from teams_sim.server import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(db_path=tmp_path / "teams_sim.db", bot_url=None)  # no Max connected
    with TestClient(app) as c:
        yield c


def test_state_lists_what_the_person_can_see(client):
    s = client.get("/api/state", params={"as": "rachitaa"}).json()
    assert s["me"]["id"] == "rachitaa"
    channel_ids = {c["id"] for t in s["teams"] for c in t["channels"]}
    assert "pp-pricing" in channel_ids and "pp-budget" not in channel_ids
    assert "max-rachitaa" in {c["id"] for c in s["chats"]}
    assert {p["id"] for p in s["people"]} >= {"prince", "praga", "rachitaa", "karthi"}


def test_unknown_person_is_refused(client):
    assert client.get("/api/state", params={"as": "nobody"}).status_code == 404


def test_post_then_read_back(client):
    r = client.post("/api/messages", json={"as": "prince", "kind": "channel", "where": "pp-models", "text": "Hello team"})
    assert r.status_code == 200
    root = r.json()
    r2 = client.post("/api/messages", json={"as": "rachitaa", "kind": "channel", "where": "pp-models",
                                             "text": "Hi", "thread_id": root["id"]})
    threads = client.get("/api/channels/pp-models/threads", params={"as": "karthi"}).json()
    mine = next(t for t in threads if t["id"] == root["id"])
    assert [x["id"] for x in mine["replies"]] == [r2.json()["id"]]


def test_private_channel_closed_to_others(client):
    assert client.get("/api/channels/pp-budget/threads", params={"as": "rachitaa"}).status_code == 403
    r = client.post("/api/messages", json={"as": "rachitaa", "kind": "channel", "where": "pp-budget", "text": "x"})
    assert r.status_code == 403
    assert client.get("/api/chats/max-prince/messages", params={"as": "praga"}).status_code == 403


def test_live_update_reaches_everyone_who_can_see_it(client):
    with client.websocket_connect("/api/live?as=rachitaa") as rachitaa, \
         client.websocket_connect("/api/live?as=praga") as praga:
        client.post("/api/messages", json={"as": "prince", "kind": "channel", "where": "pp-models", "text": "Live!"})
        event = rachitaa.receive_json()
        assert event["type"] == "message" and event["message"]["text"] == "Live!"
        # Praga is not in Product Planning: the next thing Praga gets is the chat message, not the channel post
        client.post("/api/messages", json={"as": "prince", "kind": "chat", "where": "sync", "text": "Sync!"})
        assert praga.receive_json()["message"]["text"] == "Sync!"


def test_reset_restores_the_start_set(client):
    before = client.get("/api/channels/pp-models/threads", params={"as": "prince"}).json()
    client.post("/api/messages", json={"as": "prince", "kind": "channel", "where": "pp-models", "text": "temp"})
    assert client.post("/api/reset", json={}).status_code == 200
    assert client.get("/api/channels/pp-models/threads", params={"as": "prince"}).json() == before


def test_every_handler_runs_on_the_event_loop(client):
    """Sync handlers would run in a thread pool and share the one SQLite connection across threads
    (found as a hang in the browser tests, 27 Nov 2026)."""
    import inspect

    from fastapi.routing import APIRoute, APIWebSocketRoute

    routes = [r for r in client.app.routes if isinstance(r, (APIRoute, APIWebSocketRoute))]
    assert routes
    assert [r.path for r in routes if not inspect.iscoroutinefunction(r.endpoint)] == []


def test_mentions_come_from_the_text_only(client):
    r = client.post("/api/messages", json={"as": "prince", "kind": "channel", "where": "pp-models",
                                           "text": "no tag here", "mentions": ["max", "praga", "ghost"]})
    assert r.status_code == 200 and r.json()["mentions"] == []


def test_only_json_posts(client):
    """A web page can send a "simple" cross-site form post without asking; JSON-only stops that."""
    assert client.post("/api/reset", content="x", headers={"content-type": "text/plain"}).status_code == 415
    assert client.post("/api/reset").status_code == 415                       # no body, no JSON type
    assert client.post("/api/reset", json={}).status_code == 200


def test_a_stuck_tab_is_closed_so_it_reconnects():
    import asyncio

    from teams_sim.server import Live

    class Stuck:
        closed = False

        async def send_json(self, event):
            await asyncio.sleep(60)

        async def close(self, code=1000):
            self.closed = True

    class Fine:
        got = []

        async def send_json(self, event):
            self.got.append(event)

    stuck, fine = Stuck(), Fine()
    live = Live(conn=None, send_timeout=0.1)
    live.sockets = {("prince", stuck), ("praga", fine)}
    asyncio.run(live.send_all({"type": "reset"}))
    assert stuck.closed and ("prince", stuck) not in live.sockets
    assert fine.got == [{"type": "reset"}] and ("praga", fine) in live.sockets


# ---------------------------------------------------------------- Step 3: the world, files, names

def test_state_has_everyones_names_but_only_playable_people(client):
    s = client.get("/api/state", params={"as": "prince"}).json()
    assert [p["id"] for p in s["people"]] == ["prince", "praga", "rachitaa", "karthi"]
    assert s["directory"]["kenji"] == "Kenji Mori" and s["directory"]["max"] == "Max"
    assert client.get("/api/state", params={"as": "kenji"}).status_code == 403     # background people can't be played


def test_channel_files_and_download(client):
    listed = client.get("/api/channels/pr-suppliers/files", params={"as": "praga"}).json()
    pp = next(f for f in listed if f["name"] == "Parts prices.xlsx")
    assert pp["version"] == 2 and len(pp["versions"]) == 2
    r = client.get(f"/api/files/{pp['id']}", params={"as": "praga"})
    assert r.status_code == 200 and r.content[:2] == b"PK"                     # an xlsx is a zip
    assert "Parts%20prices.xlsx" in r.headers["content-disposition"]            # the standard encoded name
    old = client.get(f"/api/files/{pp['id']}", params={"as": "praga", "v": 1})
    assert old.status_code == 200 and old.content != r.content


def test_private_files_closed_to_others(client):
    assert client.get("/api/channels/pp-budget/files", params={"as": "rachitaa"}).status_code == 403
    assert client.get("/api/files/gpu-budget", params={"as": "rachitaa"}).status_code == 403
    assert client.get("/api/files/gpu-budget", params={"as": "prince"}).status_code == 200
    assert client.get("/api/files/nope", params={"as": "prince"}).status_code == 404


def test_outsiders_learn_nothing_about_private_versions(client):
    assert client.get("/api/files/gpu-budget", params={"as": "rachitaa", "v": 9}).status_code == 403
    assert client.get("/api/files/gpu-budget", params={"as": "rachitaa", "v": 1}).status_code == 403
    assert client.get("/api/files/gpu-budget", params={"as": "prince", "v": 0}).status_code == 404
    assert client.get("/api/files/gpu-budget", params={"as": "prince", "v": 9}).status_code == 404
