"""
The fake Microsoft bot service. It speaks the real Bot Framework contract, so Max (built with the Teams SDK for
Python) can't tell it from real Teams:

  to Max     POST {bot_url} with an "activity" (the same JSON Teams sends: sender, conversation, mentions, ...)
  from Max   POST   /v3/conversations/{conversation}/activities          new message / typing / streaming
             POST   /v3/conversations/{conversation}/activities/{id}     reply (older SDK style)
             PUT    /v3/conversations/{conversation}/activities/{id}     edit Max's own message
             DELETE /v3/conversations/{conversation}/activities/{id}     delete Max's own message

Like real Teams (without extra permissions), Max gets every message in its own 1:1 chats, and in channels and group
chats only messages that @mention it. Conversation ids look like Teams ids:
  channel thread  19:{channel}@thread.tacv2;messageid={root post id}
  group chat      19:{chat}@thread.v2
  1:1 with Max    a:{chat}
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid

import httpx
from fastapi import APIRouter, HTTPException, Request

from teams_sim.cloud import store

log = logging.getLogger("teams_sim.bot")

NS = uuid.UUID("6f1d3c52-7a0e-4b8e-9d55-1c2a3b4c5d6e")  # makes stable, real-looking GUIDs from our short ids
BOT_APP_ID = str(uuid.uuid5(NS, "app:max"))
BOT_ID = f"28:{BOT_APP_ID}"
TENANT_ID = str(uuid.uuid5(NS, "tenant:thirdwave"))


def guid(kind: str, key: str) -> str:
    return str(uuid.uuid5(NS, f"{kind}:{key}"))


def user_id(pid: str) -> str:
    return BOT_ID if pid == "max" else f"29:{guid('user', pid)}"


# ---------------------------------------------------------------- conversation ids

def conversation_id(kind: str, where: str, thread_id: str | None = None) -> str:
    if kind == "channel":
        return f"19:{where}@thread.tacv2" + (f";messageid={thread_id}" if thread_id else "")
    if where.startswith("max-"):
        return f"a:{where}"
    return f"19:{where}@thread.v2"


def parse_conversation(conv: str) -> tuple[str, str, str | None]:
    """Conversation id -> (kind, place id, thread root id or None)."""
    if conv.startswith("a:") and len(conv) > 2:
        return "chat", conv[2:], None
    m = re.fullmatch(r"19:([^@;]+)@thread\.tacv2(?:;messageid=(\d+))?", conv)
    if m:
        return "channel", m.group(1), m.group(2)
    m = re.fullmatch(r"19:([^@;]+)@thread\.v2", conv)
    if m:
        return "chat", m.group(1), None
    raise ValueError(f"not a conversation id: {conv!r}")


# ---------------------------------------------------------------- to Max

def should_deliver(conn, msg: dict) -> bool:
    if msg["author"] == "max" or not store.can_see(conn, "max", msg["where_kind"], msg["where_id"]):
        return False
    if msg["where_kind"] == "chat" and store.chat(conn, msg["where_id"])["kind"] == "max":
        return True
    return "max" in msg["mentions"]


def build_activity(conn, msg: dict, service_url: str) -> dict:
    """The activity Teams would send Max for this message."""
    sender = store.person(conn, msg["author"])
    kind, where = msg["where_kind"], msg["where_id"]
    text, entities = msg["text"], []
    for pid in msg["mentions"]:
        name = store.person(conn, pid)["name"]
        tag = f"<at>{name}</at>"
        text = re.sub(rf"@{re.escape(name)}\b", tag, text, flags=re.IGNORECASE)
        entities.append({"type": "mention", "text": tag, "mentioned": {"id": user_id(pid), "name": name}})
    channel_data: dict = {"tenant": {"id": TENANT_ID}}
    if kind == "channel":
        ch = store.channel(conn, where)
        team = next(t for t in store.teams_for(conn, "max") if t["id"] == ch["team_id"])
        conv = {"id": conversation_id(kind, where, msg["thread_id"] or msg["id"]), "conversationType": "channel",
                "isGroup": True, "tenantId": TENANT_ID, "name": ch["name"]}
        general = team["channels"][0]["id"]  # in Teams a team's id is its General channel's id
        channel_data["team"] = {"id": conversation_id("channel", general), "name": team["name"], "aadGroupId": guid("team", team["id"])}
        channel_data["channel"] = {"id": conversation_id(kind, where), "name": ch["name"], "type": "private" if ch["private"] else "standard"}
    else:
        c = store.chat(conn, where)
        personal = c["kind"] == "max"
        conv = {"id": conversation_id(kind, where), "conversationType": "personal" if personal else "groupChat",
                "tenantId": TENANT_ID}
        if not personal:
            conv["isGroup"] = True
            if c["title"]:
                conv["name"] = c["title"]
    activity = {
        "type": "message",
        "id": msg["id"],
        "timestamp": msg["created_at"],
        "localTimestamp": msg["created_at"],
        "channelId": "msteams",
        "serviceUrl": service_url,
        "from": {"id": user_id(sender["id"]), "name": sender["name"], "aadObjectId": guid("user", sender["id"])},
        "conversation": conv,
        "recipient": {"id": BOT_ID, "name": "Max"},
        "text": text,
        "textFormat": "plain",
        "locale": "en-US",
        "entities": entities,
        "channelData": channel_data,
    }
    if msg["thread_id"]:
        activity["replyToId"] = msg["thread_id"]
    return activity


async def deliver(conn, msg: dict, bot_url: str, service_url: str) -> None:
    """Send one message to Max. Like Teams, waits for Max's answer to the POST (Max replies through /v3 meanwhile)."""
    try:
        activity = build_activity(conn, msg, service_url)
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(bot_url, json=activity)
        if r.status_code >= 300:
            log.warning("Max answered %s for message %s: %s", r.status_code, msg["id"], r.text[:200])
    except httpx.HTTPError as e:
        log.warning("Max is not reachable at %s (%s)", bot_url, e.__class__.__name__)
    except Exception:
        log.exception("could not deliver message %s to Max", msg["id"])


