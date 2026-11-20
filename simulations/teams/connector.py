"""
Fake Bot Connector (a.k.a. Agent Communication Service).

1. Delivery (Teams -> bot): builds real-format Activities and POSTs them to the
   bot's messaging endpoint with a signed Connector JWT.
2. REST API (bot -> Teams), base {serviceUrl} = <sim>/teams/ :
     POST   /v3/conversations/{id}/activities
     POST   /v3/conversations/{id}/activities/{activityId}
     POST   /v3/conversations/{channelId}/replyChains/{rootId}
     PUT    /v3/conversations/{id}/activities/{activityId}
     DELETE /v3/conversations/{id}/activities/{activityId}
     GET    /v3/conversations/{id}/members | /pagedMembers
     GET    /v3/teams/{teamId} | /v3/teams/{teamId}/conversations
Contract source: docs/research/teams/01-bot-messaging.md §2, §3, §8.
"""

import json
import re
import threading
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

from httpx_types import Req, Resp, Router
from identity import BOT_AUDIENCE, Identity
from store import CHANNEL_ID, TEAM_GROUP_ID, TEAM_THREAD_ID, TENANT_ID, TeamsStore, iso

MAX_ACTIVITY_BYTES = 100 * 1024
CARD_TYPE = "application/vnd.microsoft.card.adaptive"


