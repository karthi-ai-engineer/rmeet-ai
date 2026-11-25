# 01 - Teams bot messaging: channels, chats, threads, @mentions

Research date: 2026-11-20. Scope: how a Teams bot ("agent" in current Microsoft wording) is installed into and lives in
personal chats, group chats, channels, reply threads and meeting chats, how it is @mentioned, and the exact wire contracts
(HTTP + JSON) between Teams and the bot. Audio/calls are out of scope.

Legend:
- **[V-doc]**: verified against current Microsoft Learn page (URL cited inline, fetched 2026-11-20).
- **[V-src]**: verified against the official Teams SDK for Python source (`microsoft/teams.py`, `main` at commit
  `59359964408dc749923c9529365320efa86e96a2`, 2026-11-09; PyPI latest `microsoft-teams-apps==2.2.1`, 2026-11-10).
- **[COMPOSITE]**: example assembled by us from documented fields; field names/shapes are documented, the exact
  combination/values are illustrative.
- **[UNVERIFIED]**: our best knowledge, not confirmed against a primary source in this research pass.

Note on naming: Microsoft Learn now calls bots "agents" throughout the Teams docs. The wire protocol is unchanged: it is
still the Bot Framework **Activity** protocol over the Bot Connector REST API (`/v3/...`). Learn now calls the Bot
Connector the **"Agent Communication Service (ACS)"**
([connect-agent-without-sdk](https://learn.microsoft.com/en-us/microsoftteams/platform/agents-in-teams/connect-agent-without-sdk)).
Do not confuse this with Azure Communication Services.

---

## 1. Recommended SDK / stack in late 2026

| Stack | Status (2026-11) | Python | Use for Max? |
|---|---|---|---|
| **Teams SDK** (formerly "Teams AI Library" v2), packages `microsoft-teams-apps`, `microsoft-teams-api`, `microsoft-teams-cards`, `microsoft-teams-graph`... | Microsoft's primary toolkit for Teams agents. Python support **GA on 2026-05-01** ([devblog](https://devblogs.microsoft.com/microsoft365dev/python-support-for-the-microsoft-teams-sdk-is-now-generally-available/)). Latest PyPI `2.2.1` (2026-11-10), `requires_python >=3.11,<4.0` [V-src, PyPI]. | Yes, first-class | **Recommended.** Teams-only, Teams-specific APIs (threads/replyChains, mentions, meetings, streaming, targeted messages, RSC). |
| **Microsoft 365 Agents SDK**, packages `microsoft-agents-hosting-core`, `microsoft-agents-activity`, `microsoft-agents-hosting-aiohttp`, `microsoft-agents-hosting-teams`, `microsoft-agents-authentication-msal` | Successor of Bot Framework SDK for multi-channel agents (Copilot, Teams, web chat, etc.). `microsoft-agents-hosting-teams` latest `1.9.0` on PyPI [V: PyPI]. | Yes | Only if Max must also run in M365 Copilot / non-Teams channels. |
| **Bot Framework SDK v4** (`botbuilder-*`) | **Archived.** "Support tickets for the Bot Framework SDK will no longer be serviced as of December 31, 2025." Python `botbuilder-python` repo is archived on GitHub (`archived: true`), 4.17.1 was the last release. [V-doc](https://learn.microsoft.com/en-us/bot-framework/resources-support) | Dead | **No.** |
| **TeamsFx SDK** | Deprecated; community-only support until September 2026 (per search summary of Learn; [UNVERIFIED exact wording]). | n/a | No. |
| **Azure AI Bot Service** (the cloud registration + Bot Connector / ACS) | Still the required infrastructure. **New multi-tenant Azure Bot resources cannot be created after 2025-07-31**; existing ones keep working. New bots: single-tenant or user-assigned managed identity ([abs-quickstart](https://learn.microsoft.com/azure/bot-service/abs-quickstart)) [V-doc via search excerpt]. | n/a | Yes (registration only). |

Microsoft's own guidance (verbatim, [resources-support](https://learn.microsoft.com/en-us/bot-framework/resources-support)):
> "If you are building a collaborative agent designed to work within Microsoft Teams, consider using the Teams SDK. It
> provides Teams-specific APIs, adaptive card support, and built-in AI orchestration for agents that run in the Teams
> environment."

Python Teams SDK hello world (from GA blog, [V-doc]):

```python
from microsoft_teams.apps import App, ActivityContext
from microsoft_teams.api import MessageActivity

app = App()

@app.on_message
async def handle_message(ctx: ActivityContext[MessageActivity]):
   await ctx.send(f"You said: {ctx.activity.text}")

await app.start()
```

SDK facts relevant to the simulator [V-src]:
- Messaging endpoint path default `/api/messages`, port default `3978` (`PORT` env).
- Credentials from `CLIENT_ID`, `CLIENT_SECRET`, `TENANT_ID` (or `MANAGED_IDENTITY_CLIENT_ID`) env vars or `App(client_id=..., ...)`.
- Default outbound service URL `SERVICE_URL` env or `https://smba.trafficmanager.net/teams` (used only for proactive sends
  without a stored serviceUrl).
- Cloud endpoints come from a `CloudEnvironment` dataclass (`PUBLIC`, `US_GOV`, `US_GOV_DOD`, `CHINA`, selectable via
  `CLOUD` env var) and can be overridden with `with_overrides(PUBLIC, login_endpoint=..., openid_metadata_url=..., ...)`
  passed as `App(cloud=...)`. **This is the hook that lets Max point at rmeet-ai without code changes, provided Max reads
  these overrides from config.**
- `DANGEROUSLY_ALLOW_UNAUTHENTICATED_REQUESTS=true` (old name `skip_auth`) disables inbound JWT validation; do NOT rely on
  it, the simulator should sign real JWTs.
- New in 2026: **socket mode** (public preview, only for newly created bots): the agent opens SignalR sockets to
  `https://{amer|emea|apac}.botapi.skype.com/v3/websockets/connect` instead of exposing an HTTPS endpoint
  ([V-doc](https://learn.microsoft.com/en-us/microsoftteams/platform/agents-in-teams/connect-agent-without-sdk)). Out of
  scope for v1 of the simulator; HTTPS delivery is the production recommendation.

---

## 2. Inbound wire protocol (Teams -> bot)

### 2.1 Transport

[V-doc](https://learn.microsoft.com/en-us/microsoftteams/platform/agents-in-teams/connect-agent-without-sdk):
- ACS sends **each activity as an HTTPS `POST` with a JSON Activity body** to the messaging endpoint in the bot
  registration (e.g. `https://max.example.com/api/messages`). Only one messaging endpoint per bot.
- Header `Authorization: Bearer <JWT>` (see section 4). Reject with `401` on failure.
- Extra headers on every request ([V-doc](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/build-conversational-capability)):
  `x-ms-conversation-id` and `x-ms-tenant-id` (empty if not validated).
- Bot response: for `"type": "invoke"`, the HTTP response **is** the invoke response (status + JSON body). For any other
  activity, return `200 OK`. **Respond within 25 seconds.** (Teams SDK auto-200s unhandled events.)
- Do the real work asynchronously and post replies via the REST API (section 3); do not put the reply in the HTTP response
  (except invoke responses).

### 2.2 Activity schema essentials

Fields (from [Connector API reference](https://learn.microsoft.com/en-us/azure/bot-service/rest-api/bot-framework-rest-connector-api-reference)) [V-doc]:
`type`, `id`, `timestamp` (UTC ISO-8601), `localTimestamp`, `localTimezone`, `serviceUrl`, `channelId`, `from`
(ChannelAccount), `conversation` (ConversationAccount), `recipient` (ChannelAccount), `textFormat`
(`plain|markdown|xml`; Teams also uses `extendedmarkdown` for streaming), `text`, `attachments[]`, `attachmentLayout`,
`entities[]`, `channelData`, `replyToId`, `value`, `name`, `action`, `membersAdded[]`, `membersRemoved[]`,
`reactionsAdded[]`, `reactionsRemoved[]`, `locale`, `summary`, `suggestedActions`, `importance`, `deliveryMode`,
`expiration`, `relatesTo`, `topicName`, `code`, `label`, `valueType`.

Activity `type` values: `message`, `contactRelationUpdate`, `conversationUpdate`, `typing`, `endOfConversation`, `event`,
`invoke`, `deleteUserData`, `messageUpdate`, `messageDelete`, `installationUpdate`, `messageReaction`, `suggestion`,
`trace`, `handoff`.

- **ChannelAccount**: `id`, `name`, `aadObjectId`, `role` (`user|bot`).
- **ConversationAccount**: `id`, `name`, `conversationType`, `isGroup`, `tenantId`, `aadObjectId`, `role`.

### 2.3 Teams ID formats (what the simulator must generate)

| Thing | Format | Source |
|---|---|---|
| `channelId` | always `"msteams"` | [V-doc] |
| Bot id | `28:<MicrosoftAppId>` (in `recipient.id`, `membersAdded[].id`, mention `mentioned.id`) | [V-doc] events page: "The agent's `id` is formatted as `28:<MicrosoftAppId>`." |
| User id | `29:<opaque, bot-specific>` (pairwise per bot, "unique to your agent ID and a particular user. You can't reuse the userId between agents") plus `aadObjectId` = Entra object GUID | [V-doc] proactive page |
| Team id | `19:<id>@thread.tacv2` (older: `@thread.skype`). **General channel id == team id.** | [V-doc] get-teams-context |
| Channel id | `19:<32hex>@thread.tacv2` | [V-doc] |
| Channel thread conversation id | `<channelId>;messageid=<rootMessageId>` e.g. `19:0b7f...@thread.tacv2;messageid=1700000000123` | [V-doc] mention example + [V-src] `to_threaded_conversation_id` |
| Group chat id | `19:<id>@thread.v2` | [V-src] chat_info docstring |
| Meeting chat id | `19:meeting_<base64ish>@thread.v2` | [V-doc] participant event |
| 1:1 chat id | `a:<long opaque>` (classic) ; SDK also documents `19:<guid>_<guid>@unq.gbl.spaces` in `channelData.chat.id` | [V-doc], [V-src] |
| Message / activity id | numeric epoch-ms string, e.g. `"1700000000123"`; events use `f:<guid>` style ids | [V-doc] examples |
| `serviceUrl` | regional, e.g. `https://smba.trafficmanager.net/amer/`, `.../emea/`, sometimes with tenant suffix `https://smba.trafficmanager.net/emea/<tenant>/`; global fallback `https://smba.trafficmanager.net/teams/`. GCC: `https://smba.infra.gcc.teams.microsoft.com/teams` | [V-doc] |

Microsoft explicitly says **treat `conversation.id` as opaque** and use `channelData.channel.id` / `channelData.chat.id`
plus `channelData.replyChain.id` as storage keys
([agent-chat-threads](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/conversations/agent-chat-threads), page dated 2026-11-17) [V-doc].

### 2.4 Threads (L1/L2) and the new `channelData.replyChain` (preview, 2026)

[V-doc agent-chat-threads]:
- L1 = top-level message (can be a thread root); L2 = reply in thread (no nesting).
- Where threading is supported (channels, and 1:1 agent chats in preview), **both** L1 and L2 inbound activities carry
  `channelData.replyChain.id` = id of the root (L1) message.
- An inbound activity is L2 if `channelData.replyChain.id` is present and `activity.id != replyChain.id` (for
  `message`/`messageUpdate`/`messageDelete`); for `messageReaction` compare `replyToId`; for message-action invokes
  compare `value.messagePayload.id`.
- Containing chat/channel id: `channelData.chat.id` or `channelData.channel.id`.
- Recommended behaviour: always answer in the thread of the user's message.

### 2.5 @mentions

By default, in group chats and channels **a bot only receives messages in which it is @mentioned**. It does NOT receive
messages where the team/channel is mentioned, nor replies to its own messages without an @mention
([channel-and-group-conversations](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/conversations/channel-and-group-conversations)) [V-doc].
With RSC (section 5) it receives everything except messages authored by other bots.

Mention entity shape [V-doc]:

```json
{
  "type": "mention",
  "mentioned": { "id": "28:<bot-app-id>", "name": "Max" },
  "text": "<at>Max</at>"
}
```

- `text` must match the substring in `activity.text` exactly. Learn examples show both `<at>Max</at>` and
  `<at>@Max</at>`; real Teams traffic for bot mentions is typically `<at>Max</at>` [UNVERIFIED which one is current for
  inbound; simulator should emit `<at>Max</at>` and Max should strip mention text by matching the entity `text`, never by
  regex on the name].
- Teams SDK Python: `ctx.activity.strip_mentions_text().text`; filter entities with `entity.mentioned.id == ctx.activity.recipient.id`.
- Outbound mentions: by `29:` id, by Entra object id, or by UPN; tag mentions use `"mentioned": {"id": "<base64 tag id>", "name": "...", "type": "tag"}` (channels only, throttled 2 msgs/5 s per bot per thread).
- `@everyone` is not supported for bots in group chats.

### 2.6 Full example: channel reply-thread message that @mentions Max [COMPOSITE]

Assembled from documented fields (message example in
[build-conversational-capability](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/build-conversational-capability),
mention example, channelData spec, replyChain fields). IDs are illustrative.

```http
POST /api/messages HTTP/1.1
Host: max.example.com
Authorization: Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6IjEyMyIsInR5cCI6IkpXVCJ9...
Content-Type: application/json; charset=utf-8
x-ms-conversation-id: 19:0b7f32667e064dd9b25d7969801541f4@thread.tacv2;messageid=1763600000000
x-ms-tenant-id: b28fdbfd-2b78-4f93-b0f8-8881793f0f8f
```

```json
{
  "type": "message",
  "id": "1763600123456",
  "timestamp": "2026-11-20T09:15:23.456Z",
  "localTimestamp": "2026-11-20T14:45:23.456+05:30",
  "localTimezone": "Asia/Calcutta",
  "serviceUrl": "https://smba.trafficmanager.net/amer/",
  "channelId": "msteams",
  "from": {
    "id": "29:1ljv6N86roXr5pjPrCJVIz6xHh5QxjI8kFwYb8wBfC7kq2Ktj3Sd",
    "name": "Priya Raman",
    "aadObjectId": "eddfa9d4-346e-4cce-a18f-fa6261ad776b"
  },
  "conversation": {
    "isGroup": true,
    "conversationType": "channel",
    "tenantId": "b28fdbfd-2b78-4f93-b0f8-8881793f0f8f",
    "id": "19:0b7f32667e064dd9b25d7969801541f4@thread.tacv2;messageid=1763600000000"
  },
  "recipient": {
    "id": "28:608cacfd-1cea-40c9-b678-4b93e69bb72b",
    "name": "Max"
  },
  "textFormat": "plain",
  "text": "<at>Max</at> summarize this thread and list the action items",
  "attachments": [
    {
      "contentType": "text/html",
      "content": "<p><span itemtype=\"http://schema.skype.com/Mention\" itemscope=\"\" itemid=\"0\">Max</span>&nbsp;summarize this thread and list the action items</p>"
    }
  ],
  "entities": [
    {
      "type": "mention",
      "mentioned": { "id": "28:608cacfd-1cea-40c9-b678-4b93e69bb72b", "name": "Max" },
      "text": "<at>Max</at>"
    },
    {
      "type": "clientInfo",
      "locale": "en-US",
      "country": "IN",
      "platform": "Web",
      "timezone": "Asia/Calcutta"
    }
  ],
  "channelData": {
    "teamsChannelId": "19:0b7f32667e064dd9b25d7969801541f4@thread.tacv2",
    "teamsTeamId": "19:zFLSDFWsesfzcmKArqKJ65aOXJzsgf462H2wz41@thread.tacv2",
    "channel": { "id": "19:0b7f32667e064dd9b25d7969801541f4@thread.tacv2" },
    "team": {
      "id": "19:zFLSDFWsesfzcmKArqKJ65aOXJzsgf462H2wz41@thread.tacv2",
      "aadGroupId": "f3ec8cd2-e704-4344-8c47-9a3a21d683c0"
    },
    "tenant": { "id": "b28fdbfd-2b78-4f93-b0f8-8881793f0f8f" },
    "replyChain": { "id": "1763600000000" }
  },
  "replyToId": "1763600000000",
  "locale": "en-US"
}
```

Notes:
- `channelData.eventType` is **only** present on conversation-update style events, not on normal messages [V-doc].
- `channelData.team.name` / `channel.name` are only included on rename/create events; do not expect names on messages [V-doc].
- `teamsTeamId`/`teamsChannelId` are deprecated but still sent for compatibility [V-doc].
- The `text/html` attachment carrying the formatted message (mention as `<span itemtype="http://schema.skype.com/Mention" ...>`) is real Teams behaviour [UNVERIFIED exact markup; the existence of a `text/html` attachment is [V-doc]].
- `replyToId` on an inbound L2 message is the root id [UNVERIFIED for all clients; `replyChain.id` is the documented source of truth].
- Personal-chat messages have `conversation.conversationType: "personal"`, no `isGroup`, and `channelData` with `tenant` (and in 2026 possibly `app`, `chat`, `replyChain`).
- Group chats: `conversationType: "groupChat"`, `isGroup: true`, id `19:...@thread.v2`. Meeting chats look like group chats plus `channelData.meeting.id` [V-doc meeting events].

### 2.7 Install / membership events

**Bot added to a team** - `conversationUpdate` [V-doc verbatim from
[subscribe-to-conversation-events](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/conversations/subscribe-to-conversation-events)]:

```json
{
    "type": "conversationUpdate",
    "membersAdded": [
        {
            "id": "28:608cacfd-1cea-40c9-b678-4b93e69bb72b"
        }
    ],
    "timestamp": "2021-12-07T22:34:56.534Z",
    "id": "f:0b9079f4-d4d3-3d8e-b883-798298053c7e",
    "channelId": "msteams",
    "serviceUrl": "https://smba.trafficmanager.net/amer/",
    "from": {
        "id": "29:1ljv6N86roXr5pjPrCJVIz6xHh5QxjI....",
        "aadObjectId": "eddfa9d4-346e-4cce-a18f-fa6261ad776b"
    },
    "conversation": {
        "isGroup": true,
        "conversationType": "channel",
        "tenantId": "b28fdbfd-2b78-4f93-b0f8-8881793f0f8f",
        "id": "19:0b7f32667e064dd9b25d7969801541f4@thread.tacv2",
        "name": "2021 Test Channel"
    },
    "recipient": {
        "id": "28:608cacfd-1cea-40c9-b678-4b93e69bb72b",
        "name": "Test Agent"
    },
    "channelData": {
        "settings": {
            "selectedChannel": {
                "id": "19:0b7f32667e064dd9b25d7969801541f4@thread.tacv2"
            }
        },
        "team": {
            "aadGroupId": "f3ec8cd2-e704-4344-8c47-9a3a21d683c0",
            "name": "TestTeam2022",
            "id": "19:zFLSDFWsesfzcmKArqKJ-65aOXJz@sgf462H2wz41@thread.tacv2"
        },
        "tenant": {
            "id": "b28fdbfd-2b78-4f93-b0f8-8881793f0f8f"
        },
        "source": {
            "name": "message"
        }
    },
    "action": "add"
}
```

- Bot detects "it was me" when a `membersAdded[].id == recipient.id`. When a *user* is added in team context,
  `channelData.eventType` = `teamMemberAdded`; removal = `teamMemberRemoved` [V-doc].
- Other team `conversationUpdate` eventTypes: `channelCreated`, `channelRenamed`, `channelDeleted`, `channelRestored`,
  `teamRenamed`, `teamDeleted`, `teamArchived`, `teamUnarchived`, `teamRestored` (doc JSON shows lowercase `teamrestored`;
  treat case-insensitively) [V-doc].
- 1:1 install: `conversationUpdate` with `membersAdded` = [bot `28:...`, user `29:...`], `conversationType: "personal"`.

**installationUpdate** (preferred way to detect add/remove) [V-doc verbatim, outer duplicated brace in doc removed]:

```json
{
    "type": "installationUpdate",
    "id": "f:816eb23d-bfa1-afa3-dfeb-d2aa338e9541",
    "timestamp": "2021-11-09T04:47:30.91Z",
    "serviceUrl": "https://smba.trafficmanager.net/amer/",
    "channelId": "msteams",
    "from": {
        "id": "29:1ljv6N86roXr5pjPrCJVIz6xHh5QxjI....",
        "aadObjectId": "eddfa9d4-346e-4cce-a18f-fa6261ad776b"
    },
    "recipient": {
        "id": "28:608cacfd-1cea-40c9-b678-4b93e69bb72b",
        "name": "Test Agent"
    },
    "locale": "en-US",
    "entities": [ { "type": "clientInfo", "locale": "en-US" } ],
    "conversation": {
        "isGroup": true,
        "id": "19:0b7f32667e064dd9b25d7969801541f4@thread.tacv2",
        "name": "2021 Test Channel",
        "conversationType": "channel",
        "tenantId": "b28fdbfd-2b78-4f93-b0f8-8881793f0f8f"
    },
    "channelData": {
        "settings": { "selectedChannel": { "id": "19:0b7f32667e064dd9b25d7969801541f4@thread.tacv2" } },
        "channel": { "id": "19:0b7f32667e064dd9b25d7969801541f4@thread.tacv2" },
        "team": {
            "aadGroupId": "da849743-4259-475f-ae7a-4f4b0fb49943",
            "name": "TestTeam2022",
            "id": "19:zFLSDFWsesfzcmKArqKJ-65aOXJz@sgf462H2wz41@thread.tacv2"
        },
        "tenant": { "id": "b28fdbfd-2b78-4f93-b0f8-8881793f0f8f" },
        "source": { "name": "message" }
    },
    "action": "add"
}
```

`action` is `add` or `remove` (also `add-upgrade` / `remove-upgrade` on app upgrade [UNVERIFIED in current docs]).
Both `installationUpdate` and `conversationUpdate(membersAdded)` are sent on install; ordering is not guaranteed
[UNVERIFIED]. After uninstall, bot sends get `403` (`BotNotInConversationRoster`) [V-doc].

### 2.8 Reactions, edits, deletes

**messageReaction** - only for reactions on messages **sent by the bot**; contents of the original message are not
included; `replyToId` = reacted message id. Types: `like`, `heart`, `laugh`, `surprised`, `sad`, `angry` (2026 SDK
accepts any emoji reaction type string) [V-doc]:

```json
{
    "reactionsAdded": [ { "type": "like" } ],
    "type": "messageReaction",
    "timestamp": "2017-10-16T18:45:41.943Z",
    "id": "f:9f78d1f3",
    "channelId": "msteams",
    "serviceUrl": "https://smba.trafficmanager.net/amer-client-ss.msg/",
    "from": {
        "id": "29:1I9Is_Sx0O-Iy2rQ7Xz1lcaPKlO9eqmBRTBuW6XzkFtcjqxTjPaCMij8BVMdBcL9L_RwWNJyAHFQb0TRzXgyQvA",
        "aadObjectId": "c33aafc4-646d-4543-9d4c-abd28e4d2110"
    },
    "conversation": {
        "isGroup": true,
        "conversationType": "channel",
        "id": "19:3629591d4b774aa08cb0887902eee7c1@thread.skype"
    },
    "recipient": { "id": "28:f5d48856-5b42-41a0-8c3a-c5f944b679b0", "name": "SongsuggesterLocal" },
    "channelData": {
        "channel": { "id": "19:3629591d4b774aa08cb0887902eee7c1@thread.skype" },
        "team": { "id": "19:efa9296d959346209fea44151c742e73@thread.skype" },
        "tenant": { "id": "72f988bf-86f1-41af-91ab-2d7cd011db47" }
    },
    "replyToId": "1575667808184",
    "legacy": { "replyToId": "1:19uJ8TZA1cZcms7-2HLOW3pWRF4nSWEoVnRqc0DPa_kY" }
}
```

`reactionsRemoved` is the symmetric form.

**messageUpdate** (user edited/undeleted a message the bot could see): `type: "messageUpdate"`, `channelData.eventType`
`editMessage` or `undeleteMessage`, `id` = edited message id, `text` = new text.
**messageDelete**: `type: "messageDelete"`, `channelData.eventType: "softDeleteMessage"`. Full examples in
[build-conversational-capability](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/build-conversational-capability) [V-doc].

### 2.9 Meeting events

Require RSC in the manifest: `OnlineMeeting.ReadBasic.Chat` (scheduled/private meetings) and/or
`ChannelMeeting.ReadBasic.Group` (channel meetings); the bot must be in the meeting chat
([meeting-apps-apis](https://learn.microsoft.com/en-us/microsoftteams/platform/apps-in-teams-meetings/meeting-apps-apis)) [V-doc].
Start/end events are for scheduled and channel meetings only.

```json
{
  "name": "application/vnd.microsoft.meetingStart",
  "type": "event",
  "timestamp": "2023-02-23T19:34:07.478Z",
  "localTimestamp": "2023-02-23T11:34:07.478-8",
  "channelId": "msteams",
  "serviceUrl": "https://smba.trafficmanager.net/teams/",
  "from": { "id": "user_id" },
  "conversation": { "isGroup": true, "conversationType": "groupchat", "id": "conversation_id" },
  "recipient": { "id": "28:65f50003-e15d-434a-9e14-0fcfeb3d7817" },
  "value": {
    "Id": "meeting_id",
    "JoinUrl": "join_url",
    "Title": "Example meeting",
    "MeetingType": "Scheduled",
    "StartTime": "2023-02-23T19:34:07.478Z",
    "EndTime": null
  },
  "channelData": { "tenant": { "id": "tenant_id" } }
}
```

- `meetingEnd`: same with `"name": "application/vnd.microsoft.meetingEnd"`, `StartTime: null`, `EndTime` set.
- Doc quirks: the Learn JSON has a leading space in `" application/vnd.microsoft.meetingStart"` (typo; the SDK matches
  `application/vnd.microsoft.meetingStart` exactly [V-src]); `conversationType` shown as `groupchat` there vs `groupChat`
  elsewhere; value keys are **PascalCase**. Real traffic also carries `channelData.meeting.id` (listed in the field table).
- Participant events: `application/vnd.microsoft.meetingParticipantJoin` / `...Leave`, `value.members[].user{tenantId,
  objectId,id,name,aadObjectId}` and `value.members[].meeting{inMeeting, role}`; require subscribing in Developer Portal
  ("Meeting event subscriptions") and `OnlineMeetingParticipant.Read.Chat`; scheduled meetings only [V-doc].
- Other event names in SDK: `application/vnd.microsoft.readReceipt` [V-src].

### 2.10 Invokes (Adaptive Card actions, sign-in)

Invoke names handled by the Teams SDK [V-src]: `adaptiveCard/action`, `signin/tokenExchange`, `signin/verifyState`,
`signin/failure`, `task/fetch`, `task/submit`, `message/submitAction`, `message/fetchTask`, `composeExtension/*`,
`config/fetch|submit`, `tab/fetch|submit`, `fileConsent/invoke`, `handoff/action`, `actionableMessage/executeAction`.

`Action.Execute` -> invoke [V-doc](https://learn.microsoft.com/en-us/adaptive-cards/authoring-cards/universal-action-model):

```json
{
  "type": "invoke",
  "name": "adaptiveCard/action",
  "value": {
    "action": { "type": "Action.Execute", "id": "abc", "verb": "def", "data": { } },
    "trigger": "automatic | manual"
  }
}
```

Bot must return HTTP 200 with body:

```json
{ "statusCode": 200, "type": "application/vnd.microsoft.card.adaptive", "value": { "type": "AdaptiveCard", "version": "1.5", "body": [] } }
```

Allowed `type`s: `application/vnd.microsoft.card.adaptive` (replace card), `application/vnd.microsoft.activity.message`
(string toast), `application/vnd.microsoft.error` (400/500), `application/vnd.microsoft.activity.loginRequest` (401,
OAuthCard), `application/vnd.microsoft.error.incorrectAuthCode` (401), `application/vnd.microsoft.error.preconditionFailed` (412).

Legacy `Action.Submit` in Teams arrives as a plain `type: "message"` activity with `value` = the action `data` merged with
input values, `text` absent, and `replyToId` = card message id; Teams SDK detects card responses via
`channelData.source` [UNVERIFIED exact fields beyond `value`/`replyToId`; the agent-chat-threads doc references "Card
button response sent as a message with channelData.source"].

---

## 3. Outbound: how the bot replies (bot -> Teams)

All calls go to `{serviceUrl}` taken **from the inbound activity** (never hard-code), with
`Authorization: Bearer <bot token>` (section 4) and `Content-Type: application/json`.

### 3.1 Endpoint list

Verified against Learn ([connect-agent-without-sdk](https://learn.microsoft.com/en-us/microsoftteams/platform/agents-in-teams/connect-agent-without-sdk),
[Connector API ref](https://learn.microsoft.com/en-us/azure/bot-service/rest-api/bot-framework-rest-connector-api-reference))
and the exact URLs the Python Teams SDK builds [V-src `packages/api/src/microsoft_teams/api/clients/**`]:

| Operation | Method + path | Body -> Response |
|---|---|---|
| Send to conversation (new L1 post, or legacy thread reply when id has `;messageid=`) | `POST /v3/conversations/{conversationId}/activities` | Activity -> `ResourceResponse {"id": "..."}` (201) |
| Reply to activity | `POST /v3/conversations/{conversationId}/activities/{activityId}` | Activity (with `replyToId`) -> `ResourceResponse` |
| **Reply in thread (new, preferred 2026)** | `POST /v3/conversations/{chatOrChannelId}/replyChains/{rootMessageId}` (ids URL-encoded) | Activity -> `ResourceResponse` |
| Update message | `PUT /v3/conversations/{conversationId}/activities/{activityId}` | Activity -> `ResourceResponse` |
| Delete message | `DELETE /v3/conversations/{conversationId}/activities/{activityId}` | - -> status only |
| Targeted (ephemeral, visible to one user) message | `POST /v3/conversations/{id}/activities?isTargetedActivity=true`; update/delete: same `?isTargetedActivity=true` on `/activities/{activityId}`; reply-chain variant `.../replyChains/{root}?isTargetedActivity=true` | [V-src]; manifest `bots[].supportsTargetedMessages: true` [V-src sample] |
| Add / remove reaction (bot reacts) | `PUT` / `DELETE /v3/conversations/{id}/activities/{activityId}/reactions/{reactionType}` | [V-src] |
| Create conversation (proactive 1:1 or new channel post) | `POST /v3/conversations` | `ConversationParameters` -> `ConversationResourceResponse {"id","activityId","serviceUrl"}` |
| Get members | `GET /v3/conversations/{id}/members` | `ChannelAccount[]` |
| Get paged members | `GET /v3/conversations/{id}/pagedMembers?pageSize=&continuationToken=` (SDK uses `pagedMembers`; Learn writes `pagedmembers`; treat case-insensitively) | `{"members": [...], "continuationToken": "..."}`; page size min 50, default 200, max 500; chats ignore paging |
| Get member | `GET /v3/conversations/{id}/members/{memberId}` | `TeamsChannelAccount` |
| Get activity members | `GET /v3/conversations/{id}/activities/{activityId}/members` | `ChannelAccount[]` |
| Team details | `GET /v3/teams/{teamId}` | `{id, name, aadGroupId, ...}` |
| Channel list | `GET /v3/teams/{teamId}/conversations` | `{"conversations": [{id, name}]}`; General channel name is `null` |
| Meeting details | `GET /v1/meetings/{meetingId}` | see [meeting-apps-apis] |
| Meeting participant | `GET /v1/meetings/{meetingId}/participants/{participantId}?tenantId={tenantId}` | `{user{...}, meeting{role,inMeeting}, conversation{...}}` |
| Targeted meeting notification | `POST /v1/meetings/{meetingId}/notification` (needs `OnlineMeetingNotification.Send.Chat`) | |
| Upload attachment | `POST /v3/conversations/{id}/attachments` | (not used by Teams bots in practice) |

Response headers include `X-Correlating-OperationId` [V-doc]. Errors return `ErrorResponse`:
`{"error": {"code": "...", "message": "..."}}` [V-doc].

### 3.2 Reply-in-thread semantics (what the Python SDK actually does) [V-src]

`ctx.send()` / `ctx.reply()` in a **channel** when the inbound message has `channelData.replyChain.id`:
1. `POST {serviceUrl}/v3/conversations/{channelData.channel.id}/replyChains/{replyChain.id}`.
2. If that returns **404**, fall back to `POST {serviceUrl}/v3/conversations/{activity.conversation.id}/activities`
   (where `conversation.id` already contains `;messageid=<root>`, i.e. the legacy thread route).

Without `replyChain`, it posts to `/v3/conversations/{conversation.id}/activities`. In 1:1 chats, the context methods post
L1 unless the inbound message is already L2. `ctx.reply()` additionally stamps a **quoted reply** entity referencing the
inbound message. `app.send(chat_or_channel_id, msg)` = L1 post; `app.reply(chat_or_channel_id, root_id, msg)` = L2 via
`replyChains`.

Thread error contract [V-doc agent-chat-threads]:

| Condition | HTTP | code | message |
|---|---|---|---|
| `chatOrChannelId` is a `;messageid=` id or user id | 400 | `BadArgument` | `conversationId must be a thread id (19:...@...), not a reply-chain id (;messageid=) or a user id; the reply chain is identified by replyChainId` |
| chat/channel missing | 404 | `ConversationNotFound` | `Conversation not found.` |
| root not in chat/channel | 404 | `ActivityNotFoundInConversation` | `Message does not exist in the thread.` |
| root is a targeted message | 400 | `BadArgument` | `Replies are not allowed for Targeted Messages.` |
| chat type without threads | 400 | `BadArgument` | `Reply chains is not allowed in this thread type.` |

### 3.3 Outgoing message examples

Minimal reply (REST, [V-doc]):

```http
POST https://smba.trafficmanager.net/amer/v3/conversations/19%3A0b7f...%40thread.tacv2/replyChains/1763600000000
Authorization: Bearer <bot-token>
Content-Type: application/json

{ "type": "message", "text": "Here is the summary..." }
```
Response `201`: `{"id": "1763600130001"}`.

Typical full outgoing activity the SDK sends [COMPOSITE: SDK sets `from` = bot, `conversation` = ref.conversation]:

```json
{
  "type": "message",
  "from": { "id": "28:608cacfd-1cea-40c9-b678-4b93e69bb72b", "name": "Max" },
  "conversation": { "id": "19:0b7f32667e064dd9b25d7969801541f4@thread.tacv2" },
  "textFormat": "markdown",
  "text": "Hi <at>Priya Raman</at>, 3 action items found:\n\n1. ...",
  "entities": [
    {
      "type": "mention",
      "text": "<at>Priya Raman</at>",
      "mentioned": { "id": "29:1ljv6N86roXr5pjPrCJVIz6xHh5QxjI8kFwYb8wBfC7kq2Ktj3Sd", "name": "Priya Raman" }
    }
  ]
}
```

Typing indicator: `POST .../activities` with `{"type": "typing"}`; the service may answer with an empty body
(SDK handles "Typing activities (non-streaming) answer with an empty body") [V-src].

Update: `PUT .../activities/{activityId}` with `{"type": "message", "text": "This message has been updated"}` ->
`{"id": "{{activityID}}"}`. Bots **cannot** edit/delete users' messages [V-doc].

New channel post via create-conversation (legacy, still valid) [V-doc archived bot-v3 page]:

```json
POST {serviceUrl}/v3/conversations
{
  "activity": { "type": "message", "text": "new conversation" },
  "bot": { "id": "{{botID}}", "name": "{{botName}}" },
  "channelData": {
    "teamsChannelId": "{{channelId}}",
    "teamsTeamId": "{{teamID}}",
    "channel": { "id": "{{channelId}}" },
    "team": { "id": "{{teamID}}" },
    "tenant": { "id": "{{tenantID}}" }
  },
  "isGroup": true,
  "tenantId": "{{tenantID}}"
}
```
Response: `{"id": "{{conversationID}}", "activityId": "{{activityID}}"}` (conversation id is the thread id with
`;messageid=` [UNVERIFIED exact form]).

### 3.4 Streaming (LLM token streaming) [V-doc](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/streaming-ux)

Works in 1:1, group chats, channels, meeting chats with current SDKs (Python `microsoft-teams-apps >= 2.0.15`); not for
proactive messages. Sequence of normal `POST /v3/conversations/{id}/activities` calls:
1. Open: `{"type":"typing","replyToId":"<userMsgId>","text":"Searching...","entities":[{"type":"streaminfo","streamType":"informative","streamSequence":1}]}` -> **201** `{"id":"<streamId>"}`.
2. Updates: `type: typing`, `entities[0]` = `{"type":"streaminfo","streamId":"<streamId>","streamType":"informative"|"streaming","streamSequence":n}`; each `streaming` request carries the **entire accumulated text**; -> **202** `{}`.
3. Close: `{"type":"message","text":"<full>","entities":[{"type":"streaminfo","streamId":"<streamId>","streamType":"final"}]}` (no `streamSequence`).
Rules: 1 request/sec/stream; one open stream per conversation; informative text <= 1000 chars; stream auto-closes 10 min
after first chunk; errors `403 ContentStreamNotAllowed` (various messages incl. `Request streamed content should contain
the previously streamed content`), `400 BadRequest`, `429`, `202 ContentStreamSequenceOrderPreConditionFailed`.
(Doc uses both `streamInfo` and `streaminfo`; SDK sends `streaminfo` [V-src].) The Python SDK also mirrors stream fields
into `channelData.streamId/streamType/streamSequence` [V-src model].

### 3.5 Adaptive Cards

Attachment `contentType: "application/vnd.microsoft.card.adaptive"`, `content` = card JSON [V-doc]. Universal Actions
(`Action.Execute`) need card `version` >= 1.4 (Teams docs say 1.5); wrap actions in `ActionSet`, give `Action.Submit`
fallback. `refresh.userIds` max 60 MRIs.

Minimal card message:

```json
{
  "type": "message",
  "attachments": [
    {
      "contentType": "application/vnd.microsoft.card.adaptive",
      "content": {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.5",
        "body": [
          { "type": "TextBlock", "text": "Meeting summary ready", "weight": "Bolder", "size": "Medium" },
          { "type": "TextBlock", "text": "3 action items, 2 decisions", "wrap": true },
          { "type": "Input.Text", "id": "note", "placeholder": "Add a note" }
        ],
        "actions": [
          {
            "type": "Action.Execute",
            "title": "Post to channel",
            "verb": "postSummary",
            "data": { "summaryId": "s-123" },
            "fallback": { "type": "Action.Submit", "title": "Post to channel", "data": { "summaryId": "s-123" } }
          }
        ]
      }
    }
  ]
}
```

### 3.6 Limits and errors to reproduce

- Message size 100 KB (aim < 80 KB); over -> `413 MessageSizeTooBig` [V-doc].
- Per bot per thread: send 7/1 s, 8/2 s, 60/30 s, 1800/3600 s; get members 14/1 s, 16/2 s, 120/30 s, 3600/3600 s; all bots
  per thread: send 14/1 s, 16/2 s; global 50 RPS per app per tenant; `429` with `Retry-After`; also retry 412, 502, 504
  ([rate-limit](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/rate-limit)) [V-doc].
- Error codes: `400 BadArgument`; `401 BotNotRegistered`; `403 BotDisabledByAdmin`, `BotNotInConversationRoster`,
  `ConversationBlockedByUser`, `ForbiddenOperationException` (proactive to user without personal install),
  `InvalidBotApiHost` (GCC), `NotEnoughPermissions`; `404 ActivityNotFoundInConversation`, `ConversationNotFound`;
  `412 PreconditionFailed`; `413 MessageSizeTooBig`; `429 Throttled`; `500/502 ServiceError`; 503; 504 [V-doc].
- Blocked/uninstalled user: `403` body `{"errorCode":209,"message":"{\n  \"subCode\": \"MessageWritesBlocked\", ...}"}` [V-doc].

---

## 4. Authentication

### 4.1 Teams/ACS -> bot (inbound JWT)

[V-doc connector-auth](https://learn.microsoft.com/en-us/azure/bot-service/rest-api/bot-framework-rest-connector-authentication) +
[V-src `apps/auth/token_validator.py`]:
- OpenID metadata: `GET https://login.botframework.com/v1/.well-known/openidconfiguration` ->
  `{"issuer":"https://api.botframework.com","authorization_endpoint":"https://invalid.botframework.com","jwks_uri":"https://login.botframework.com/v1/.well-known/keys","id_token_signing_alg_values_supported":["RS256"],"token_endpoint_auth_methods_supported":["private_key_jwt"]}`.
- JWKS: `GET https://login.botframework.com/v1/.well-known/keys` (JWK set; each key also has an `endorsements` array of
  channel ids, e.g. `["msteams"]`). Refresh at least every 24 h.
- Checks: Bearer scheme; RS256 signature with a JWKS key (`kid`); `iss == "https://api.botframework.com"`;
  `aud == <bot app id>` (Python SDK also accepts `api://<appId>` and `api://botid-<appId>`); `exp`/`nbf` with 5 min skew;
  `serviceurl` claim must equal `activity.serviceUrl`; endorsement for `channelId` (403 if missing).
- **Python SDK detail:** it does not fetch the metadata document; it derives the JWKS URL by regex-replacing
  `/openidconfiguration$` with `/keys` on `openid_metadata_url`, uses PyJWT `PyJWKClient`, `algorithms=["RS256"]`,
  verifies `iat` too. Simulator must serve keys at `<metadata-base>/keys` and include `kid` in the JWT header.
- Agent 365 / agentic-user traffic may additionally arrive with Entra-issued tokens (`https://login.microsoftonline.com/{tid}/v2.0`
  or `https://sts.windows.net/{tid}/`), validated against `https://login.microsoftonline.com/{tid}/discovery/v2.0/keys` [V-src].

Example Connector->bot token payload (claim names per doc; `serviceurl` claim lower-case [V-src reads `serviceurl`]):

```json
{ "iss": "https://api.botframework.com", "aud": "608cacfd-1cea-40c9-b678-4b93e69bb72b",
  "serviceurl": "https://smba.trafficmanager.net/amer/", "nbf": 1763600000, "exp": 1763603600, "iat": 1763600000 }
```

### 4.2 Bot -> ACS (outbound token)

[V-doc]: client-credentials against Entra:

```http
POST https://login.microsoftonline.com/<tenant-id | botframework.com>/oauth2/v2.0/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&client_id=<app-id>&client_secret=<secret>&scope=https%3A%2F%2Fapi.botframework.com%2F.default
```

Response: `{"token_type":"Bearer","expires_in":3600,"ext_expires_in":3600,"access_token":"eyJ..."}`. Use the app
registration's tenant id for single-tenant, `botframework.com` for multi-tenant. Cache until shortly before expiry.
Resulting token: `aud: https://api.botframework.com`, `appid: <app id>`. Managed identity: IMDS/App Service MSI endpoint
with `resource=https://api.botframework.com`.
Python SDK: `{login_endpoint}/{tenant_id or "botframework.com"}/oauth2/v2.0/token` [V-src]. Agentic-user calls use scope
`https://botapi.skype.com/.default` [V-src `agent_bot_scope`].

### 4.3 Single- vs multi-tenant in 2026

- New Azure Bot resources: **single-tenant** or **user-assigned managed identity** only (multi-tenant creation ended
  2025-07-31; existing ones still work) [V-doc via search excerpt of abs-quickstart].
- A single-tenant Azure Bot can still serve other tenants if its Entra **app registration** is multi-tenant and the app is
  published/installed there; community reports are mixed [UNVERIFIED, forum-only evidence]. For Max (SaaS meeting
  assistant) this needs a dedicated decision; the simulator should support both the tenant-specific and `botframework.com`
  token URLs.
- Teams Developer Portal can also create "Teams-managed" bots; these do **not** support OAuth connections (needed for user
  SSO via token service) [V-doc via Teams SDK user-auth guide].

---

## 5. Proactive messaging and RSC

### 5.1 Proactive

[V-doc send-proactive-messages](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/conversations/send-proactive-messages):
- The app must already be installed in that team/chat/user scope (install via Graph if needed:
  `POST /users/{id}/teamwork/installedApps`, `POST /teams/{id}/installedApps` [V-doc link only]).
- Store from any inbound activity (especially `installationUpdate`): `conversation.id`, `serviceUrl`, `tenantId`,
  user `id`/`aadObjectId`, team/channel ids. Conversation reference fields: `activityId`, `bot`, `channelId`,
  `conversation`, `serviceUrl`, `user`.
- Create 1:1 conversation: `POST {serviceUrl}/v3/conversations` with
  `{"bot":{"id":"28:<appId>","name":"Max"},"members":[{"id":"29:..."}],"channelData":{"tenant":{"id":"<tid>"}}}`
  (members `id` may be the `aadObjectId`; UPN/email not allowed) -> `{"id":"a:1qhN..."}`.
- Global service URLs when none stored: Public `https://smba.trafficmanager.net/teams/`, GCC
  `https://smba.infra.gcc.teams.microsoft.com/teams`, GCCH `https://smba.infra.gov.teams.microsoft.us/teams`, DoD
  `https://smba.infra.dod.teams.microsoft.us/teams`.
- Cannot create new group chats or channels proactively; can start a new channel thread.
- Python: `await app.send(conversation_id, MessageActivityInput(text="..."))`; thread: `await app.reply(channel_id, root_id, "...", service_url=...)`.

### 5.2 RSC: receive all messages without @mention

[V-doc enable-receive-all-chat-messages](https://learn.microsoft.com/en-us/microsoftteams/platform/agents-in-teams/enable-receive-all-chat-messages):
- `ChannelMessage.Read.Group` - receive all user messages in the channels of the team where installed.
- `ChatMessage.Read.Chat` - receive all user messages in the group chat where installed.
- Owner consents at install; messages authored by other bots (incl. Workflows) are never delivered; private/shared channels
  only if the app is explicitly added there; bots cannot post in private channels.

```json
{
  "webApplicationInfo": { "id": "<MICROSOFT-ENTRA-APP-ID>", "resource": "https://RscBasedStoreApp" },
  "authorization": {
    "permissions": {
      "resourceSpecific": [
        { "name": "ChannelMessage.Read.Group", "type": "Application" },
        { "name": "ChatMessage.Read.Chat", "type": "Application" }
      ]
    }
  }
}
```

Other RSC permissions useful for Max ([resource-specific-consent](https://learn.microsoft.com/en-us/microsoftteams/platform/graph-api/rsc/resource-specific-consent)) [V-doc]:
`OnlineMeeting.ReadBasic.Chat` (meeting basics + start/end events), `ChannelMeeting.ReadBasic.Group`,
`OnlineMeetingParticipant.Read.Chat` (participant events, app-only or delegated), `ChannelMeetingParticipant.Read.Group`,
`OnlineMeetingTranscript.Read.Chat`, `OnlineMeetingRecording.Read.Chat`, `ChannelMeetingRecording.Read.Group`,
`OnlineMeetingNotification.Send.Chat`, `ChannelMeetingNotification.Send.Group`, `ChatMember.Read.Chat`,
`TeamMember.Read.Group`, `ChannelSettings.Read.Group`, `ChannelMessage.Send.Group`, `TeamsActivity.Send.{Group,Chat,User}`
(always-consented basics). App-only RSC: manifest >= 1.6 (`authorization.permissions.resourceSpecific` form needs >= 1.12;
<= 1.11 used `webApplicationInfo.applicationPermissions`). Delegated RSC: >= 1.12.

---

## 6. App manifest

- Latest schema listed on Learn: **1.30** (`https://developer.microsoft.com/json-schemas/teams/v1.30/MicrosoftTeams.schema.json`),
  1.29 is the newest in the "GA versions" list; the official Python SDK samples use **1.29**
  ([schema index](https://learn.microsoft.com/en-us/microsoft-365/extensibility/schema/), [V-src sample]).
- Recent agent-related additions: 1.25 `agenticUserTemplates` (Agent 365 / Entra Agent ID), `supportsChannelFeatures`;
  1.27 `agentConnectors` (MCP), bot command `type`/`prompt`; 1.28 `agentSkills`; 1.29 one-turn human-to-agent, compose
  extension `triggers`; 1.23 `bots[].registrationInfo`; 1.24 bot commands limit 12 [V-doc summary of schema page].
- Bot scopes: `personal`, `team`, `groupChat`. **Meeting chats are served by `groupChat` scope**; meeting side panel /
  stage requires `configurableTabs` with `context` such as `meetingChatTab`, `meetingSidePanel`, `meetingStage`
  [UNVERIFIED in this pass; standard pre-2026 schema].
- `webApplicationInfo.resource` for bot SSO: `api://botid-{appId}` (as in SDK sample); for RSC-only, Learn samples use
  `https://RscBasedStoreApp` (any URI works) [V-doc/V-src].
- `validDomains`: your bot host + `*.botframework.com` (SDK sample); `token.botframework.com` needed for OAuth.

Minimal manifest for Max [COMPOSITE: structure from SDK sample + RSC docs; verify against v1.29 schema before upload]:

```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/teams/v1.29/MicrosoftTeams.schema.json",
  "manifestVersion": "1.29",
  "version": "1.0.0",
  "id": "00000000-0000-0000-0000-00000000a001",
  "name": { "short": "Max", "full": "Max - AI meeting assistant" },
  "developer": {
    "name": "Example Corp",
    "websiteUrl": "https://max.example.com",
    "privacyUrl": "https://max.example.com/privacy",
    "termsOfUseUrl": "https://max.example.com/terms"
  },
  "description": {
    "short": "AI meeting assistant for Teams",
    "full": "Max summarizes meetings and threads, tracks action items, and answers questions. Max reads messages in channels and chats where it is installed to provide context; see privacy policy."
  },
  "icons": { "outline": "outline.png", "color": "color.png" },
  "accentColor": "#4F6BED",
  "bots": [
    {
      "botId": "608cacfd-1cea-40c9-b678-4b93e69bb72b",
      "scopes": ["personal", "team", "groupChat"],
      "isNotificationOnly": false,
      "supportsCalling": false,
      "supportsVideo": false,
      "supportsFiles": false,
      "commandLists": [
        {
          "scopes": ["personal", "team", "groupChat"],
          "commands": [
            { "title": "summarize", "description": "Summarize this thread or meeting" },
            { "title": "action items", "description": "List open action items" },
            { "title": "help", "description": "What Max can do" }
          ]
        }
      ]
    }
  ],
  "permissions": ["identity", "messageTeamMembers"],
  "validDomains": ["max.example.com", "*.botframework.com", "token.botframework.com"],
  "webApplicationInfo": {
    "id": "608cacfd-1cea-40c9-b678-4b93e69bb72b",
    "resource": "api://botid-608cacfd-1cea-40c9-b678-4b93e69bb72b"
  },
  "authorization": {
    "permissions": {
      "resourceSpecific": [
        { "name": "ChannelMessage.Read.Group", "type": "Application" },
        { "name": "ChatMessage.Read.Chat", "type": "Application" },
        { "name": "OnlineMeeting.ReadBasic.Chat", "type": "Application" },
        { "name": "ChannelMeeting.ReadBasic.Group", "type": "Application" },
        { "name": "OnlineMeetingParticipant.Read.Chat", "type": "Application" },
        { "name": "OnlineMeetingTranscript.Read.Chat", "type": "Application" }
      ]
    }
  }
}
```

---

## 7. "Agentic" actions a Teams bot can take (high level)

1. **Bot Connector / ACS actions (bot identity, no Graph):** post/reply/update/delete its own messages, threads,
   mentions, cards, reactions, streaming, typing, targeted (ephemeral) messages, roster/team/channel lookup, meeting
   details/participants, in-meeting notifications. Auth: bot token (section 4.2). This is what rmeet-ai must mock first.
2. **Microsoft Graph as the app (app-only):** client-credentials token with scope `https://graph.microsoft.com/.default`.
   With **RSC** the app gets access scoped to the specific team/chat/meeting where it is installed and consented (e.g. read
   channel/chat messages history, read meeting transcripts/recordings, read members) without tenant-wide admin consent.
   Tenant-wide Graph application permissions (e.g. `ChannelMessage.Read.All`, `OnlineMeetingTranscript.Read.All`) need
   admin consent (and some are protected APIs) [UNVERIFIED specifics; to be detailed in a Graph research doc]. Note:
   bots post messages via Bot Connector, not Graph; Graph `POST .../messages` is delegated-only for normal use
   [UNVERIFIED in this pass]. Teams SDK Python exposes `app_graph` (app) and `user_graph` (delegated) clients
   [V-doc GA blog].
3. **Graph on behalf of a user (delegated):** via SSO/OAuth using an **OAuth connection on the Azure Bot** and the Bot
   Framework token service (`https://token.botframework.com`, SDK paths `api/usertoken/GetToken`, `GetAadTokens`,
   `GetTokenStatus`, `SignOut`, `exchange` [V-src]). Flow: bot sends OAuthCard (`application/vnd.microsoft.card.oauth`,
   with `tokenExchangeResource`) -> Teams client silently obtains an Entra token for `api://botid-{appId}` ->
   `signin/tokenExchange` invoke -> bot exchanges via token service (respond 200, or 412 to fall back to sign-in) ->
   `signin/verifyState` for the magic-code/popup path, `signin/failure` on failure. SSO for bots works in personal and group
   chat, **not in channel scope** ([bot-sso-overview](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/authentication/bot-sso-overview)) [V-doc]. Python 2.1+: `graph = app.add_oauth_flow("graph")`, `token = await graph.sign_in(ctx)`.
4. **Agentic users (Agent 365, 2026):** an agent instance can have its own Entra Agent ID "user" identity (manifest
   `agenticUserTemplates`); inbound activities carry the agentic identity in `recipient`, replies are sent *as* that agentic
   user; proactive sends require passing `agentic_identity` ([receiving-sending-messages](https://learn.microsoft.com/en-us/microsoftteams/platform/concepts/agentic-identity/receiving-sending-messages)) [V-doc]. Emerging; not needed for simulator v1.

---

## 8. What our simulator (rmeet-ai) must imitate

Design principle: Max's Teams integration code must run unchanged; only configuration differs. Because every reply goes
to `activity.serviceUrl`, setting `serviceUrl` = `https://<rmeet-ai host>/teams/` in delivered activities redirects all
Connector traffic automatically. The remaining hard-coded URLs (Entra token endpoint, Bot Framework OpenID/JWKS, token
service, Graph) must be overridable in Max via the Teams SDK `CloudEnvironment` (`App(cloud=with_overrides(PUBLIC, ...))`)
plus `SERVICE_URL` / `OAUTH_URL` env vars. Max should load these from config, never patch SDK code.

### 8.1 Identity endpoints (mock Entra + Bot Framework auth)

| Mock | Real equivalent | Behaviour |
|---|---|---|
| `POST {sim}/{tenant}/oauth2/v2.0/token` | `https://login.microsoftonline.com/{tenant or botframework.com}/oauth2/v2.0/token` | form `grant_type=client_credentials`, `client_id`, `client_secret`, `scope=https://api.botframework.com/.default` (also Graph scope). Validate creds against registered bot. Return `{"token_type":"Bearer","expires_in":3600,"ext_expires_in":3600,"access_token":"<RS256 JWT aud=https://api.botframework.com, appid=<appId>, iss=https://sts.windows.net/<tid>/>"}`. Errors as Entra (`400 invalid_client` etc.). |
| `GET {sim}/v1/.well-known/openidconfiguration` | `https://login.botframework.com/v1/.well-known/openidconfiguration` | Exact JSON from 4.1 with `jwks_uri` pointing to sim. |
| `GET {sim}/v1/.well-known/keys` | `https://login.botframework.com/v1/.well-known/keys` | JWKS (RSA, `kid`, `kty`, `n`, `e`, `x5t`, `endorsements:["msteams"]`). Must be at `<metadata path minus /openidconfiguration>/keys` (SDK derives it). |
| Inbound JWT minting | Bot Connector signer | RS256, header `kid`/`x5t`, claims `iss=https://api.botframework.com`, `aud=<appId>`, `serviceurl=<activity.serviceUrl>`, `nbf`, `exp` (~1 h), `iat`. Option to emit bad tokens for negative tests. |

### 8.2 Inbound delivery engine (sim -> Max)

- POST JSON Activity to the registered messaging endpoint (default `http://localhost:3978/api/messages`), headers
  `Authorization`, `Content-Type: application/json; charset=utf-8`, `x-ms-conversation-id`, `x-ms-tenant-id`.
- Timeout 25 s; for `invoke`, read status + JSON body and use it (e.g. replace the card); for others expect 200.
- Generators for: `message` (personal / groupChat / channel L1 / channel L2 / meeting chat), with mention entities,
  `clientInfo` entity, `text/html` attachment, `channelData` (`tenant`, `team`, `channel`, `chat`, `replyChain`,
  `meeting`), `replyToId`; `conversationUpdate` (all eventTypes in 2.7); `installationUpdate` (`add`/`remove`);
  `messageReaction` (`reactionsAdded/Removed`, only for bot-authored messages); `messageUpdate` (`editMessage`,
  `undeleteMessage`); `messageDelete` (`softDeleteMessage`); `event` meetingStart/meetingEnd/participantJoin/Leave;
  `invoke` `adaptiveCard/action`, `signin/tokenExchange`, `signin/verifyState`; `Action.Submit` card-response messages.
- Delivery rules to imitate:
  - Group chat/channel: deliver only if Max is @mentioned, **unless** the installed app declared and was granted
    `ChannelMessage.Read.Group` (channels) / `ChatMessage.Read.Chat` (group chats).
  - Never deliver messages authored by other bots.
  - Personal chat: deliver everything.
  - Do not deliver replies-to-bot without mention (absent RSC).
  - Meeting events only if `OnlineMeeting.ReadBasic.Chat` / `ChannelMeeting.ReadBasic.Group` granted; participant events
    only if subscribed + `OnlineMeetingParticipant.Read.Chat`.
  - On install send `installationUpdate` + `conversationUpdate(membersAdded with 28:<appId>)`; `conversation.id` = the
    selected channel; `channelData.settings.selectedChannel.id`.
- ID generators matching 2.3 (pairwise `29:` user ids per bot, `28:<appId>`, `19:...@thread.tacv2`, `;messageid=`,
  numeric ms message ids, `f:<guid>` event ids, `a:...` 1:1 ids).

### 8.3 Connector REST API (Max -> sim), base `{serviceUrl}` = `{sim}/teams/` (also accept regional paths like `/amer/`)

All endpoints require `Authorization: Bearer` with a sim-issued bot token (`aud=https://api.botframework.com`, matching
`appid`); 401 otherwise.

| Endpoint | Must do |
|---|---|
| `POST /v3/conversations/{id}/activities` | Accept thread ids (`19:...;messageid=R`) -> L2 in thread R; plain `19:...` -> new L1 post; `a:...` -> 1:1. Return 201 `{"id":"<ms id>"}`. Handle `type: typing` (empty/`{}` body, optional) and streaming (`streaminfo` entities: 201 with stream id on open, 202 `{}` on updates, enforce 1/s, accumulate-only, 10 min, final). `?isTargetedActivity=true` targeted messages. |
| `POST /v3/conversations/{id}/activities/{activityId}` | Reply-to-activity; same result as thread reply. |
| `POST /v3/conversations/{chatOrChannelId}/replyChains/{rootId}` | New thread API: URL-decode ids; 400/404 error contract from 3.2 exactly (codes and messages). Optional toggle to return 404 so the SDK's fallback path is exercised. |
| `PUT /v3/conversations/{id}/activities/{activityId}` | Update bot's own message only (else 403); return `{"id": ...}`; emits nothing to Max. |
| `DELETE /v3/conversations/{id}/activities/{activityId}` | Delete bot's own message; 200 empty. |
| `PUT/DELETE /v3/conversations/{id}/activities/{activityId}/reactions/{type}` | Bot reactions. |
| `POST /v3/conversations` | Create 1:1 (`members`, `channelData.tenant`, `bot`) -> `{"id":"a:..."}`; channel post (`isGroup`, `channelData.channel.id`, `activity`) -> `{"id":"<channel>;messageid=<id>","activityId":"<id>"}`; 403 `ForbiddenOperationException` if not installed for that user. |
| `GET /v3/conversations/{id}/members`, `/pagedMembers` (case-insensitive), `/members/{memberId}`, `/activities/{activityId}/members` | Roster with `id`, `name`, `aadObjectId`, `email`, `userPrincipalName`, `givenName`, `surname`, `tenantId`, `userRole`; paging 50..500, default 200, `continuationToken`. |
| `GET /v3/teams/{teamId}`, `GET /v3/teams/{teamId}/conversations` | Team details; channel list (General name `null`, General id == team id). |
| `GET /v1/meetings/{meetingId}`, `GET /v1/meetings/{meetingId}/participants/{participantId}?tenantId=`, `POST /v1/meetings/{meetingId}/notification` | Meeting metadata (shapes in meeting-apps-apis), RSC-gated 403. |

Cross-cutting behaviours:
- Error body `{"error":{"code":"...","message":"..."}}`, header `X-Correlating-OperationId` on every response.
- Rate limits from 3.6 with `429` + `Retry-After`; optional chaos mode for 412/502/503/504.
- Size limit 100 KB -> 413 `MessageSizeTooBig`.
- Installation state: uninstalled/blocked -> 403 `BotNotInConversationRoster` / `MessageWritesBlocked` subCode.
- Mentions in outgoing text: validate `entities[].text` substring exists in `text`; render for the fake UI.
- Card actions: when a simulated user clicks `Action.Execute`, send `adaptiveCard/action` invoke and apply the returned
  card; `Action.Submit` -> `message` with `value`.
- A simple UI or API for test scripts to: create tenants/teams/channels/chats/users, install the app (with RSC grant
  toggles), post user messages (L1/L2, with @mentions), react/edit/delete, start/end meetings, click card buttons, and
  inspect everything the bot posted.

### 8.4 Later / optional mocks

- Bot Framework token service (`OAUTH_URL` override) `api/usertoken/GetToken|GetAadTokens|GetTokenStatus|SignOut|exchange`
  + `signin/tokenExchange` / `signin/verifyState` invokes for SSO testing.
- Microsoft Graph subset for RSC reads (channel/chat messages, meeting transcripts) - separate research doc.
- Socket mode (`/v3/websockets/connect` + SignalR hub `bothub`, frames `SocketReady`/`Activity`/`SocketClosing`) - only if
  Max adopts socket mode.

---

## 9. Open questions / to verify before implementation

1. Exact current inbound mention `text` form (`<at>Max</at>` vs `<at>@Max</at>`) and `text/html` attachment markup -
   capture from a real tenant (dev tenant + ngrok) once.
2. Whether `replyToId` is populated on inbound L2 channel messages in all clients, and whether `channelData.replyChain`
   is already GA for channels (doc says threading capabilities are "in preview").
3. Order of `installationUpdate` vs `conversationUpdate` on install.
4. Exact `POST /v3/conversations` response id format for new channel posts.
5. Single-tenant bot serving external tenants (SaaS distribution) - confirm with Microsoft docs on "Teams Store + single
   tenant bot" before committing the auth model.
6. Manifest 1.30 GA status and meeting-specific manifest pieces (`configurableTabs` contexts) - verify in the meetings doc.

## Sources

- https://learn.microsoft.com/en-us/microsoftteams/platform/concepts/build-and-test/tool-sdk-overview
- https://devblogs.microsoft.com/microsoft365dev/python-support-for-the-microsoft-teams-sdk-is-now-generally-available/
- https://learn.microsoft.com/en-us/bot-framework/resources-support
- https://github.com/microsoft/botbuilder-python (archived)
- https://learn.microsoft.com/en-us/microsoft-365/agents-sdk/bf-migration-guidance
- https://learn.microsoft.com/en-us/microsoft-365/agents-sdk/bf-migration-python
- https://learn.microsoft.com/azure/bot-service/abs-quickstart
- https://learn.microsoft.com/en-us/microsoftteams/platform/agents-in-teams/connect-agent-without-sdk
- https://learn.microsoft.com/en-us/azure/bot-service/rest-api/bot-framework-rest-connector-authentication
- https://learn.microsoft.com/en-us/azure/bot-service/rest-api/bot-framework-rest-connector-api-reference
- https://learn.microsoft.com/en-us/microsoftteams/platform/bots/build-conversational-capability
- https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/conversations/channel-and-group-conversations
- https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/conversations/agent-chat-threads
- https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/conversations/subscribe-to-conversation-events
- https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/conversations/send-proactive-messages
- https://learn.microsoft.com/en-us/microsoftteams/platform/resources/bot-v3/bot-conversations/bots-conv-proactive
- https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/get-teams-context
- https://learn.microsoft.com/en-us/microsoftteams/platform/bots/streaming-ux
- https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/rate-limit
- https://learn.microsoft.com/en-us/microsoftteams/platform/agents-in-teams/enable-receive-all-chat-messages
- https://learn.microsoft.com/en-us/microsoftteams/platform/graph-api/rsc/resource-specific-consent
- https://learn.microsoft.com/en-us/microsoftteams/platform/apps-in-teams-meetings/meeting-apps-apis
- https://learn.microsoft.com/en-us/microsoftteams/platform/task-modules-and-cards/cards/universal-actions-for-adaptive-cards/work-with-universal-actions-for-adaptive-cards
- https://learn.microsoft.com/en-us/adaptive-cards/authoring-cards/universal-action-model
- https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/authentication/bot-sso-overview
- https://microsoft.github.io/teams-sdk/python/in-depth-guides/user-authentication/
- https://learn.microsoft.com/en-us/microsoftteams/platform/concepts/agentic-identity/receiving-sending-messages
- https://learn.microsoft.com/en-us/microsoft-365/extensibility/schema/
- https://github.com/microsoft/teams.py (source: `packages/api/src/microsoft_teams/api/clients/**`, `auth/cloud_environment.py`, `apps/auth/token_validator.py`, `apps/routing/activity_context.py`, `apps/activity_send.py`, `examples/targeted-messages/appPackage/manifest.json`)
- https://pypi.org/project/microsoft-teams-apps/ , https://pypi.org/project/microsoft-agents-hosting-teams/