# ---------------------------------------------------------------- from Max

QUOTE = re.compile(r'^\s*<quoted messageId="(\d+)"\s*/>\s*')
AT = re.compile(r"<at>([^<]+)</at>")


def make_router(conn, live) -> APIRouter:
    router = APIRouter()

    async def json_body(request: Request) -> dict:
        """Only JSON, like the real service (also stops simple cross-site form posts from a web page)."""
        if not request.headers.get("content-type", "").lower().startswith("application/json"):
            raise HTTPException(415, "send JSON (Content-Type: application/json)")
        body = await request.json()
        if not isinstance(body, dict):
            raise HTTPException(400, "the activity must be a JSON object")
        return body

    def place(conv: str) -> tuple[str, str, str | None]:
        try:
            kind, where, thread = parse_conversation(conv)
        except ValueError as e:
            raise HTTPException(400, str(e))
        if not _exists(conn, kind, where):
            raise HTTPException(404, f"no conversation {conv}")
        if kind == "chat" and (store.chat(conn, where)["kind"] == "max") != conv.startswith("a:"):
            raise HTTPException(404, f"no conversation {conv}")  # one id per chat: "a:" only for 1:1 with Max
        if not store.can_see(conn, "max", kind, where):
            raise HTTPException(403, "Max is not in this conversation")
        return kind, where, thread

    def own_message(mid: str, kind: str, where: str) -> dict:
        try:
            msg = store.get_message(conn, mid)
        except store.NotFound:
            raise HTTPException(404, f"no message {mid}")
        if (msg["where_kind"], msg["where_id"]) != (kind, where):
            raise HTTPException(404, f"no message {mid} in this conversation")
        if msg["author"] != "max":
            raise HTTPException(403, "a bot can only change its own messages")
        return msg

    def thread_of(kind: str, where: str, mid: str | None) -> str | None:
        """Replying to a channel message puts the answer in that message's thread."""
        if kind != "channel" or not mid:
            return None
        try:
            m = store.get_message(conn, mid)
        except store.NotFound:
            raise HTTPException(404, f"no message {mid}")
        if (m["where_kind"], m["where_id"]) != (kind, where):
            raise HTTPException(404, f"no message {mid} in this conversation")
        return m["thread_id"] or m["id"]

    async def create(conv: str, body: dict, reply_to: str | None = None) -> dict:
        kind, where, thread = place(conv)
        if body.get("type") != "typing":  # a typing notice's replyToId doesn't matter
            thread = thread or thread_of(kind, where, reply_to or body.get("replyToId"))
        stream = _stream_info(body)
        personal = kind == "chat" and store.chat(conn, where)["kind"] == "max"
        if stream is not None and not personal:
            raise HTTPException(403, "Streaming is not allowed in this conversation (only in 1:1 chats)")
        sid = (stream or {}).get("streamId") or (body.get("id") if stream is not None else None)
        if body.get("type") == "typing":
            if stream is None:
                await live.send({"type": "typing", "kind": kind, "where": where, "thread_id": thread, "who": "max"}, kind, where)
                return {}
            if not sid:  # first chunk: the answer gets its real message id now (hidden until final)
                sid = store.post(conn, "max", kind, where, "", pending=True)["id"]
            else:
                own_message(sid, kind, where)
            await live.send({"type": "stream", "kind": kind, "where": where, "thread_id": thread,
                             "stream_id": sid, "text": body.get("text", "")}, kind, where)
            return {"id": sid}
        if body.get("type", "message") != "message":
            return {}
        text = body.get("text") or ""
        quote_id = None
        m = QUOTE.match(text)
        if m:
            quote_id, text = m.group(1), text[m.end():]
        for e in body.get("entities") or []:
            if e.get("type") == "quotedReply":
                quote_id = (e.get("quotedReply") or {}).get("messageId") or quote_id
        text = AT.sub(r"@\1", text)
        members = set(store.members_of(conn, kind, where))
        mentions = [p for p in (_pid_of(conn, (e.get("mentioned") or {}).get("id", ""))
                                for e in body.get("entities") or [] if e.get("type") == "mention")
                    if p in members and p != "max"]
        flags = {"ai_label": _ai_generated(body), "feedback": _feedback(body)}
        try:
            if sid:  # the final message of a stream
                own_message(sid, kind, where)
                msg = store.finish(conn, sid, text, attachments=body.get("attachments"), quote_id=quote_id,
                                   mentions=mentions, **flags)
            else:
                msg = store.post(conn, "max", kind, where, text, thread_id=thread, quote_id=quote_id,
                                 mentions=mentions, attachments=body.get("attachments") or None, **flags)
        except store.NotAllowed as e:
            raise HTTPException(400, str(e))
        except store.NotFound as e:
            raise HTTPException(404, str(e))
        await live.send({"type": "message", "message": msg, "stream_id": sid}, kind, where)
        return {"id": msg["id"]}

    @router.post("/v3/conversations/{conv}/activities")
    async def send_to_conversation(conv: str, request: Request):
        return await create(conv, await json_body(request))

    @router.post("/v3/conversations/{conv}/activities/{mid}")
    async def reply_to_activity(conv: str, mid: str, request: Request):
        return await create(conv, await json_body(request), reply_to=mid)

    @router.put("/v3/conversations/{conv}/activities/{mid}")
    async def update_activity(conv: str, mid: str, request: Request):
        body = await json_body(request)
        kind, where, _ = place(conv)
        old = own_message(mid, kind, where)
        text = AT.sub(r"@\1", body.get("text") or "")
        try:
            if old["pending"]:  # the SDK's fallback when a stream times out: the final text as an edit of the stream
                msg = store.finish(conn, mid, text, attachments=body.get("attachments"),
                                   ai_label=_ai_generated(body), feedback=_feedback(body))
                await live.send({"type": "message", "message": msg, "stream_id": mid}, kind, where)
                return {"id": mid}
            msg = store.edit(conn, mid, text, body.get("attachments"))
        except store.NotFound as e:
            raise HTTPException(404, str(e))
        except store.NotAllowed as e:
            raise HTTPException(400, str(e))
        await live.send({"type": "update", "message": msg}, msg["where_kind"], msg["where_id"])
        return {"id": mid}

    @router.delete("/v3/conversations/{conv}/activities/{mid}")
    async def delete_activity(conv: str, mid: str):
        kind, where, _ = place(conv)
        own_message(mid, kind, where)
        msg = store.delete(conn, mid)
        await live.send({"type": "update", "message": msg}, msg["where_kind"], msg["where_id"])
        return {}

    return router


