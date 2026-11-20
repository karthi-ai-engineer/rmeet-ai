"""
Max: AI teammate for Microsoft Teams (its own program).

Built on Microsoft's official Teams SDK for Python. It talks to "Microsoft" only
through the real contracts:
  - Bot Connector: receives activities at /api/messages, replies via the activity's serviceUrl
  - Microsoft Graph: reads channel posts, replies and files (app-only token)
In the simulator those endpoints are rmeet-ai (see max/.env); in production they
are Microsoft's. The code is the same.

Run:  .venv\\Scripts\\python max\\app.py      (listens on http://localhost:3978)
"""

import asyncio
import json
import logging
import re
import time
from urllib.parse import quote

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse
from microsoft_teams.api import (InstalledActivity, MeetingEndEventActivity, MeetingStartEventActivity,
                                  MessageActivity, TypingActivityInput, UninstalledActivity)
from microsoft_teams.api.auth.cloud_environment import PUBLIC, with_overrides
from microsoft_teams.apps import ActivityContext, App, FastAPIAdapter

import httpx
import jwt

import brain
from auth import TOKENS
from calling import MeetingCall
from config import CONFIG
from graph_client import GraphClient, GraphError
from knowledge import TeamKnowledge, author_of, html_to_text, read_file
from llm import LLMError
from meetings_sync import parse_vtt, sync_meetings
from subscriptions import SubscriptionManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [max] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("max")
for noisy in ("httpx", "uvicorn.access"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

if not CONFIG.configured:
    raise SystemExit("max/.env is missing CLIENT_ID / CLIENT_SECRET / TENANT_ID. "
                     "Run: .venv\\Scripts\\python simulations\\teams\\register_app.py")

web = FastAPI(title="Max")
cloud = with_overrides(PUBLIC, login_endpoint=CONFIG.login_endpoint, openid_metadata_url=CONFIG.openid_metadata_url)
# token=TOKENS: standard client-credentials provider (see auth.py) instead of MSAL, which needs https authorities.
app = App(client_id=CONFIG.client_id, token=TOKENS, tenant_id=CONFIG.tenant_id,
          cloud=cloud, http_server_adapter=FastAPIAdapter(app=web))
graph = GraphClient()
SUBS = SubscriptionManager(graph)

TEAMS_DIR = CONFIG.data_dir / "teams"
REFS_FILE = CONFIG.data_dir / "conversation_refs.json"
knowledge: dict[str, TeamKnowledge] = {}          # team (M365 group) id -> knowledge
refs: dict[str, dict] = json.loads(REFS_FILE.read_text("utf-8")) if REFS_FILE.exists() else {}
_tasks: set = set()


def _bg(coro) -> None:
    t = asyncio.create_task(coro)
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


def _kb_path(team_id: str):
    return TEAMS_DIR / f"{team_id}.json"


def _save_ref(team_id: str, channel_id: str, service_url: str) -> None:
    refs[team_id] = {"channelId": channel_id, "serviceUrl": service_url}
    REFS_FILE.parent.mkdir(parents=True, exist_ok=True)
    REFS_FILE.write_text(json.dumps(refs, indent=1), "utf-8")


async def get_knowledge(team_id: str, channel_id: str, rebuild: bool = False) -> TeamKnowledge:
    kb = None if rebuild else (knowledge.get(team_id) or TeamKnowledge.load(_kb_path(team_id)))
    if kb is None:
        log.info("Reading the channel through Graph (team %s)...", team_id)
        kb = await TeamKnowledge.build(graph, team_id, channel_id, _kb_path(team_id), {})
        log.info("Read %s", kb.stats)
    knowledge[team_id] = kb
    return kb


def plain(text: str) -> str:
    return re.sub(r"<at>(.*?)</at>", r"@\1", text or "").strip()


# ==================================================================== install
@app.on_install_add
async def on_install(ctx: ActivityContext[InstalledActivity]):
    cd = ctx.activity.channel_data
    if not cd or not cd.team:
        return                                   # personal / group chat install: nothing to pre-read
    team_id = cd.team.aad_group_id
    channel_id = (cd.channel.id if cd.channel else None) or ctx.activity.conversation.id
    service_url = ctx.activity.service_url
    _save_ref(team_id, channel_id, service_url)
    log.info("Installed in team '%s' (%s)", cd.team.name, team_id)
    _bg(_preread_and_welcome(team_id, channel_id, service_url))


async def _preread_and_welcome(team_id: str, channel_id: str, service_url: str) -> None:
    try:
        kb = await get_knowledge(team_id, channel_id, rebuild=True)
    except GraphError as e:
        log.error("Pre-read failed: %s", e)
        await app.send(channel_id, "Hi team, I'm **Max**. I couldn't read the channel yet "
                                   f"(Graph said: {e.code}). Ask an admin to check my permissions.",
                       service_url=service_url)
        return
    await sync_team_meetings(kb)
    await ensure_subscriptions(kb)
    s = kb.stats
    text = (f"Hi team 👋 I'm **Max**, your AI teammate. I've read this channel: **{s['posts']} posts, "
            f"{s['replies']} replies and {s['files']} files**, plus **{s['meetings']} Teams meetings with "
            f"{s['transcripts']} official transcripts**.\n\n"
            "I stay up to date as you post, reply and upload files. Ask me anything by **@mentioning me** in any "
            "thread, e.g. *@Max what did we decide about the pilot?* I'll also join your meetings and post the notes here.")
    problems = kb.access_problems()
    if problems:
        text += "\n\n**Heads-up for an admin:**\n" + "\n".join(f"- {p}" for p in problems)
    sent = await app.send(channel_id, text, service_url=service_url)
    kb.add_message(sent.id, "Max", text, None)
    kb.data["announcedProblems"] = problems
    kb.save()
    await asyncio.to_thread(brain.warm, kb.prompt_text(), brain.THREAD_RULES)


@app.on_install_remove
async def on_uninstall(ctx: ActivityContext[UninstalledActivity]):
    cd = ctx.activity.channel_data
    if cd and cd.team:
        team_id = cd.team.aad_group_id
        knowledge.pop(team_id, None)
        refs.pop(team_id, None)
        SUBS.forget_team(team_id)               # Graph removes them too (RSC revoked)
        if _kb_path(team_id).exists():
            _kb_path(team_id).unlink()          # removed from the team: forget its data
        log.info("Removed from team %s; deleted its channel knowledge", team_id)


# ============================================================ meetings + subscriptions
async def sync_team_meetings(kb: TeamKnowledge) -> None:
    try:
        result = await sync_meetings(graph, kb.data["teamId"])
    except Exception as e:       # Graph or network trouble: keep what we know, retry later
        log.warning("Meeting sync failed: %s", e)
        return
    kb.set_meetings(result)
    log.info("Meetings: %s | access: %s", kb.stats, kb.access_problems() or "ok")


async def ensure_subscriptions(kb: TeamKnowledge) -> None:
    team = kb.data["teamId"]
    await SUBS.ensure(team, "messages", f"/teams/{team}/channels/{kb.data['channelId']}/messages",
                      "created,updated,deleted")
    if kb.data.get("driveId"):
        await SUBS.ensure(team, "drive", f"/drives/{kb.data['driveId']}/root", "updated")
    for org in sorted({m.get("organizerId") for m in kb.data.get("meetings", []) if m.get("onlineMeetingId")}):
        err = await SUBS.ensure(team, "transcripts", f"users/{org}/onlineMeetings/getAllTranscripts", "created")
        if err:
            log.info("No transcript notifications yet (%s)", err)


async def background_jobs() -> None:
    """Renew subscriptions; re-check meeting access when an admin may have fixed permissions."""
    tick = 0
    while True:
        await asyncio.sleep(30)
        tick += 1
        try:
            await SUBS.renew_due()
            if tick % 3 == 0:
                for team_id, kb in list(knowledge.items()):
                    if not kb.access_problems() and kb.stats["meetings"]:
                        continue
                    before = kb.stats["transcripts"]
                    await sync_team_meetings(kb)
                    await ensure_subscriptions(kb)
                    await announce_access_change(team_id, kb, before)
        except Exception as e:  # never let the loop die
            log.warning("Background job error: %s", e)


async def announce_access_change(team_id: str, kb: TeamKnowledge, transcripts_before: int) -> None:
    now_problems = kb.access_problems()
    if kb.data.get("announcedProblems") and not now_problems and refs.get(team_id):
        s = kb.stats
        text = (f"Thanks! My meeting access is working now: I've read **{s['meetings']} Teams meetings and "
                f"{s['transcripts']} official transcripts**.")
        sent = await app.send(refs[team_id]["channelId"], text, service_url=refs[team_id]["serviceUrl"])
        kb.add_message(sent.id, "Max", text, None)
        kb.data["announcedProblems"] = []
        kb.save()


@web.on_event("startup")
async def _start_background() -> None:
    _bg(background_jobs())


@web.post("/graph/notifications")
async def graph_notifications(request: Request, validationToken: str | None = None):
    if validationToken is not None:                    # subscription validation handshake
        return PlainTextResponse(validationToken)
    body = await request.json()
    for n in body.get("value", []):
        sub = SUBS.get(n.get("subscriptionId", ""), n.get("clientState"))
        if not sub:
            log.warning("Ignored a notification with an unknown subscription or wrong clientState")
            continue
        _bg(handle_notification(sub, n))
    return Response(status_code=202)


@web.post("/graph/lifecycle")
async def graph_lifecycle(request: Request, validationToken: str | None = None):
    if validationToken is not None:
        return PlainTextResponse(validationToken)
    body = await request.json()
    for n in body.get("value", []):
        sub = SUBS.get(n.get("subscriptionId", ""), n.get("clientState"))
        if not sub:
            continue
        event = n.get("lifecycleEvent")
        log.info("Lifecycle event %s for %s subscription", event, sub["kind"])
        if event == "reauthorizationRequired":
            _bg(SUBS.reauthorize(sub))
        elif event == "subscriptionRemoved":
            SUBS.forget(sub["id"])
            _bg(recover_team(sub["teamId"]))
    return Response(status_code=202)


_recovering: set[str] = set()


async def recover_team(team_id: str) -> None:
    """After a subscription was removed: resubscribe, then resync anything we may have missed.
    Several 'subscriptionRemoved' events usually arrive together: run one recovery per team."""
    if team_id in _recovering:
        return
    kb = knowledge.get(team_id)
    ref = refs.get(team_id)
    if not kb or not ref:
        return
    _recovering.add(team_id)
    try:
        await asyncio.sleep(2)                # let the burst of lifecycle events arrive
        kb = await get_knowledge(team_id, ref["channelId"], rebuild=True)
        await sync_team_meetings(kb)
        await ensure_subscriptions(kb)
        log.info("Recovered after subscription removal: %s", kb.stats)
    except Exception as e:
        log.warning("Recovery failed (will retry in the background): %s", e)
    finally:
        _recovering.discard(team_id)


RES_MSG = re.compile(r"messages\('([^']+)'\)(?:/replies\('([^']+)'\))?")
RES_TRANSCRIPT = re.compile(r"users/([^/]+)/onlineMeetings\('([^']+)'\)/transcripts\('([^']+)'\)")


async def handle_notification(sub: dict, n: dict) -> None:
    team_id = sub["teamId"]
    kb = knowledge.get(team_id) or TeamKnowledge.load(_kb_path(team_id))
    if not kb:
        return
    knowledge[team_id] = kb
    change, resource = n.get("changeType"), n.get("resource", "")
    try:
        if sub["kind"] == "messages":
            m = RES_MSG.search(resource)
            if not m:
                return
            root, reply = m.group(1), m.group(2)
            msg_id = reply or root
            if change == "deleted":
                kb.delete_message(msg_id)
                log.info("Graph: message %s deleted", msg_id)
                return
            path = f"/teams/{team_id}/channels/{graph._q(kb.data['channelId'])}/messages/{root}"
            msg = await graph.get(path + (f"/replies/{reply}" if reply else ""))
            text, author = html_to_text(msg.get("body")), author_of(msg)
            if change == "updated" and kb.update_message(msg_id, text):
                log.info("Graph: message %s edited", msg_id)
            else:
                kb.add_message(msg_id, author, text, root if reply else None,
                               msg.get("createdDateTime", "")[:16].replace("T", " "))
                log.info("Graph: new %s from %s", "reply" if reply else "post", author)
        elif sub["kind"] == "drive":
            await sync_files(kb)
        elif sub["kind"] == "transcripts":
            m = RES_TRANSCRIPT.search(resource)
            if not m:
                return
            org, mid, tid = m.groups()
            base = f"/users/{org}/onlineMeetings/{mid}"
            vtt = await graph.get_text(f"{base}/transcripts/{tid}/content", {"$format": "text/vtt"})
            info = None
            if not any(x.get("onlineMeetingId") == mid for x in kb.data.get("meetings", [])):
                om = await graph.get(base)
                info = {"subject": om.get("subject"), "start": om.get("startDateTime", "")[:16].replace("T", " "),
                        "end": om.get("endDateTime", "")[:16].replace("T", " "), "organizerId": org,
                        "joinUrl": om.get("joinWebUrl")}
            meeting = kb.add_transcript(mid, {"id": tid, "created": time.strftime("%Y-%m-%d %H:%M"),
                                              "cues": parse_vtt(vtt)}, info)
            log.info("Graph: new transcript for '%s' (%d lines)", meeting.get("subject"),
                     len(meeting["transcripts"][-1]["cues"]))
    except GraphError as e:
        log.warning("Could not process a %s notification: %s", sub["kind"], e)


async def sync_files(kb: TeamKnowledge) -> None:
    """Drive notification -> ask Graph what changed since our last delta token."""
    try:
        delta = await graph.get(kb.data["driveDelta"]) if kb.data.get("driveDelta") else None
    except GraphError as e:
        if e.status != 410:
            raise
        delta = None                                     # token expired: full resync below
    if delta is None:
        delta = await graph.get(f"/drives/{kb.data['driveId']}/root/delta")
    for item in delta.get("value", []):
        if "deleted" in item:
            kb.remove_file(item["id"])
            log.info("Graph: file removed %s", item["id"])
        elif "file" in item:
            rec = await read_file(graph, kb.data["driveId"], item)
            change = kb.upsert_file(rec)
            log.info("Graph: %s file %s (%d chars)", change, rec["name"], len(rec["text"]))
    kb.data["driveDelta"] = delta.get("@odata.deltaLink", kb.data.get("driveDelta"))
    kb.save()


# ==================================================================== messages
@app.on_message
async def on_message(ctx: ActivityContext[MessageActivity]):
    act = ctx.activity
    cd = act.channel_data
    asker = act.from_.name or "Someone"
    raw = plain(act.text)
    if not cd or not cd.team:
        await ctx.send("Hi! I work inside team channels and meetings. Add me to a team and @mention me in a thread.")
        return
    team_id = cd.team.aad_group_id
    channel_id = cd.channel.id
    root_id = cd.reply_chain.id if cd.reply_chain else act.id
    _save_ref(team_id, channel_id, act.service_url)
    kb = knowledge.get(team_id) or TeamKnowledge.load(_kb_path(team_id))

    if not act.is_recipient_mentioned():
        # Delivered because of RSC (ChannelMessage.Read.Group): just keep up to date, don't answer.
        if kb:
            kb.add_message(act.id, asker, raw, root_id)
        return

    question = plain(act.model_copy().strip_mentions_text().text) or "Hello"
    log.info("@Max from %s: %s", asker, question)
    await ctx.send(TypingActivityInput())
    kb = await get_knowledge(team_id, channel_id)
    kb.add_message(act.id, asker, raw, root_id)

    # The thread for context, read through Graph like a real bot would.
    thread = [(asker, raw)]
    try:
        root = await graph.message(team_id, channel_id, root_id)
        replies = await graph.replies(team_id, channel_id, root_id)
        thread = [(author_of(m), html_to_text(m.get("body")))
                  for m in [root, *sorted(replies, key=lambda m: m.get("createdDateTime", ""))]]
    except GraphError as e:
        log.warning("Could not read the thread: %s", e)

    try:
        answer = await asyncio.to_thread(brain.answer_in_thread, kb.prompt_text(), thread, asker, question)
    except LLMError as e:
        log.error("LLM error: %s", e)
        answer = "Sorry, I couldn't think that through just now (my language model didn't respond). Please try again."
    sent = await ctx.send(answer)                 # goes into the same thread (replyChains API)
    kb.add_message(sent.id, "Max", answer, root_id)
    log.info("Replied in thread %s", root_id)


# ===================================================================== meetings (calling)
# Teams tells Max a meeting started (Bot Connector event). Max looks up the meeting, joins the call through
# Graph (POST /communications/calls), receives call notifications at /api/calling and media over the relay.
calls: dict[str, MeetingCall] = {}               # call id -> MeetingCall
pending_calls: dict[str, MeetingCall] = {}       # meeting id -> MeetingCall (until the call id is known)
_jwks = jwt.PyJWKClient(re.sub(r"/openidconfiguration$", "/keys", CONFIG.openid_metadata_url))


async def bot_api_get(service_url: str, path: str) -> dict:
    """Bot Connector GET with the bot token (e.g. /v1/meetings/{id})."""
    token = await TOKENS.get("https://api.botframework.com/.default")
    async with httpx.AsyncClient(timeout=20) as h:
        r = await h.get(service_url.rstrip("/") + path, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json()


@app.on_meeting_start
async def on_meeting_start(ctx: ActivityContext[MeetingStartEventActivity]):
    act = ctx.activity
    cd = act.channel_data
    meeting_id = act.value.id
    title = act.value.title
    team_id = cd.team.aad_group_id if cd and cd.team else None
    log.info("Meeting started: '%s' (%s)", title, act.value.meeting_type)
    if not team_id:
        return
    _bg(join_meeting(team_id, meeting_id, title, act.value.join_url, act.conversation.id, act.service_url))


async def join_meeting(team_id: str, meeting_id: str, title: str, join_url: str | None, conversation_id: str,
                       service_url: str) -> None:
    ref = refs.get(team_id)
    kb = knowledge.get(team_id) or TeamKnowledge.load(_kb_path(team_id))
    if not kb or not ref:
        log.warning("Not joining: no knowledge for this team yet")
        return
    knowledge[team_id] = kb
    try:
        if not join_url:                          # channel meetings send JoinUrl = null
            info = await bot_api_get(service_url, f"/v1/meetings/{quote(meeting_id, safe='')}")
            join_url = info["details"]["joinUrl"]
        call = MeetingCall(app, graph, team_id, kb, conversation_id, service_url, title,
                           on_finished=lambda c: calls.pop(c.call_id, None))
        pending_calls[meeting_id] = call
        await call.join(join_url)
        calls[call.call_id] = call
    except GraphError as e:
        log.error("Could not join the meeting: %s", e)
        why = ("an admin needs to grant consent for Calls.JoinGroupCall.All and Calls.AccessMedia.All"
               if e.status == 403 else str(e))
        await app.send(conversation_id, f"I couldn't join this meeting's call: {why}.", service_url=service_url)
    except Exception as e:
        log.error("Could not join the meeting: %s", e)
    finally:
        pending_calls.pop(meeting_id, None)


@app.on_meeting_end
async def on_meeting_end(ctx: ActivityContext[MeetingEndEventActivity]):
    log.info("Meeting ended: '%s'", ctx.activity.value.title)
    # The call's 'terminated' notification normally arrives first; this is the safety net.
    for call in list(calls.values()):
        if call.conversation_id == ctx.activity.conversation.id:
            _bg(call.finish())


@web.post("/api/calling")
async def calling_callback(request: Request):
    """Graph call notifications. Signed like Bot Framework traffic: iss api.botframework.com, aud = our app id."""
    auth = request.headers.get("authorization", "")
    try:
        token = auth.split(" ", 1)[1]
        key = _jwks.get_signing_key_from_jwt(token).key
        jwt.decode(token, key, algorithms=["RS256"], audience=CONFIG.client_id, issuer="https://api.botframework.com")
    except Exception:
        log.warning("Rejected a call notification with an invalid token")
        return Response(status_code=401)
    body = await request.json()
    for n in body.get("value", []):
        m = re.search(r"/communications/calls/([^/]+)", n.get("resourceUrl", ""))
        cid = m.group(1) if m else None
        call = calls.get(cid) or next((c for c in pending_calls.values() if c.call_id == cid), None)
        if call is None and cid:
            # The 'establishing' notification can race the POST response: wait briefly for the call id.
            for _ in range(20):
                await asyncio.sleep(0.1)
                call = calls.get(cid)
                if call:
                    break
        if call:
            _bg(call.on_notification(n))
    return Response(status_code=202)


@web.get("/health")
async def health():
    return {"ok": True, "teams": {k: {**v.stats, "accessProblems": v.access_problems()} for k, v in knowledge.items()},
            "subscriptions": [{"kind": s["kind"], "resource": s["resource"],
                               "minutesLeft": int((s["expires"] - time.time()) / 60)} for s in SUBS.subs.values()]}


if __name__ == "__main__":
    for f in TEAMS_DIR.glob("*.json") if TEAMS_DIR.exists() else []:
        kb = TeamKnowledge.load(f)
        if kb:
            knowledge[kb.data["teamId"]] = kb
    log.info("Max starting on http://localhost:%s  (Microsoft endpoints: login=%s, graph=%s)",
             CONFIG.port, CONFIG.login_endpoint, CONFIG.graph_base_url)
    asyncio.run(app.start(CONFIG.port))
