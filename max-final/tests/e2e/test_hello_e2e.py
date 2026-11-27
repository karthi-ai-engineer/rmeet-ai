"""Step 2 end to end (no browser): a person writes, the fake Microsoft service tells Max, Max answers in place."""

import time

import httpx


def post(sim, **body):
    r = httpx.post(f"{sim}/api/messages", json=body)
    r.raise_for_status()
    return r.json()


def wait_for(fn, seconds=15):
    end = time.time() + seconds
    while time.time() < end:
        value = fn()
        if value:
            return value
        time.sleep(0.2)
    return fn()


def replies(sim, channel, root_id, person="prince"):
    threads = httpx.get(f"{sim}/api/channels/{channel}/threads", params={"as": person}).json()
    return next(t for t in threads if t["id"] == root_id)["replies"]


def test_mention_in_a_channel_gets_a_reply_in_the_thread(sim):
    root = post(sim, **{"as": "prince", "kind": "channel", "where": "pp-models", "text": "@Max are you there?"})
    got = wait_for(lambda: replies(sim, "pp-models", root["id"]))
    assert [(m["author"], m["text"]) for m in got] == [("max", "Hi Prince, I'm Max. I'm connected 👋")]


def test_mention_inside_a_reply_thread(sim):
    root = post(sim, **{"as": "prince", "kind": "channel", "where": "pp-models", "text": "Launch moved"})
    post(sim, **{"as": "rachitaa", "kind": "channel", "where": "pp-models", "text": "@Max hi", "thread_id": root["id"]})
    got = wait_for(lambda: [m for m in replies(sim, "pp-models", root["id"]) if m["author"] == "max"])
    assert got[0]["text"].startswith("Hi Rachitaa")


def test_own_chat_with_max(sim):
    post(sim, **{"as": "praga", "kind": "chat", "where": "max-praga", "text": "hello"})
    msgs = lambda: httpx.get(f"{sim}/api/chats/max-praga/messages", params={"as": "praga"}).json()
    got = wait_for(lambda: [m for m in msgs() if m["author"] == "max"])
    assert got[0]["text"] == "Hi Praga, I'm Max. I'm connected 👋"


def test_no_mention_no_answer(sim):
    root = post(sim, **{"as": "prince", "kind": "channel", "where": "pp-models", "text": "just people talking"})
    time.sleep(2)
    assert replies(sim, "pp-models", root["id"]) == []
