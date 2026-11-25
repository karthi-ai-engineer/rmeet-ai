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

import os
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse
from microsoft_teams.api import (Account, AdaptiveCardActionCardResponse, AdaptiveCardActionMessageResponse,
                                  AdaptiveCardInvokeActivity, Attachment, InstalledActivity, MeetingEndEventActivity,
                                  MeetingStartEventActivity, MessageActivity, MessageActivityInput, TypingActivityInput,
                                  UninstalledActivity)
from microsoft_teams.api.auth.cloud_environment import PUBLIC, with_overrides
from microsoft_teams.apps import ActivityContext, App, FastAPIAdapter

import httpx
import jwt

import brain
import conversation
import followups
import meeting_actions
import policies
from agent.clock import OffsetClock
from agent.graph import Deps, build_max_graph, new_request, resume_run, start_run
from agent.actions import action_tools
from agent.models import make_chat_handle
from agent.tools import memory_tools, task_tools
from approvals import CARD, Approvals
from auth import TOKENS
from jobs import JobRunner
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from calling import MeetingCall
from config import CONFIG
from graph_client import GraphClient, GraphError
from knowledge import TeamKnowledge, author_id_of, author_of, html_to_text, read_file
from llm import LLMError
from meetings_sync import parse_vtt, sync_meetings
from store import Store
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
STORE = Store(CONFIG.data_dir / "max.db")        # everything Max remembers (store.py)
SUBS = SubscriptionManager(graph, STORE)

TEAMS_DIR = CONFIG.data_dir / "teams"             # old JSON knowledge files: imported once, then renamed
REFS_FILE = CONFIG.data_dir / "conversation_refs.json"
knowledge: dict[str, TeamKnowledge] = {}          # team (M365 group) id -> knowledge (in memory, backed by STORE)
refs: dict[str, dict] = {}                        # team id -> {channelId, serviceUrl} (backed by STORE)
_tasks: set = set()


def _bg(coro) -> None:
    t = asyncio.create_task(coro)
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


def import_old_files() -> None:
    """One-time move of the old JSON files (knowledge per team, conversation refs) into max.db."""
    for f in sorted(TEAMS_DIR.glob("*.json")) if TEAMS_DIR.exists() else []:
        team_id = json.loads(f.read_text("utf-8"))["teamId"]
        if STORE.team(team_id) is None:
            kb = TeamKnowledge.import_json(STORE, f)
            log.info("Imported %s into the database: %s", f.name, kb.stats)
        f.replace(f.with_suffix(".json.imported"))
    if REFS_FILE.exists():
        for team_id, r in json.loads(REFS_FILE.read_text("utf-8")).items():
            if team_id not in STORE.refs():
                STORE.save_ref(team_id, r["channelId"], r["serviceUrl"])
        REFS_FILE.replace(REFS_FILE.with_suffix(".json.imported"))


CLOCK = OffsetClock()                             # real time (test hooks may shift it in the simulator)
TEST_HOOKS = os.environ.get("MAX_TEST_HOOKS") == "1"


async def post_channel(team_id: str, text: str, mentions: list | None = None, root_id: str | None = None) -> str | None:
    """Proactive post in the team's channel (in a thread when root_id is given), with @mentions by AAD id."""
    ref = refs.get(team_id)
    if not ref:
        raise RuntimeError("no conversation reference for this team (is Max installed?)")
    conv = ref["channelId"] + (f";messageid={root_id}" if root_id else "")
    act = MessageActivityInput(text=text)
    for name, aad in mentions or []:
        act.add_mention(Account(id=aad, name=name), add_text=False)
    sent = await app.send(conv, act, service_url=ref["serviceUrl"])
    kb = load_known(team_id)
    if kb:
        kb.add_message(sent.id, "Max", re.sub(r"</?at>", "", text), root_id)
    return sent.id


RUNNER = JobRunner(STORE, CLOCK, followups.handlers(STORE, CLOCK, post_channel))

# ------------------------------------------------------------------ the agent (Phase 4, LangGraph)
THREAD_BRAIN = os.environ.get("MAX_THREAD_BRAIN", "agent")     # "classic" = the Phase 1-3 one-shot answer
AGENT: dict = {"graph": None, "saver_cm": None, "model": None}
_thread_locks: dict[str, asyncio.Lock] = {}