def _ai_generated(body: dict) -> bool:
    """Teams shows "AI generated" when the bot adds this entity (the SDK's add_ai_generated())."""
    return any(e.get("type") == "https://schema.org/Message" and "AIGeneratedContent" in (e.get("additionalType") or [])
               for e in body.get("entities") or [])


def _feedback(body: dict) -> bool:
    """Teams shows 👍/👎 when the bot turns on the feedback loop."""
    data = body.get("channelData") or {}
    return bool(data.get("feedbackLoop")) or data.get("feedbackLoopEnabled") is True


def _stream_info(body: dict) -> dict | None:
    for e in body.get("entities") or []:
        if e.get("type") == "streaminfo":
            return e
    return None


def _exists(conn, kind: str, where: str) -> bool:
    try:
        store.channel(conn, where) if kind == "channel" else store.chat(conn, where)
        return True
    except store.NotFound:
        return False


def _pid_of(conn, teams_id: str) -> str | None:
    if teams_id == BOT_ID:
        return "max"
    for p in store.people(conn):
        if user_id(p["id"]) == teams_id:
            return p["id"]
    return None


def start_delivery(tasks: set, conn, msg: dict, bot_url: str | None, service_url: str) -> None:
    """Fire and forget (the screen must not wait for Max). Keeps a reference so the task isn't lost."""
    if not bot_url or not should_deliver(conn, msg):
        return
    task = asyncio.create_task(deliver(conn, msg, bot_url, service_url))
    tasks.add(task)
    task.add_done_callback(tasks.discard)