class Connector:
    def __init__(self, base_url: str, identity: Identity, store: TeamsStore, notify):
        self.service_url = base_url.rstrip("/") + "/teams/"
        self.identity = identity
        self.store = store
        self.notify = notify          # notify(event_dict) -> UI

    # ================================================================ helpers
    @property
    def app(self) -> dict:
        reg = self.identity.registration
        return {"appId": reg.get("appId", ""), "name": reg.get("botName", "Max")} if reg else {}

    def bot_account(self) -> dict:
        return {"id": f"28:{self.app['appId']}", "name": self.app["name"]}

    def user_account(self, key: str) -> dict:
        u = self.store.users[key]
        return {"id": self.store.pairwise_user_id(key, self.app["appId"]), "name": u["name"],
                "aadObjectId": u["aadObjectId"]}

    def _channel_data(self, root_id: str | None = None, install: bool = False) -> dict:
        cd = {"teamsChannelId": CHANNEL_ID, "teamsTeamId": TEAM_THREAD_ID,
              "channel": {"id": CHANNEL_ID},
              "team": {"id": TEAM_THREAD_ID, "aadGroupId": TEAM_GROUP_ID},
              "tenant": {"id": TENANT_ID}}
        if install:
            cd["settings"] = {"selectedChannel": {"id": CHANNEL_ID}}
            cd["team"]["name"] = self.store.team_name
            cd["source"] = {"name": "message"}
        if root_id:
            cd["replyChain"] = {"id": root_id}
        return cd

    @staticmethod
    def _local_times(ms: int) -> tuple[str, str]:
        utc = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        local = utc.astimezone(timezone(timedelta(hours=5, minutes=30)))
        return iso(ms), local.strftime("%Y-%m-%dT%H:%M:%S.") + f"{local.microsecond // 1000:03d}+05:30"

    # ======================================================= delivery to bot
    def deliver(self, activity: dict) -> None:
        """POST an activity to the bot in the background, like the Connector does."""
        threading.Thread(target=self._deliver, args=(activity,), daemon=True).start()

    def _deliver(self, activity: dict) -> None:
        endpoint = self.identity.registration.get("messagingEndpoint")
        if not endpoint:
            return
        token = self.identity.connector_token_for_bot(self.service_url)
        req = urllib.request.Request(endpoint, data=json.dumps(activity).encode("utf-8"), method="POST", headers={
            "Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8",
            "x-ms-conversation-id": activity.get("conversation", {}).get("id", ""), "x-ms-tenant-id": TENANT_ID,
        })
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                resp.read()
        except urllib.error.HTTPError as e:
            self.notify({"type": "bot_error", "message": f"Max answered HTTP {e.code} to a {activity['type']} activity."})
        except Exception:
            self.notify({"type": "bot_error", "message": "Max is not reachable. Is the Max app running? "
                                                         "(python max/app.py)"})

    def message_activity(self, msg: dict) -> dict:
        """Activity for a channel message posted by a person (L1 root or L2 reply)."""
        root_id = msg["replyToId"] or msg["id"]
        ts, local = self._local_times(msg["createdMs"])
        entities = []
        for m in msg["mentions"]:
            if "app" in m:
                mentioned = self.bot_account()
            else:
                mentioned = {"id": self.store.pairwise_user_id(m["user"], self.app["appId"]), "name": m["mentionText"]}
            entities.append({"type": "mention", "mentioned": mentioned, "text": f"<at>{m['mentionText']}</at>"})
        entities.append({"type": "clientInfo", "locale": "en-US", "country": "IN", "platform": "Web",
                         "timezone": "Asia/Calcutta"})
        html_text = self.store.render_text(msg, "html")
        html_text = re.sub(r'<at id="(\d+)">(.*?)</at>',
                           r'<span itemtype="http://schema.skype.com/Mention" itemscope="" itemid="\1">\2</span>',
                           html_text)
        act = {
            "type": "message", "id": msg["id"], "timestamp": ts, "localTimestamp": local,
            "localTimezone": "Asia/Calcutta", "serviceUrl": self.service_url, "channelId": "msteams",
            "from": self.user_account(msg["author"]["user"]),
            "conversation": {"isGroup": True, "conversationType": "channel", "tenantId": TENANT_ID,
                             "id": f"{CHANNEL_ID};messageid={root_id}"},
            "recipient": self.bot_account(), "textFormat": "plain",
            "text": self.store.render_text(msg, "activity"),
            "attachments": [{"contentType": "text/html", "content": f"<p>{html_text}</p>"}],
            "entities": entities, "channelData": self._channel_data(root_id), "locale": "en-US",
        }
        if msg["replyToId"]:
            act["replyToId"] = msg["replyToId"]
        return act

    def install_activities(self, installer: str, action: str) -> list[dict]:
        now = int(datetime.now(timezone.utc).timestamp() * 1000)
        ts, _ = self._local_times(now)
        conv = {"isGroup": True, "conversationType": "channel", "tenantId": TENANT_ID, "id": CHANNEL_ID,
                "name": "General"}
        base = {"channelId": "msteams", "serviceUrl": self.service_url, "timestamp": ts,
                "from": {k: v for k, v in self.user_account(installer).items() if k != "name"},
                "recipient": self.bot_account(), "conversation": conv, "locale": "en-US",
                "channelData": self._channel_data(install=True)}
        acts = [{**base, "type": "installationUpdate", "id": f"f:{uuid.uuid4()}", "action": action,
                 "entities": [{"type": "clientInfo", "locale": "en-US"}]}]
        if action == "add":
            acts.append({**base, "type": "conversationUpdate", "id": f"f:{uuid.uuid4()}",
                         "membersAdded": [{"id": self.bot_account()["id"]}]})
        return acts

    # ======================================================= UI-side actions
    def user_posts(self, user_key: str, text: str, root_id: str | None) -> dict:
        """A person posts in the channel from the rmeet-ai client."""
        marked, mentions = self.store.parse_user_text(text, self.app or None)
        msg = self.store.add_message({"user": user_key}, marked, mentions, root_id)
        mentioned_bot = any("app" in m for m in mentions)
        # Delivery rule: only @mentions, unless RSC ChannelMessage.Read.Group was granted.
        if self.store.install.get("installed") and (mentioned_bot or self.store.has_rsc("ChannelMessage.Read.Group")):
            self.deliver(self.message_activity(msg))
        return msg

    def meeting_event(self, name: str, meeting: dict, root_id: str, start: bool) -> bool:
        """application/vnd.microsoft.meetingStart|meetingEnd for a channel meeting (needs RSC
        ChannelMeeting.ReadBasic.Group). Channel meetings send JoinUrl = null: the bot calls
        GET {serviceUrl}/v1/meetings/{id} to get it."""
        if not (self.store.install.get("installed") and self.store.has_rsc("ChannelMeeting.ReadBasic.Group")):
            return False
        now = int(datetime.now(timezone.utc).timestamp() * 1000)
        ts, _ = self._local_times(now)
        value = {"Id": meeting["bfMeetingId"], "MeetingType": "ChannelScheduled", "JoinUrl": None,
                 "Title": meeting["title"]}
        value["StartTime" if start else "EndTime"] = ts
        org = self.user_account(meeting["organizer"])
        self.deliver({
            "type": "event", "name": name, "id": f"f:{uuid.uuid4()}", "timestamp": ts, "channelId": "msteams",
            "serviceUrl": self.service_url, "from": {"id": org["id"], "aadObjectId": org["aadObjectId"]},
            "conversation": {"isGroup": True, "conversationType": "channel", "tenantId": TENANT_ID,
                             "id": f"{CHANNEL_ID};messageid={root_id}"},
            "recipient": self.bot_account(), "value": value,
            "channelData": {**self._channel_data(root_id), "meeting": {"id": meeting["bfMeetingId"]}},
        })
        return True

    def install(self, installer: str, rsc: list) -> None:
        self.store.set_installed(True, self.app, rsc)
        for act in self.install_activities(installer, "add"):
            self.deliver(act)

    def uninstall(self, installer: str) -> None:
        acts = self.install_activities(installer, "remove")
        self.store.set_installed(False)
        for act in acts:
            self.deliver(act)

    # ============================================================ REST API
    def routes(self, r: Router) -> None:
        conv = r"/teams/(?:[a-z]+/)?v3/conversations/([^/]+)"
        r.add("POST", conv + r"/activities", self._post_activity)
        r.add("POST", conv + r"/activities/([^/]+)", self._reply_to_activity)
        r.add("POST", conv + r"/replyChains/([^/?]+)", self._reply_chain)
        r.add("PUT", conv + r"/activities/([^/]+)", self._update_activity)
        r.add("DELETE", conv + r"/activities/([^/]+)", self._delete_activity)
        r.add("GET", conv + r"/(?:members|pagedMembers|pagedmembers)", self._members)
        r.add("GET", r"/teams/(?:[a-z]+/)?v3/teams/([^/]+)", self._team)
        r.add("GET", r"/teams/(?:[a-z]+/)?v3/teams/([^/]+)/conversations", self._team_conversations)
        r.add("GET", r"/teams/(?:[a-z]+/)?v1/meetings/([^/?]+)", self._meeting_info)

    def _meeting_info(self, req: Req, meeting_id: str) -> Resp:
        """GET {serviceUrl}/v1/meetings/{meetingId} (RSC ChannelMeeting.ReadBasic.Group / OnlineMeeting.ReadBasic.Chat)."""
        if (g := self._guard(req)):
            return g
        if not (self.store.has_rsc("ChannelMeeting.ReadBasic.Group") or self.store.has_rsc("OnlineMeeting.ReadBasic.Chat")):
            return Resp.error(403, "Forbidden", "The app does not have permission to read meeting details.")
        meetings = getattr(self, "meetings", None)
        m = next((m for m in meetings.meetings.values() if m["bfMeetingId"] == unquote(meeting_id)), None) if meetings else None
        if not m:
            return Resp.error(404, "NotFound", "Meeting not found or expired.")
        org = self.store.users[m["organizer"]]
        return Resp.json(200, {
            "details": {"id": m["bfMeetingId"], "msGraphResourceId": m["onlineMeetingId"],
                        "scheduledStartTime": iso(m["startMs"]), "scheduledEndTime": iso(m["endMs"]),
                        "joinUrl": m["joinUrl"], "title": m["title"], "type": "ChannelScheduled"},
            "conversation": {"isGroup": True, "conversationType": "channel", "id": CHANNEL_ID},
            "organizer": {"id": self.store.pairwise_user_id(m["organizer"], self.app["appId"]),
                          "aadObjectId": org["aadObjectId"], "objectId": org["aadObjectId"], "tenantId": TENANT_ID}})

    def _guard(self, req: Req) -> Resp | None:
        if not self.identity.verify_app_token(req.bearer(), BOT_AUDIENCE):
            return Resp.error(401, "Unauthorized", "Authorization has been denied for this request.")
        if not self.store.install.get("installed"):
            return Resp.error(403, "BotNotInConversationRoster", "The bot is not part of the conversation roster.")
        if len(req.body) > MAX_ACTIVITY_BYTES:
            return Resp.error(413, "MessageSizeTooBig", "Message size too large.")
        return None

    @staticmethod
    def _split(conv_id: str) -> tuple[str, str | None]:
        conv_id = unquote(conv_id)
        if ";messageid=" in conv_id:
            base, root = conv_id.split(";messageid=", 1)
            return base, root
        return conv_id, None

    def _store_bot_activity(self, activity: dict, root_id: str | None) -> Resp:
        typ = activity.get("type", "message")
        if typ == "typing":
            self.notify({"type": "typing", "who": "max", "rootId": root_id})
            return Resp.json(201, {})
        if typ != "message":
            return Resp.json(201, {"id": f"f:{uuid.uuid4()}"})
        text = activity.get("text") or ""
        mentions = []
        for ent in activity.get("entities") or []:
            if ent.get("type") != "mention" or not ent.get("text") or ent["text"] not in text:
                continue
            uid = (ent.get("mentioned") or {}).get("id", "")
            key = self.store.user_by_pairwise(uid, self.app["appId"]) or next(
                (k for k, u in self.store.users.items() if u["aadObjectId"] == uid), None)
            if not key:
                continue
            idx = len(mentions)
            mentions.append({"id": idx, "mentionText": self.store.users[key]["name"], "user": key})
            text = text.replace(ent["text"], f"\u0000{idx}\u0000", 1)
        cards = [a.get("content") for a in activity.get("attachments") or [] if a.get("contentType") == CARD_TYPE]
        try:
            msg = self.store.add_message({"app": self.app["appId"], "name": self.app["name"]}, text, mentions,
                                         root_id, cards=cards, text_format=activity.get("textFormat") or "markdown")
        except KeyError:
            return Resp.error(404, "ConversationNotFound", "Conversation not found.")
        return Resp.json(201, {"id": msg["id"]})

    def _post_activity(self, req: Req, conv_id: str) -> Resp:
        if (g := self._guard(req)):
            return g
        base, root = self._split(conv_id)
        if base != CHANNEL_ID:
            return Resp.error(404, "ConversationNotFound", "Conversation not found.")
        return self._store_bot_activity(req.json(), root)

    def _reply_to_activity(self, req: Req, conv_id: str, activity_id: str) -> Resp:
        if (g := self._guard(req)):
            return g
        base, root = self._split(conv_id)
        target = self.store.find(unquote(activity_id))
        if base != CHANNEL_ID or not target:
            return Resp.error(404, "ConversationNotFound", "Conversation not found.")
        return self._store_bot_activity(req.json(), target["replyToId"] or target["id"])

    def _reply_chain(self, req: Req, channel_id: str, root_id: str) -> Resp:
        if (g := self._guard(req)):
            return g
        channel_id, root_id = unquote(channel_id), unquote(root_id)
        if channel_id != CHANNEL_ID:
            return Resp.error(404, "NotFound", "The chat or channel was not found.")
        if root_id not in self.store.roots:
            return Resp.error(404, "NotFound", "The reply chain root message was not found.")
        return self._store_bot_activity(req.json(), root_id)

    def _own_message(self, activity_id: str):
        msg = self.store.find(unquote(activity_id))
        if not msg:
            return None, Resp.error(404, "ActivityNotFound", "Activity not found.")
        if msg["author"].get("app") != self.app["appId"]:
            return None, Resp.error(403, "Forbidden", "The bot can only modify its own messages.")
        return msg, None

    def _update_activity(self, req: Req, conv_id: str, activity_id: str) -> Resp:
        if (g := self._guard(req)):
            return g
        msg, err = self._own_message(activity_id)
        if err:
            return err
        a = req.json()
        cards = [x.get("content") for x in a.get("attachments") or [] if x.get("contentType") == CARD_TYPE]
        self.store.update_message(msg["id"], a.get("text"), cards if a.get("attachments") is not None else None)
        return Resp.json(200, {"id": msg["id"]})

    def _delete_activity(self, req: Req, conv_id: str, activity_id: str) -> Resp:
        if (g := self._guard(req)):
            return g
        msg, err = self._own_message(activity_id)
        if err:
            return err
        self.store.delete_message(msg["id"])
        return Resp(200, b"", {"X-Correlating-OperationId": str(uuid.uuid4())})

    def _members(self, req: Req, conv_id: str) -> Resp:
        if (g := self._guard(req)):
            return g
        members = [{**self.user_account(k), "email": u["email"], "userPrincipalName": u["email"],
                    "givenName": u["givenName"], "surname": u["surname"], "tenantId": TENANT_ID,
                    "userRole": u["userRole"]} for k, u in self.store.users.items()]
        if "paged" in req.path.lower():
            return Resp.json(200, {"members": members})
        return Resp.json(200, members)

    def _team(self, req: Req, team_id: str) -> Resp:
        if (g := self._guard(req)):
            return g
        if unquote(team_id) != TEAM_THREAD_ID:
            return Resp.error(404, "NotFound", "Team not found.")
        return Resp.json(200, {"id": TEAM_THREAD_ID, "name": self.store.team_name, "aadGroupId": TEAM_GROUP_ID,
                               "tenantId": TENANT_ID, "type": "standard"})

    def _team_conversations(self, req: Req, team_id: str) -> Resp:
        if (g := self._guard(req)):
            return g
        return Resp.json(200, {"conversations": [{"id": CHANNEL_ID, "name": None}]})