def toolsets(ctx):
    """Every tool for a run; intake narrows it down (events, policies)."""
    return memory_tools(ctx) + task_tools(
        ctx, on_change=lambda tid: followups.reschedule_task(STORE, ctx.team_id, tid, CLOCK)) + action_tools(ctx)


def _card_activity(card: dict) -> MessageActivityInput:
    return MessageActivityInput().add_attachments(Attachment(content_type=CARD, content=card))


async def post_card(team_id: str, card: dict, root_id: str | None) -> str:
    ref = refs[team_id]
    conv = ref["channelId"] + (f";messageid={root_id}" if root_id else "")
    sent = await app.send(conv, _card_activity(card), service_url=ref["serviceUrl"])
    return sent.id


async def update_card(team_id: str, root_id: str | None, message_id: str, card: dict) -> None:
    ref = refs[team_id]
    conv = ref["channelId"] + (f";messageid={root_id}" if root_id else "")
    await app.api.conversations.update_activity(conv, message_id, _card_activity(card), service_url=ref["serviceUrl"])


APPROVALS = Approvals(STORE, CLOCK, graph, toolsets, post_card, update_card)
RUNNER.handlers["expire_approval"] = APPROVALS.expire_job


async def resume_approval(run_id: str, decision: dict, thread_root: str | None) -> None:
    """A card click (or the expiry job) continues the paused run, one run at a time per thread."""
    if AGENT["graph"] is None:
        return
    lock = _thread_locks.setdefault(thread_root or run_id, asyncio.Lock())
    async with lock:
        try:
            result = await resume_run(AGENT["graph"], run_id, decision)
            call = MEETING_RUNS.get(run_id)       # asked in a meeting: a new card after "Change" -> say so
            if call is not None and not call.finished:
                await meeting_actions.announce_pause(call, result, STORE, APPROVALS, updated=True)
        except Exception as e:  # noqa: BLE001
            log.exception("Resuming run %s failed: %s", run_id, e)


APPROVALS.resume = resume_approval


async def start_agent() -> None:
    if THREAD_BRAIN != "agent":
        log.info("Agent off (MAX_THREAD_BRAIN=%s): thread answers use the classic brain", THREAD_BRAIN)
        return
    try:
        handle = make_chat_handle(source="max")
    except Exception as e:  # no model configured: keep Max working with the classic brain
        log.warning("Agent off (%s): thread answers use the classic brain", e)
        return
    cm = AsyncSqliteSaver.from_conn_string(str(CONFIG.data_dir / "checkpoints.db"))
    saver = await cm.__aenter__()
    AGENT.update(saver_cm=cm, model=handle.model_id,
                 graph=build_max_graph(Deps(STORE, handle, CLOCK, toolsets, post_channel, approvals=APPROVALS,
                                            policy=policies.make_filter(STORE),
                                            extra={"graph": graph, "deliver_meeting": deliver_meeting}), saver))
    log.info("Agent ready: %s (%s), saved runs in checkpoints.db", handle.model_id, handle.provider)


# ------------------------------------------------------------------ actions asked for in a meeting (Phase 5.2)
MEETING_RUNS: dict = {}                            # agent run id -> MeetingCall it was asked in


async def meeting_act(call, speaker: str, speaker_aad: str | None, said: str) -> None:
    """'Max, book a follow-up…' in a call: same agent, tools, policies and approval cards as in the channel."""
    if AGENT["graph"] is None:
        await call.say("I can't do that from the meeting right now. Please ask me in the channel.")
        return
    r = await meeting_actions.run_request(call, speaker, speaker_aad, said, graph=AGENT["graph"], store=STORE,
                                          approvals=APPROVALS, runs=MEETING_RUNS, locks=_thread_locks)
    log.info("Meeting request by %s: %s", speaker, "waiting for approval" if r["paused"] else "answered")


deliver_meeting = meeting_actions.make_deliver(MEETING_RUNS, post_channel)


async def sync_people(team_id: str) -> None:
    """Team members (names, AAD ids, emails, owner role) for @mentions, task owners and approvers."""
    try:
        members = await graph.get_all(f"/teams/{team_id}/members")
    except Exception as e:      # keep what we know
        log.warning("Member sync failed: %s", e)
        return
    for m in members:
        if m.get("displayName"):
            STORE.touch_person(team_id, m["displayName"], m.get("userId"), "person", m.get("email"),
                               "owner" if "owner" in (m.get("roles") or []) else "member")


def load_known(team_id: str) -> TeamKnowledge | None:
    kb = knowledge.get(team_id) or TeamKnowledge.load(STORE, team_id)
    if kb:
        knowledge[team_id] = kb
    return kb


def _save_ref(team_id: str, channel_id: str, service_url: str) -> None:
    if refs.get(team_id) != {"channelId": channel_id, "serviceUrl": service_url}:
        refs[team_id] = {"channelId": channel_id, "serviceUrl": service_url}
        STORE.save_ref(team_id, channel_id, service_url)


async def get_knowledge(team_id: str, channel_id: str, rebuild: bool = False) -> TeamKnowledge:
    kb = None if rebuild else load_known(team_id)
    if kb is None:
        log.info("Reading the channel through Graph (team %s)...", team_id)
        kb = await TeamKnowledge.build(graph, team_id, channel_id, STORE, {})
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
    await sync_people(team_id)
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
        STORE.delete_team(team_id)              # removed from the team: forget everything about it
        log.info("Removed from team %s; deleted everything Max knew about it", team_id)


# ============================================================ meetings + subscriptions
async def sync_team_meetings(kb: TeamKnowledge) -> None:
    try:
        result = await sync_meetings(graph, kb.data["teamId"])
    except Exception as e:       # Graph or network trouble: keep what we know, retry later
        log.warning("Meeting sync failed: %s", e)
        return
    kb.set_meetings(result)
    added = followups.schedule_meeting_reminders(STORE, kb.team_id, kb.data["meetings"], CLOCK)
    log.info("Meetings: %s | access: %s | new reminders: %d", kb.stats, kb.access_problems() or "ok", added)


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
            if tick % 2880 == 0:                       # once a day: forget old duplicate-check keys
                STORE.prune_inbound()
            if tick % 4 == 0:                          # every 2 min: ask SharePoint what changed (delta polling);
                for kb in list(knowledge.values()):    # with Sites.Selected there are no drive notifications
                    if kb.data.get("driveId"):
                        try:
                            await sync_files(kb)
                        except Exception as e:  # noqa: BLE001
                            log.warning("File polling failed: %s", e)
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
    announced = (STORE.team(team_id) or {}).get("announcedProblems")   # the database is the truth (rebuilds race)
    if announced and not now_problems and refs.get(team_id):
        s = kb.stats
        text = (f"Thanks! My meeting access is working now: I've read **{s['meetings']} Teams meetings and "
                f"{s['transcripts']} official transcripts**.")
        sent = await app.send(refs[team_id]["channelId"], text, service_url=refs[team_id]["serviceUrl"])
        kb.add_message(sent.id, "Max", text, None)
        kb.data["announcedProblems"] = []
        kb.save()


async def job_loop() -> None:
    """Runs due jobs (reminders, chases) every few seconds."""
    while True:
        await asyncio.sleep(5)
        try:
            await RUNNER.tick()
        except Exception as e:  # never let the loop die
            log.warning("Job runner error: %s", e)


async def startup_sync() -> None:
    for team_id, kb in list(knowledge.items()):
        await sync_people(team_id)
        followups.schedule_meeting_reminders(STORE, team_id, kb.data.get("meetings", []), CLOCK)


@web.on_event("startup")
async def _start_background() -> None:
    await start_agent()
    _bg(APPROVALS.recover())
    _bg(background_jobs())
    _bg(job_loop())
    _bg(startup_sync())


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
    kb = load_known(team_id)
    if not kb:
        return
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
                first = STORE.first_seen("channel-message", msg_id)   # the bot path may have seen it already
                kb.add_message(msg_id, author, text, root if reply else None,
                               msg.get("createdDateTime", "")[:16].replace("T", " "), author_id_of(msg))
                log.info("Graph: %s %s from %s", "new" if first else "already known", "reply" if reply else "post",
                         author)
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
    asker_id = getattr(act.from_, "aad_object_id", None)
    _save_ref(team_id, channel_id, act.service_url)
    kb = load_known(team_id)
    first = STORE.first_seen("channel-message", act.id)          # Graph notifications deliver it too
    if not first and not act.is_recipient_mentioned():
        return

    if not act.is_recipient_mentioned():
        # Delivered because of RSC (ChannelMessage.Read.Group): keep up to date, don't answer, but notice
        # when someone says one of their deadlines moves (rule below).
        if kb:
            kb.add_message(act.id, asker, raw, root_id, author_id=asker_id)
            maybe_deadline_rule(team_id, root_id, asker, asker_id, raw)
        return

    if not STORE.first_seen("mention", act.id):                  # a redelivered @mention: answer only once
        log.info("Ignored a repeated delivery of message %s", act.id)
        return
    question = plain(act.model_copy().strip_mentions_text().text) or "Hello"
    log.info("@Max from %s: %s", asker, question)
    await ctx.send(TypingActivityInput())
    kb = await get_knowledge(team_id, channel_id)
    kb.add_message(act.id, asker, raw, root_id, author_id=asker_id)
    # Answer Teams at once; the work runs in the background, one request at a time per thread.
    _bg(answer_mention(team_id, channel_id, root_id, asker, asker_id, raw, question))


# Deadline-slip rule: cheap checks in code first (words + the author has open tasks); only then one model run,
# which may only propose a task date change (confirmed on a card by the owner or the manager).
SLIP_WORDS = re.compile(r"\b(need|needs|until|till|push(?:ed)?|mov(?:e|ed|ing)|delay(?:ed)?|postpone(?:d)?|later|"
                        r"extend(?:ed)?|extension|slip(?:s|ped)?|instead)\b", re.IGNORECASE)
DATE_WORDS = re.compile(r"\b(?:mon|tues?|wed(?:nes)?|thu(?:rs)?|fri|sat(?:ur)?|sun)(?:day)?\b|\btomorrow\b|\bnext week\b|"
                        r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
                        re.IGNORECASE)


def maybe_deadline_rule(team_id: str, root_id: str, asker: str, asker_id: str | None, raw: str) -> None:
    if AGENT["graph"] is None or not (SLIP_WORDS.search(raw) and DATE_WORDS.search(raw)):
        return
    person = STORE.person(team_id, asker)
    tasks = STORE.tasks(team_id, "open", person["name"]) if person else []
    if tasks:
        _bg(deadline_rule_run(team_id, root_id, asker, asker_id, raw, tasks))


async def deadline_rule_run(team_id: str, root_id: str, asker: str, asker_id: str | None, raw: str,
                            tasks: list) -> None:
    lock = _thread_locks.setdefault(root_id, asyncio.Lock())
    async with lock:
        req = new_request(STORE, team_id, "deadline-rule", asker, asker_id, root_id,
                          onlyTools=["propose_task_update"], silentIf="NO_CHANGE")
        lst = "\n".join(f"#{t['id']} {t['title']} (due {t['due'] or 'none'})" for t in tasks)
        try:
            await start_run(AGENT["graph"], req,
                            f"{asker} just wrote in the team channel: \"{raw}\"\n\nTheir open tasks:\n{lst}\n\n"
                            "If the message clearly says the deadline of one of these tasks is moving, call "
                            "propose_task_update with that task and the new date (YYYY-MM-DD). Otherwise reply with "
                            "exactly NO_CHANGE and nothing else.")
        except Exception as e:  # noqa: BLE001
            log.warning("Deadline rule failed: %s", e)
            STORE.finish_run(req["runId"], "error", str(e))


async def read_thread(team_id: str, channel_id: str, root_id: str, asker: str, raw: str) -> list[tuple[str, str]]:
    """The thread for context, read through Graph like a real bot would."""
    try:
        root = await graph.message(team_id, channel_id, root_id)
        replies = await graph.replies(team_id, channel_id, root_id)
        return [(author_of(m), html_to_text(m.get("body")))
                for m in [root, *sorted(replies, key=lambda m: m.get("createdDateTime", ""))]]
    except GraphError as e:
        log.warning("Could not read the thread: %s", e)
        return [(asker, raw)]


async def answer_mention(team_id: str, channel_id: str, root_id: str, asker: str, asker_id: str | None, raw: str,
                         question: str) -> None:
    lock = _thread_locks.setdefault(root_id, asyncio.Lock())
    async with lock:
        thread = await read_thread(team_id, channel_id, root_id, asker, raw)
        if AGENT["graph"] is not None:
            req = new_request(STORE, team_id, "mention", asker, asker_id, root_id)
            STORE.audit(req["runId"], team_id, "question", {"from": asker, "text": question})
            convo = "\n".join(f"{a}: {t}" for a, t in thread[-30:])
            earlier = None
            if len(thread) <= 1 and conversation.is_short_reply(question):   # "yes go ahead" as a NEW post
                earlier = conversation.earlier_question(STORE, team_id, asker, root_id, CLOCK.now().timestamp())
                if earlier:
                    STORE.audit(req["runId"], team_id, "context", {"earlier": earlier[:400]})
            try:
                await start_run(AGENT["graph"], req, (earlier + "\n\n" if earlier else "") +
                                f"THE THREAD YOU ARE IN (oldest first):\n{convo}\n\n"
                                f"{asker} just asked you: \"{question}\"")
                log.info("Agent answered in thread %s", root_id)
                return
            except Exception as e:  # the agent failed in an unexpected way: answer the classic way instead
                log.exception("Agent run failed (%s): falling back to the classic answer", e)
                STORE.finish_run(req["runId"], "error", f"agent failure: {e}")
        await classic_answer(team_id, root_id, asker, question, thread)


async def classic_answer(team_id: str, root_id: str, asker: str, question: str, thread: list) -> None:
    """Phase 1-3 brain: the whole team memory + the thread in one model call."""
    kb = load_known(team_id)
    run_id = STORE.start_run(team_id, "mention-classic", asker, root_id)
    status = "ok"
    try:
        answer = await asyncio.to_thread(brain.answer_in_thread, kb.prompt_text(), thread, asker, question)
    except LLMError as e:
        log.error("LLM error: %s", e)
        status = "model-error"
        answer = "Sorry, I couldn't think that through just now (my language model didn't respond). Please try again."
    msg_id = await post_channel(team_id, answer, [], root_id)
    STORE.audit(run_id, team_id, "answer", {"text": answer, "messageId": msg_id})
    STORE.finish_run(run_id, status, summary=answer, model_calls=1)
    log.info("Replied in thread %s (classic)", root_id)


# ===================================================================== approval cards
@app.on_card_action_execute
async def on_card_action(ctx: ActivityContext[AdaptiveCardInvokeActivity]):
    """Approve / Change / Cancel on an approval card (Universal Actions). Answers at once with the updated card;
    the approved work continues in the background."""
    act = ctx.activity
    action = act.value.action
    res = await APPROVALS.on_click(action.verb or "", dict(action.data or {}),
                                   getattr(act.from_, "aad_object_id", None), act.from_.name)
    if "card" in res:
        return AdaptiveCardActionCardResponse(value=res["card"])
    return AdaptiveCardActionMessageResponse(value=res["message"])


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
    kb = load_known(team_id)
    if not kb or not ref:
        log.warning("Not joining: no knowledge for this team yet")
        return
    try:
        if not join_url:                          # channel meetings send JoinUrl = null
            info = await bot_api_get(service_url, f"/v1/meetings/{quote(meeting_id, safe='')}")
            join_url = info["details"]["joinUrl"]
        call = MeetingCall(app, graph, team_id, kb, conversation_id, service_url, title,
                           on_finished=lambda c: calls.pop(c.call_id, None), clock=CLOCK, act=meeting_act)
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


async def join_own_meeting_job(job: dict) -> str | None:
    """Max joins a meeting it organised when it starts (calendar meetings send Max no meetingStart event).
    Graph 404 'not in progress' raises: the job runner tries again a little later (until 20 min late)."""
    p, team_id = job["payload"], job["team_id"]
    ref, kb = refs.get(team_id), load_known(team_id)
    if not ref or not kb:
        return "skipped"
    if any(c.title == p["subject"] and not c.finished for c in calls.values()):
        return "skipped"
    conv = ref["channelId"] + (f";messageid={p['threadRoot']}" if p.get("threadRoot") else "")
    call = MeetingCall(app, graph, team_id, kb, conv, ref["serviceUrl"], p["subject"],
                       on_finished=lambda c: calls.pop(c.call_id, None), clock=CLOCK, act=meeting_act)
    key = f"own:{p['eventId']}"
    pending_calls[key] = call
    try:
        await call.join(p["joinUrl"])
        calls[call.call_id] = call
        log.info("Joined my own meeting '%s'", p["subject"])
        return None
    finally:
        pending_calls.pop(key, None)


RUNNER.handlers["join_own_meeting"] = join_own_meeting_job


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
    return {"ok": True, "db": {"file": STORE.path.name, "schema": STORE.version},
            "teams": {k: {**v.stats, "accessProblems": v.access_problems()} for k, v in knowledge.items()},
            "subscriptions": [{"kind": s["kind"], "resource": s["resource"],
                               "minutesLeft": int((s["expires"] - time.time()) / 60)} for s in SUBS.subs.values()]}


# ===================================================================== Max's admin page (step 4.7)
# http://localhost:3978/admin : who may use which tool, who approves, team time zone, and Max's activity log.
# Only from this machine (or with the MAX_ADMIN_KEY header). In real Teams this becomes a Teams tab with SSO
# limited to team owners.
ADMIN_PAGE = CONFIG.data_dir.parent / "admin.html"


def _admin_ok(request: Request) -> bool:
    key = os.environ.get("MAX_ADMIN_KEY", "")
    if key and request.headers.get("x-max-admin-key") == key:
        return True
    return (request.client.host if request.client else "") in ("127.0.0.1", "::1", "localhost")


def _admin_guard(request: Request) -> None:
    if not _admin_ok(request):
        raise HTTPException(403, "Max's admin page is only available on this machine")


@web.get("/admin")
async def admin_page(request: Request):
    _admin_guard(request)
    return Response(ADMIN_PAGE.read_text(encoding="utf-8"), media_type="text/html; charset=utf-8")


@web.get("/admin/api/state")
async def admin_state(request: Request, team: str | None = None):
    _admin_guard(request)
    teams = [{"id": t, "name": (STORE.team(t) or {}).get("teamName")} for t in STORE.team_ids()]
    team = team or (teams[0]["id"] if teams else None)
    if not team:
        return {"teams": [], "team": None}
    rows = lambda rs: [dict(r) for r in rs]   # noqa: E731
    t = STORE.team(team) or {}
    return {
        "teams": teams, "team": {"id": team, "name": t.get("teamName"), "timeZone": t.get("timeZone") or "UTC"},
        "model": AGENT.get("model") or "classic brain", "now": CLOCK.now().isoformat(),
        "policies": policies.catalog(STORE, team, toolsets, CLOCK, {"graph": graph}),
        "people": rows(STORE.people(team)), "runs": rows(STORE.runs(team, 40)),
        "pending": rows(STORE.pendings(team))[-20:], "tasks": rows(STORE.tasks(team, None)),
        "jobs": [j for j in rows(STORE.jobs(team)) if j["status"] == "pending"][:30],
        "usage": {"runs": len(STORE.runs(team, 10000)), "modelCalls": sum(r["model_calls"] for r in STORE.runs(team, 10000)),
                  "tokens": sum(r["tokens"] for r in STORE.runs(team, 10000)),
                  "costUsd": round(sum(r["cost_usd"] for r in STORE.runs(team, 10000)), 5)}}


@web.get("/admin/api/audit/{run_id}")
async def admin_audit(request: Request, run_id: str):
    _admin_guard(request)
    return [dict(r) for r in STORE.audit_for(run_id)]


@web.post("/admin/api/policy")
async def admin_policy(request: Request):
    _admin_guard(request)
    b = await request.json()
    try:
        return STORE.set_policy(b["team"], b["tag"], b.get("who"), b.get("approvers"), by="admin page")
    except (KeyError, ValueError) as e:
        raise HTTPException(400, str(e))


@web.post("/admin/api/team")
async def admin_team(request: Request):
    _admin_guard(request)
    b = await request.json()
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(b["timeZone"])
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "Unknown time zone (use an IANA name like Asia/Kolkata or Europe/London)")
    STORE.set_team_time_zone(b["team"], b["timeZone"])
    STORE.audit(None, b["team"], "team-setting", {"timeZone": b["timeZone"], "by": "admin page"})
    return {"ok": True}


if TEST_HOOKS:
    # Simulator-only helpers (MAX_TEST_HOOKS=1 is written by simulations/teams/register_app.py; real Teams
    # deployments don't set it): move Max's clock, run due jobs now, feed meeting notes, read Max's state.
    @web.post("/test/clock")
    async def test_clock(request: Request):
        body = await request.json()
        if body.get("reset"):
            CLOCK.reset()
        else:
            CLOCK.set(datetime.fromisoformat(body["now"].replace("Z", "+00:00")))
        return {"now": CLOCK.now().isoformat()}

    @web.post("/test/jobs/run")
    async def test_run_jobs():
        return await RUNNER.tick()

    @web.post("/test/notes")
    async def test_notes(request: Request):
        b = await request.json()
        ids = followups.save_meeting_tasks(STORE, b["teamId"], b["notes"], b["title"], b.get("root"), CLOCK)
        return {"taskIds": ids}

    @web.post("/test/tokens/reset")
    async def test_tokens_reset():
        """Forget cached app tokens (a revoked consent only shows in NEW tokens: real tokens keep their roles
        until they expire, which tests can't wait for)."""
        TOKENS.invalidate(CONFIG.graph_scope)
        return {"ok": True}

    @web.post("/test/sample-card")
    async def test_sample_card(request: Request):
        """Post a sample approval card (Max's real card renderer, no model call) to check how the client shows it."""
        from approvals import card_for
        b = await request.json()
        p = {"id": "sample", "team_id": b["teamId"], "status": "pending", "version": 1, "requester": "Karthi M",
             "requester_aad": None, "decided_by": None, "read_outside": 1, "result": None,
             "expires_at": CLOCK.now().timestamp() + 86400,
             "preview": json.dumps({"kind": "email", "title": "Email for approval", "facts": [
                 ["From", "Max (AI) <max@example.com>"], ["To", "Sample Person <sample@example.com>"],
                 ["Subject", "Sample approval card"], ["Attachments", "sample.xlsx (7 KB)"]],
                 "body": "Hi,\n\nThis is a sample approval card to check how the Teams client shows it.\n\nMax"})}
        owners = [{"name": o["name"], "aad_id": o["aad_id"]} for o in STORE.owners(b["teamId"])]
        msg_id = await post_card(b["teamId"], card_for(p, owners), None)
        return {"messageId": msg_id}

    @web.post("/test/tasks/{task_id}/close")
    async def test_close_task(task_id: int):
        followups.close_task(STORE, task_id)
        return {"ok": True}

    @web.get("/test/state")
    async def test_state(teamId: str):
        rows = lambda rs: [dict(r) for r in rs]   # noqa: E731
        return {"now": CLOCK.now().isoformat(), "tasks": rows(STORE.tasks(teamId, None)),
                "jobs": rows(STORE.jobs(teamId)), "runs": rows(STORE.runs(teamId, 20)),
                "people": rows(STORE.people(teamId)), "pending": rows(STORE.pendings(teamId))}

    @web.get("/test/audit/{run_id}")
    async def test_audit(run_id: str):
        return [dict(r) for r in STORE.audit_for(run_id)]


if __name__ == "__main__":
    import_old_files()
    refs.update(STORE.refs())
    for tid in STORE.team_ids():
        load_known(tid)
    log.info("Max starting on http://localhost:%s  (Microsoft endpoints: login=%s, graph=%s; memory: %s, %d team(s))",
             CONFIG.port, CONFIG.login_endpoint, CONFIG.graph_base_url, STORE.path.name, len(knowledge))
    asyncio.run(app.start(CONFIG.port))
