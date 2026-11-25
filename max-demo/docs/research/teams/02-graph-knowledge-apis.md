# 02 - Microsoft Graph APIs Max uses to read and write team knowledge

**Scope:** teams, channels, members, channel messages and replies, channel files (SharePoint/OneDrive), online meetings, transcripts, recordings, AI insights, calendar, change notifications, auth, paging, throttling and errors.
**Purpose:** a contract reference for the `rmeet-ai` simulator. Max's Graph client should be able to switch from the simulator to `https://graph.microsoft.com` with no code changes.
**Researched:** 2026-11-20, against Microsoft Learn (Graph v1.0 unless noted).

## Conventions

- **Citations:** every section cites its sources inline.
- **Verbatim JSON:** "verbatim" means the JSON is copied from a Microsoft Learn example. Arrays may be trimmed to 1-2 items, marked `/* ... */`.
- **Composite JSON:** "COMPOSITE" means we assembled the JSON from documented schemas. It is not a single Microsoft example.
- **UNVERIFIED:** marks anything we could not confirm in an official Microsoft doc.
- **Base URL:** `https://graph.microsoft.com/v1.0` unless stated. Beta is never required for Max's must-have paths.

---

## 0. Key facts for 2025-2026 (read first)

1. **Teams API metering is gone.** "Starting August 25, 2025, the Teams APIs are no longer metered, and no billing configuration is required to use these APIs." Do not append `?model=A` or `?model=B`. The old `graph/teams-licenses` page now redirects to the Graph hub. Source: https://learn.microsoft.com/en-us/graph/metered-api-list
2. **The protected-API request form appears retired.** `https://learn.microsoft.com/en-us/graph/teams-protected-apis` returns 404. No current page for getAllMessages or change notifications mentions protected-API approval. The exact retirement date is UNVERIFIED, so still handle a 403.
3. **A new tenant switch blocks transcripts, and it is OFF by default.** Admins enable it in Teams admin center > Meetings > Meeting settings > *Transcript API access*, or with `Set-CsTeamsMeetingConfiguration -EnableGraphTranscriptAccess $true -EnableAttributedTranscripts $true`. While it is off, every transcript call (including subscription create/renew) returns `403` with `innerError.code = GraphAccessToTranscriptsDisabled`. Speaker-attributed VTT has a separate switch; if that one is off, the call returns `403 SpeakerAttributionNotAllowed`. Source: https://learn.microsoft.com/en-us/microsoftteams/meeting-transcript-api-access (dated 2026-10-20) and https://learn.microsoft.com/en-us/graph/api/calltranscript-get?view=graph-rest-1.0
4. **Graph cannot post channel messages as an app**, except in migration/import mode. On `POST .../messages` the only application permission is `Teamwork.Migrate.All`. Max must therefore post through the **Bot Framework connector** and read through Graph. Source: https://learn.microsoft.com/en-us/graph/api/chatmessage-post?view=graph-rest-1.0
5. **Meeting AI insights are GA in v1.0.** The endpoint is `/v1.0/copilot/users/{id}/onlineMeetings/{id}/aiInsights`. Every user needs a Microsoft 365 Copilot license.
6. **Polling rule.** "If your app polls to see whether a resource has changed, you can only do that once per day." Use change notifications for anything near real time. Source: https://learn.microsoft.com/en-us/graph/api/resources/teams-api-overview

---

## 1. Identifier formats (the simulator must produce realistic IDs)

| Object | Format | Example (from docs) |
|---|---|---|
| Tenant ID | GUID | `2432b57b-0abd-43db-aa7b-16eadd115d34` |
| User ID (Entra object ID) | GUID | `8ea0e38b-efb3-4757-924a-5f94061cf8c2` |
| Team ID | GUID, equal to the M365 group ID | `fbe2bf47-16c8-47cf-b4a5-4b9b187c508b` |
| Channel ID | `19:{32 hex}@thread.tacv2`. Older channels use `@thread.skype`. Shared channels may use a non-hex id. | `19:4a95f7d8db4c4e7fae857bcebe0623e6@thread.tacv2`, `19:LpxShHZZh9utjNcEmUS5aOEP9ASw85OUn05NcWYAhX81@thread.tacv2` |
| Chat ID (1:1) | `19:{userA}_{userB}@unq.gbl.spaces` | `19:8ea0e38b-..._97f62344-...@unq.gbl.spaces` |
| Chat ID (group / meeting chat) | `19:{hex}@thread.v2`, meeting chats `19:meeting_{base64}@thread.v2` | `19:meeting_MGQ4MDQyNTEtNTQ2NS00YjQxLTlkMYzMmY2@thread.v2` |
| Message ID | Epoch milliseconds as a string. It is unique only within its channel or chat. `etag` usually equals the id until the message is edited. | `1616965872395` |
| Team member (conversationMember) ID | Opaque. It is base64 of `{teamId}##{userId}` (our observation; Microsoft says treat it as opaque) | `ZWUwZjVhZTItOGJjNi00YWU1LTg0NjYtN2RhZWViYmZhMDYyIyM3Mzc2MWYwNi0yYWM5LTQ2OWMtOWYxMC0yNzlhOGNjMjY3Zjk=` |
| Drive ID | `b!` followed by base64url | `b!2SInBlQrN0K8-GXMy9qNsPtI5ScW8C5IlZtycoy6ZpJZRRtgE4qVTrE8wrvL0-hd` |
| DriveItem ID | 34-char base32-ish | `01H7CFEKENJSSIUHGADZBKODARINQC5JMD` |
| onlineMeeting ID | Opaque base64 (`MSo...`/`MSp...`). Some examples show `{userId}_19:meeting_...@thread.v2`. | `MSo1N2Y5ZGFjYy03MWJmLTQ3NDMtYjQxMy01M2EdFGkdRWHJlQ` |
| callTranscript ID | Opaque base64 (`MSMjMCMj...`, `VjIjIz...`) | `MSMjMCMjNzU3ODc2ZDYtOTcwMi00MDhkLWFkNDItOTE2ZDNmZjkwZGY4` |
| Event ID | Exchange base64 (`AAMk...`). It changes when the event moves; send `Prefer: IdType="ImmutableId"` for a stable ID. | `AAMkAGI1AAAt8AHjAAA=` |
| Subscription ID | GUID | `7f105c7d-2dc5-4530-97cd-4e7ae6534c07` |

Path encoding: channel IDs contain `:` and `@` and appear raw in Graph paths, for example `/teams/{guid}/channels/19:abc@thread.tacv2/messages`. `@odata.context` URL-encodes them as `19%3A...%40thread.tacv2`. The simulator must accept both the raw and the percent-encoded forms.

---

## 2. Teams, channels, members

### 2.1 `GET /teams/{team-id}`
Source: https://learn.microsoft.com/en-us/graph/api/team-get?view=graph-rest-1.0

- Supports `$select` and `$expand`.
- Permissions:
  - Delegated: `Team.ReadBasic.All` (least).
  - Application: **`TeamSettings.Read.Group` (RSC, least)**, then `TeamSettings.ReadWrite.Group`, `Team.ReadBasic.All`, `TeamSettings.Read.All`, and others.
  - `Group.*` and `Directory.*` are supported for backward compatibility only.

Verbatim response (the doc example is shortened; real responses also include `id`, `displayName`, `description`, `internalId`, `webUrl`, `visibility`, `tenantId`, `createdDateTime`, `specialization`, `classification`; UNVERIFIED example values):

```json
{
  "isArchived": false,
  "memberSettings": {
    "allowCreateUpdateChannels": true,
    "allowDeleteChannels": true,
    "allowAddRemoveApps": true,
    "allowCreateUpdateRemoveTabs": true,
    "allowCreateUpdateRemoveConnectors": true
  },
  "guestSettings": { "allowCreateUpdateChannels": true, "allowDeleteChannels": true },
  "messagingSettings": {
    "allowUserEditMessages": true,
    "allowUserDeleteMessages": true,
    "allowOwnerDeleteMessages": true,
    "allowTeamMentions": true,
    "allowChannelMentions": true
  },
  "funSettings": { "allowGiphy": true, "giphyContentRating": "strict", "allowStickersAndMemes": true, "allowCustomMemes": true },
  "discoverySettings": { "showInTeamsSearchAndSuggestions": true },
  "summary": { "ownersCount": 2, "membersCount": 3, "guestsCount": 4 }
}
```

Simulator: return `id`, `displayName`, `description`, `tenantId`, `webUrl` (`https://teams.microsoft.com/l/team/19%3A...%40thread.tacv2/conversations?groupId={id}&tenantId={tid}`; format UNVERIFIED), `isArchived`, `visibility`, plus the settings blocks above.

### 2.2 `GET /teams/{team-id}/channels`
Source: https://learn.microsoft.com/en-us/graph/api/channel-list?view=graph-rest-1.0

- Supports `$filter` (for example `$filter=membershipType eq 'private'`) and `$select`.
- The `email` property is expensive to populate; `$select` it away.
- Members can't see private or shared channels they don't belong to.
- Known issue: `layoutType` returns `null` in lists.
- Permissions:
  - Delegated: `Channel.ReadBasic.All`.
  - Application: **`ChannelSettings.Read.Group` (RSC, least)**, `Channel.ReadBasic.All`, `ChannelSettings.Read.All`, and others.
- Pages with `@odata.nextLink`.

Verbatim (Example 3, shared channel):

```json
{
    "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#teams('6a720ba5-7373-463b-bc9f-4cd04b5c6742')/channels",
    "@odata.count": 1,
    "value": [
        {
            "id": "19:LpxShHZZh9utjNcEmUS5aOEP9ASw85OUn05NcWYAhX81@thread.tacv2",
            "createdDateTime": null,
            "displayName": "shared channel-01",
            "description": "this is the shared channel description",
            "isFavoriteByDefault": null,
            "email": "",
            "webUrl": "https://teams.microsoft.com/l/channel/19%3ALpxShHZZh9utjNcEmUS5aOEP9ASw85OUn05NcWYAhX81%40thread.tacv2/shared%20channel-01?groupId=6a720ba5-7373-463b-bc9f-4cd04b5c6742&tenantId=df81db53-c7e2-418a-8803-0e68d4b88607",
            "membershipType": "shared",
            "layoutType": null,
            "moderationSettings": null,
            "isArchived": false
        }
    ]
}
```

Channel resource notes (https://learn.microsoft.com/en-us/graph/api/resources/channel?view=graph-rest-1.0):

- `membershipType` is one of `standard`, `private`, `unknownFutureValue`, `shared`. `shared` is returned only with `Prefer: include-unknown-enum-members`.
- `tenantId` is a property.
- `webUrl` is opaque.
- `GET /teams/{id}/channels/{id}` has the same permissions. Its `summary` property is returned only when you `$select` it.

### 2.3 `GET /teams/{team-id}/members`
Source: https://learn.microsoft.com/en-us/graph/api/team-list-members?view=graph-rest-1.0

- Supports `$filter`, `$select`, `$top`. Default page size is 100, max 999.
- Filter example: `?$filter=(microsoft.graph.aadUserConversationMember/userId eq '73761f06-...')`.
- Permissions:
  - Delegated: `TeamMember.Read.All`.
  - Application: **`TeamMember.Read.Group` (RSC, least)**, `TeamMember.Read.All`, `TeamMember.ReadWrite.All`.
- Known issue: returns 401 for newly created tenants.

Verbatim:

```json
{
    "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#teams('ee0f5ae2-8bc6-4ae5-8466-7daeebbfa062')/members",
    "@odata.count": 3,
    "value": [
        {
            "@odata.type": "#microsoft.graph.aadUserConversationMember",
            "id": "ZWUwZjVhZTItOGJjNi00YWU1LTg0NjYtN2RhZWViYmZhMDYyIyM3Mzc2MWYwNi0yYWM5LTQ2OWMtOWYxMC0yNzlhOGNjMjY3Zjk=",
            "roles": [],
            "displayName": "Adele Vance",
            "userId": "73761f06-2ac9-469c-9f10-279a8cc267f9",
            "email": "AdeleV@contoso.com"
        },
        {
            "@odata.type": "#microsoft.graph.aadUserConversationMember",
            "id": "ZWUwZjVhZTItOGJjNi00YWU1LTg0NjYtN2RhZWViYmZhMDYyIyM1OThlZmNkNC1lNTQ5LTQwMmEtOTYwMi0wYjUwMjAxZmFlYmU=",
            "roles": ["owner"],
            "displayName": "MOD Administrator",
            "userId": "598efcd4-e549-402a-9602-0b50201faebe",
            "email": "admin@contoso.com"
        }
    ]
}
```

Notes:
- `roles` is `[]` for ordinary members, `["owner"]` for owners, `["guest"]` for guests.
- The aadUserConversationMember resource also has `tenantId` and `visibleHistoryStartDateTime` (https://learn.microsoft.com/en-us/graph/api/resources/aaduserconversationmember?view=graph-rest-1.0).

---

## 3. Channel messages

### 3.1 The chatMessage resource
Source: https://learn.microsoft.com/en-us/graph/api/resources/chatmessage?view=graph-rest-1.0

Properties:

| Property | Notes |
|---|---|
| `id` | Message ID. |
| `replyToId` | `null` for a root post; the root ID for a reply. Channel messages only. |
| `etag` | Version. |
| `messageType` | `message`, `chatEvent`, `typing`, `unknownFutureValue`, `systemEventMessage`. `systemEventMessage` is returned only with `Prefer: include-unknown-enum-members`; otherwise system events show as `unknownFutureValue`. |
| `createdDateTime`, `lastModifiedDateTime` | `lastModifiedDateTime` also changes on reactions. |
| `lastEditedDateTime`, `deletedDateTime` | |
| `subject` | Channel root posts only. |
| `summary` | |
| `chatId` | `null` for channel messages. |
| `importance` | `normal`, `high`, `urgent`. |
| `locale` | Always `en-us`. |
| `webUrl` | |
| `policyViolation` | |
| `eventDetail` | System events only. |
| `from` | `chatMessageFromIdentitySet`: `{application, device, user}`. One of them is set; `from` is `null` for system events. |
| `body` | `itemBody`: `contentType` is `text` or `html`. It is always `html` when the message has mentions. |
| `channelIdentity` | `{teamId, channelId}`. |
| `attachments[]`, `mentions[]`, `reactions[]` | See 3.1.1-3.1.3. |
| `messageHistory[]` | |
| Relationships | `replies` (supports `$expand` for channel messages) and `hostedContents`. |

#### 3.1.1 Mentions
Source: https://learn.microsoft.com/en-us/graph/api/chatmessage-post?view=graph-rest-1.0

- Body HTML contains `<at id="0">Display Name</at>`. The `id` matches `mentions[i].id`, which is an integer.
- `mentions[i].mentioned` is an identity set: `user`, `application`, `conversation` (for example "Everyone" with `conversationIdentityType: "chat"`), or `tag`.
- When the bot Max is @mentioned, expect `mentioned.application` to be a `teamworkApplicationIdentity`:
  - Fields: `id` (bot app ID), `displayName`, `applicationIdentityType: "bot"`.
  - Allowed `applicationIdentityType` values: `aadApplication`, `bot`, `tenantBot`, `office365Connector`, `outgoingWebhook`, `unknownFutureValue`.
  - Source: https://learn.microsoft.com/en-us/graph/api/resources/teamworkapplicationidentity?view=graph-rest-1.0
  - The bot-mention JSON shape below is COMPOSITE (no verbatim doc example of a bot mention found).

#### 3.1.2 Attachments
Source: https://learn.microsoft.com/en-us/graph/api/resources/chatmessageattachment?view=graph-rest-1.0 and https://learn.microsoft.com/en-us/graph/teams-messaging-overview

- **Fields:** `id`, `contentType`, `contentUrl`, `content`, `name`, `thumbnailUrl`, `teamsAppId`.
- **`contentType` values:**
  - `reference` is a file. `contentUrl` is the SharePoint URL, not a Graph URL. Resolve it through `/shares` (section 4.6).
  - `forwardedMessageReference`: `content` is a JSON string describing the original message.
  - `meetingReference`: channel meeting posts. `content` is `{"exchangeId":"AAMk...","organizerId":"..."}`.
  - `application/vnd.microsoft.card.adaptive`, `.thumbnail`, `.hero`: cards. `content` is the card JSON as a string.
  - `application/vnd.microsoft.card.codesnippet` and `application/vnd.microsoft.card.announcement`.
- **Linking:** the body references each attachment with `<attachment id="{id}"></attachment>`.
- **File attachment ID:** for SharePoint file references the ID is the driveItem `eTag` GUID, and `contentUrl` is the `webDavUrl` (from the chatmessage-post docs, Example 4).

Verbatim file attachment (from teams-messaging-overview):

```json
"attachments": [
    {
        "id": "924D1F74-E0D2-4927-8A67-15ECEF455527",
        "contentType": "reference",
        "contentUrl": "https://testing.sharepoint.com/sites/Samples/Shared Documents/General/color.png",
        "content": null,
        "name": "color.png",
        "thumbnailUrl": null,
        "teamsAppId": null
    }
]
```

#### 3.1.3 Reactions
Sources: https://learn.microsoft.com/en-us/graph/api/resources/chatmessagereaction?view=graph-rest-1.0 and chatmessage-get Example 4.

- **Fields:** `reactionType`, `displayName`, `reactionContentUrl`, `createdDateTime`, `user`.
- **`reactionType`:** a Unicode emoji such as `"💯"`, or `custom`, or a legacy value: `like`, `angry`, `sad`, `laugh`, `heart`, `surprised`.
- **`user`:** inside it, `user.displayName` is often `null`.

```json
"reactions": [
    {
        "reactionType": "💯",
        "displayName": "Hundred points",
        "reactionContentUrl": null,
        "createdDateTime": "2024-02-14T22:07:36.3Z",
        "user": {
            "application": null,
            "device": null,
            "user": {
                "@odata.type": "#microsoft.graph.teamworkUserIdentity",
                "id": "670374fa-3b0e-4a3b-9d33-0e1bc5ff1956",
                "displayName": null,
                "userIdentityType": "aadUser"
            }
        }
    }
]
```

#### 3.1.4 COMPOSITE: a full channel root message as Max would see it
This example mentions Max and attaches a SharePoint file. It is built from the verbatim pieces above; the field set and order follow the channel-list-messages examples.

```json
{
    "id": "1731600000123",
    "replyToId": null,
    "etag": "1731600000123",
    "messageType": "message",
    "createdDateTime": "2026-11-18T15:20:00.123Z",
    "lastModifiedDateTime": "2026-11-18T15:21:10.456Z",
    "lastEditedDateTime": null,
    "deletedDateTime": null,
    "subject": "Q4 budget",
    "summary": null,
    "chatId": null,
    "importance": "normal",
    "locale": "en-us",
    "webUrl": "https://teams.microsoft.com/l/message/19%3A4a95f7d8db4c4e7fae857bcebe0623e6%40thread.tacv2/1731600000123?groupId=fbe2bf47-16c8-47cf-b4a5-4b9b187c508b&tenantId=2432b57b-0abd-43db-aa7b-16eadd115d34&createdTime=1731600000123&parentMessageId=1731600000123",
    "policyViolation": null,
    "eventDetail": null,
    "from": {
        "application": null,
        "device": null,
        "user": {
            "@odata.type": "#microsoft.graph.teamworkUserIdentity",
            "id": "8ea0e38b-efb3-4757-924a-5f94061cf8c2",
            "displayName": "Robin Kline",
            "userIdentityType": "aadUser",
            "tenantId": "2432b57b-0abd-43db-aa7b-16eadd115d34"
        }
    },
    "body": {
        "contentType": "html",
        "content": "<p><at id=\"0\">Max</at> what did we decide about the budget? <attachment id=\"153fa47d-18c9-4179-be08-9879815a9f90\"></attachment></p>"
    },
    "channelIdentity": {
        "teamId": "fbe2bf47-16c8-47cf-b4a5-4b9b187c508b",
        "channelId": "19:4a95f7d8db4c4e7fae857bcebe0623e6@thread.tacv2"
    },
    "attachments": [
        {
            "id": "153fa47d-18c9-4179-be08-9879815a9f90",
            "contentType": "reference",
            "contentUrl": "https://contoso.sharepoint.com/sites/Finance/Shared%20Documents/General/Budget.docx",
            "content": null,
            "name": "Budget.docx",
            "thumbnailUrl": null,
            "teamsAppId": null
        }
    ],
    "mentions": [
        {
            "id": 0,
            "mentionText": "Max",
            "mentioned": {
                "application": {
                    "@odata.type": "#microsoft.graph.teamworkApplicationIdentity",
                    "id": "00000000-0000-0000-0000-00000000max1",
                    "displayName": "Max",
                    "applicationIdentityType": "bot"
                },
                "device": null,
                "conversation": null,
                "user": null
            }
        }
    ],
    "reactions": [],
    "messageHistory": []
}
```

A message posted by the bot carries `from.application = {id: botAppId, displayName: "Max", applicationIdentityType: "bot"}` and `from.user = null` (COMPOSITE).

### 3.2 List root messages: `GET /teams/{team-id}/channels/{channel-id}/messages`
Source: https://learn.microsoft.com/en-us/graph/api/channel-list-messages?view=graph-rest-1.0 (updated 2026-04-10)

- **Content:** returns root messages only, without replies.
- **Sort order:** by the last-modified time of the whole reply chain, including replies.
- **Query params:**
  - `$top`: default 20, max 50.
  - `$expand=replies`: up to 200 replies inline (one example says 1,000), with `replies@odata.nextLink` for more.
  - No other OData parameters are supported.
- **Header:** `Prefer: include-unknown-enum-members` exposes `systemEventMessage`.
- **Permissions:**
  - Delegated: `ChannelMessage.Read.All`.
  - Application: **`ChannelMessage.Read.Group` (RSC, least)**, `ChannelMessage.Read.All`.
- **Federation:** in application context, "the request must be made from the tenant that the channel owner belongs to".

Verbatim response envelope (one item shown; the `$skiptoken` is long, URL-encoded and opaque):

```json
{
    "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#teams('fbe2bf47-16c8-47cf-b4a5-4b9b187c508b')/channels('19%3A4a95f7d8db4c4e7fae857bcebe0623e6%40thread.tacv2')/messages",
    "@odata.count": 3,
    "@odata.nextLink": "https://graph.microsoft.com/v1.0/teams/fbe2bf47-16c8-47cf-b4a5-4b9b187c508b/channels/19:4a95f7d8db4c4e7fae857bcebe0623e6@thread.tacv2/messages?$skiptoken=%5b%7B%22token%22%3a%22%2bRID%3a~vpsQAJ9uAC047gwAAACcBQ%3d%3d...%22%7d%5d",
    "value": [
        {
            "id": "1616965872395",
            "replyToId": null,
            "etag": "1616965872395",
            "messageType": "message",
            "createdDateTime": "2021-03-28T21:11:12.395Z",
            "lastModifiedDateTime": "2021-03-28T21:11:12.395Z",
            "lastEditedDateTime": null,
            "deletedDateTime": null,
            "subject": null,
            "summary": null,
            "chatId": null,
            "importance": "normal",
            "locale": "en-us",
            "webUrl": "https://teams.microsoft.com/l/message/19%3A4a95f7d8db4c4e7fae857bcebe0623e6%40thread.tacv2/1616965872395?groupId=fbe2bf47-16c8-47cf-b4a5-4b9b187c508b&tenantId=2432b57b-0abd-43db-aa7b-16eadd115d34&createdTime=1616965872395&parentMessageId=1616965872395",
            "policyViolation": null,
            "eventDetail": null,
            "from": {
                "application": null,
                "device": null,
                "user": {
                    "id": "8ea0e38b-efb3-4757-924a-5f94061cf8c2",
                    "displayName": "Robin Kline",
                    "userIdentityType": "aadUser"
                }
            },
            "body": { "contentType": "html", "content": "Hello World <at id=\"0\">Jane Smith</at>" },
            "channelIdentity": {
                "teamId": "fbe2bf47-16c8-47cf-b4a5-4b9b187c508b",
                "channelId": "19:4a95f7d8db4c4e7fae857bcebe0623e6@thread.tacv2"
            },
            "attachments": [],
            "mentions": [
                {
                    "id": 0,
                    "mentionText": "Jane Smith",
                    "mentioned": {
                        "application": null, "device": null, "conversation": null,
                        "user": { "id": "ef1c916a-3135-4417-ba27-8eb7bd084193", "displayName": "Jane Smith", "userIdentityType": "aadUser" }
                    }
                }
            ],
            "reactions": [],
            "messageHistory": []
        }
    ]
}
```

A system event message from the same doc:

```json
{
  "messageType": "systemEventMessage",
  "from": null,
  "body": { "contentType": "html", "content": "<systemEventMessage/>" },
  "eventDetail": {
    "@odata.type": "#microsoft.graph.teamDescriptionUpdatedEventMessageDetail",
    "teamId": "fbe2bf47-16c8-47cf-b4a5-4b9b187c508b",
    "teamDescription": "Team for Microsoft Teams members",
    "initiator": { "application": null, "device": null, "user": { "id": "1fb8890f-423e-4154-8fbf-db6809bc8756", "displayName": null, "userIdentityType": "aadUser" } }
  }
}
```

With `$expand=replies`, each root carries `"replies@odata.count": 3`, `"replies@odata.nextLink": "https://graph.microsoft.com/v1.0/teams/{id}/channels/{id}/messages/{rootId}/replies?$skiptoken=MSwwLDE2NDQ0MzkzODAxNDU"` and `"replies": [ ...chatMessage... ]`. Replies are newest first in the example.

### 3.3 Replies: `GET /teams/{team-id}/channels/{channel-id}/messages/{message-id}/replies`
Source: https://learn.microsoft.com/en-us/graph/api/chatmessage-list-replies?view=graph-rest-1.0

- `$top` max is 50. No other OData parameters are supported.
- Permissions are the same as 3.2 (RSC `ChannelMessage.Read.Group` is least privileged for application).
- Response: `{"@odata.context": ".../messages('1616989510408')/replies", "@odata.count": 3, "value": [ chatMessage ... ]}`.
- Each reply has `"replyToId": "1616989510408"`.
- In the doc example `webUrl` has `parentMessageId={rootId}`, and `body.contentType` is `"text"` with content `"Reply3"`.

### 3.4 Get one message or reply
Source: https://learn.microsoft.com/en-us/graph/api/chatmessage-get?view=graph-rest-1.0

```
GET /teams/{team-id}/channels/{channel-id}/messages/{message-id}
GET /teams/{team-id}/channels/{channel-id}/messages/{message-id}/replies/{reply-id}
```

- No OData parameters.
- Permissions:
  - Application: `ChannelMessage.Read.Group` (RSC), `ChannelMessage.Read.All`.
  - Delegated: `ChannelMessage.Read.All`.
- `@odata.context`:
  - Message: `...$metadata#teams('{teamId}')/channels('19%3A...%40thread.tacv2')/messages/$entity`
  - Reply: `.../messages('{rootId}')/replies/$entity`
- In GET responses `from.user` includes `"@odata.type": "#microsoft.graph.teamworkUserIdentity"` and `tenantId`. `from` also has `"conversation": null`.

### 3.5 Delta: `GET /teams/{team-id}/channels/{channel-id}/messages/delta`

- **Status:** the v1.0 endpoint still exists. The PowerShell cmdlet `Get-MgTeamChannelMessageDelta` (updated 2026-10) lists application permissions `ChannelMessage.Read.Group` (RSC) and `ChannelMessage.Read.All`, and delegated `ChannelMessage.Read.All`. Source: https://learn.microsoft.com/en-us/powershell/module/microsoft.graph.teams/get-mgteamchannelmessagedelta
- **Docs caveat:** the current Graph reference page (https://learn.microsoft.com/en-us/graph/api/chatmessage-delta?view=graph-rest-1.0, updated 2025-11) now documents only `GET /users/{id}/chats/getAllMessages/delta` (application `Chat.Read.All`). The channel-delta details below come from that same page family and from search summaries of the channel version. They are partly UNVERIFIED for the channel variant.
- **Semantics:**
  - Full sync first, then incremental. Returns root messages without replies; use `$expand=replies`.
  - **Only messages from the last 8 months are returned.** Use plain list for older ones.
  - `$top` max is 50. `$skip` is supported.
  - `$filter=lastModifiedDateTime gt {ISO}` is the only filter, with `gt` only.
  - Put query parameters on the first call only; they get encoded into the tokens.
  - Each page returns either `@odata.nextLink` (with `$skiptoken`) or, on the last page, `@odata.deltaLink` (with `$deltatoken`). Save the deltaLink for the next round.
- **Known issue:** some channels return `400 BadRequest/UnknownError`. Adding a `lastModifiedDateTime` filter has worked around it (community report).

Verbatim response shape (from the chats delta example; channel delta has the same envelope):

```json
{
  "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#Collection(microsoft.graph.chatMessage)",
  "@odata.deltaLink": "https://graph.microsoft.com/v1.0/users/5ed12dd6-24f8-4777-be3d-0d234e06cefa/chats/getAllMessages/delta?$deltatoken=aQdvS1VwGCSRxVmZJqykmDik_JIC44iCZpv-GLiA2VnFuE5yG-kCEBROb2iaPT_y_eMWVQtBO_ejzzyIxl00ji-tQ3HzAbW4liZAVG88lO3nG_6-MBFoHY1n8y21YUzjocG-Cn1tCNeeLPLTzIe5Dw.EP9gLiCoF2CE_e6l_m1bTk2aokD9KcgfgfcLGqd1r_4",
  "value": [ { "id": "1726706340932", "replyToId": null, "etag": "1726706340932", "messageType": "message", "...": "..." } ]
}
```

Simulator: produce `.../channels/{id}/messages/delta?$skiptoken=...` and `...?$deltatoken=...` links in the same style.

### 3.6 Export across a team: `GET /teams/{team-id}/channels/getAllMessages`
Source: https://learn.microsoft.com/en-us/graph/api/channel-getallmessages?view=graph-rest-1.0

- Application permission `ChannelMessage.Read.All` only.
- Supports `$top` and `$filter` on `lastModifiedDateTime`.
- Returns roots and replies flattened.
- No longer metered.
- Nice-to-have for Max's initial backfill.

### 3.7 Sending messages and replies

**Graph (not usable app-only):**

```
POST /teams/{team-id}/channels/{channel-id}/messages
POST /teams/{team-id}/channels/{channel-id}/messages/{message-id}/replies
```

- Source: https://learn.microsoft.com/en-us/graph/api/chatmessage-post?view=graph-rest-1.0
- Permissions:
  - Delegated: `ChannelMessage.Send`.
  - Application: `Teamwork.Migrate.All` only: "Application permissions are only supported for migration."
- The RSC permission `ChannelMessage.Send.Group` ("Send messages to this team's channels") exists in the RSC list, but it is not listed on the Graph POST permission tables. Using it for Graph app-only posting is UNVERIFIED and should be assumed not to work.
- Response is `201 Created` with a chatMessage.
- Only `body` is required.
- The Teams terms of use prohibit using Teams as a log file.

Verbatim request with a mention:

```json
{
  "body": { "contentType": "html", "content": "Hello World <at id=\"0\">Jane Smith</at>" },
  "mentions": [
    { "id": 0, "mentionText": "Jane Smith",
      "mentioned": { "user": { "displayName": "Jane Smith", "id": "ef1c916a-3135-4417-ba27-8eb7bd084193", "userIdentityType": "aadUser" } } }
  ]
}
```

Verbatim request with a SharePoint file reference (Example 4):

```json
{
    "body": {
        "contentType": "html",
        "content": "Here's the latest budget. <attachment id=\"153fa47d-18c9-4179-be08-9879815a9f90\"></attachment>"
    },
    "attachments": [
        {
            "id": "153fa47d-18c9-4179-be08-9879815a9f90",
            "contentType": "reference",
            "contentUrl": "https://m365x987948.sharepoint.com/sites/test/Shared%20Documents/General/test%20doc.docx",
            "name": "Budget.docx"
        }
    ]
}
```

- In the response, the attachment echoes back with `"content": null` and `"thumbnailUrl": null` added.
- Cards: attachment `contentType` is `application/vnd.microsoft.card.*`, and only the `OpenUrl` action is supported via Graph.
- Inline images use `hostedContents` with a `@microsoft.graph.temporaryId`.

**Bot Framework connector (how Max must post):**

- Sources:
  - https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/conversations/send-proactive-messages
  - https://learn.microsoft.com/en-us/azure/bot-service/rest-api/bot-framework-rest-connector-send-and-receive-messages
- Covered in detail in the bot research doc. Summary:
  - Bot token: `POST https://login.microsoftonline.com/{tenant|botframework.com}/oauth2/v2.0/token` with `scope=https://api.botframework.com/.default`.
  - New channel thread: `POST {serviceUrl}/v3/conversations` with `isGroup: true`, `channelData.channel.id = 19:...@thread.tacv2`, `channelData.tenant.id`, and `activity`. Response: `{"id": "{conversationId}", "activityId": "{activityId}"}`.
  - Reply in a thread: `POST {serviceUrl}/v3/conversations/{conversationId}/activities/{activityId}`, where conversationId is `19:...@thread.tacv2;messageid={rootMessageId}`. The `;messageid=` form with `@thread.skype` is documented; with `tacv2` it is from community sources (UNVERIFIED).
  - The `activityId` returned by the connector equals the Graph `chatMessage.id`. This is widely observed but UNVERIFIED in the docs.
  - Limits per bot per thread: 7 per 1 s, 8 per 2 s, 60 per 30 s, 1800 per hour. Global limit: 50 RPS per app per tenant. Retry 412, 429, 502, 504 (https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/rate-limit).
  - A blocked or uninstalled bot gets 403 `MessageWritesBlocked`.

---

## 4. Files in a channel (SharePoint)

How channel files are stored:
- Each team is an M365 group with a SharePoint site.
- Each standard channel maps to a folder in that site's "Shared Documents" library, named after the channel.
- Private and shared channels have their own sites.
- After the 2025 private-channel "group compliance" migration, `filesFolder` for a private channel returns the root folder.
- Source: https://learn.microsoft.com/en-us/graph/api/channel-get-filesfolder?view=graph-rest-1.0

### 4.1 `GET /teams/{team-id}/channels/{channel-id}/filesFolder` returns a driveItem (the folder)

- Permissions:
  - Application: `Files.Read.All` (least). Higher options include `File.Read.Group` (RSC; note the singular "File"), `Files.ReadWrite.All`, `Sites.Read.All`.
  - Delegated: `Files.Read.All`.
- No OData parameters.
- Special characters in channel names can cause errors (known issue).

Verbatim:

```json
{
    "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#teams('32e3b156-66b2-4135-9aeb-73295a35a55b')/channels('19%3Af253e46c035b42308e9a4a22a87037af%40thread.skype')/filesFolder/$entity",
    "id": "01H7CFEKENJSSIUHGADZBKODARINQC5JMD",
    "createdDateTime": "0001-01-01T00:00:00Z",
    "lastModifiedDateTime": "2020-01-23T18:47:13Z",
    "name": "Documentation Planning",
    "webUrl": "https://microsoft.sharepoint.com/teams/ExtensibilityandFundamentals/Shared%20Documents/Documentation%20Planning",
    "size": 2374080,
    "parentReference": {
        "driveId": "b!2SInBlQrN0K8-GXMy9qNsPtI5ScW8C5IlZtycoy6ZpJZRRtgE4qVTrE8wrvL0-hd",
        "driveType": "documentLibrary"
    },
    "fileSystemInfo": { "createdDateTime": "2020-01-23T18:47:12Z", "lastModifiedDateTime": "2020-01-23T18:47:13Z" },
    "folder": { "childCount": 7 }
}
```

Max flow:
1. Call `filesFolder` and read `parentReference.driveId` and `id`.
2. List children with `GET /drives/{driveId}/items/{id}/children`.
3. Download each file with `GET /drives/{driveId}/items/{childId}/content`.

### 4.2 `GET /drives/{drive-id}/items/{item-id}/children`
Source: https://learn.microsoft.com/en-us/graph/api/driveitem-list-children?view=graph-rest-1.0

- Alternate paths: `/groups/{group-id}/drive/items/{id}/children`, `/sites/{site-id}/drive/items/{id}/children`, `/drives/{drive-id}/root:/{path}:/children`.
- Query params: `$expand` (for example `thumbnails`), `$select`, `$skipToken`, `$top`, `$orderby`.
- Default page size is 200; `@odata.nextLink` appears beyond that.
- `if-none-match: {etag}` returns `304`.
- Permissions:
  - Application: `Files.Read.All` (least), `Files.ReadWrite.All`, `Sites.Read.All`, `Sites.ReadWrite.All`. `Sites.Selected` also works with a per-site grant (https://learn.microsoft.com/en-us/graph/permissions-selected-overview).
  - The tables for children and content do **not** list RSC `File.Read.Group`. Whether an RSC-only token can list or download under the folder is UNVERIFIED and needs a live test.

Verbatim (minimal doc example):

```json
{
  "value": [
    {"name": "myfile.jpg", "size": 2048, "file": {} },
    {"name": "Documents", "folder": { "childCount": 4} }
  ],
  "@odata.nextLink": "https://..."
}
```

COMPOSITE file driveItem, built from the driveItem, itemReference and hashes schemas. The simulator should return these fields:

```json
{
  "@microsoft.graph.downloadUrl": "https://contoso.sharepoint.com/sites/Finance/_layouts/15/download.aspx?UniqueId=2246bd2d-7811-4660-bd0f-1cf36133677b&Translate=false&tempauth=eyJ0eXAi...&ApiVersion=2.0",
  "createdDateTime": "2026-11-10T09:12:44Z",
  "eTag": "\"{2246BD2D-7811-4660-BD0F-1CF36133677B},3\"",
  "id": "01BYE5RZZNHVDCMEC4MZGL3QX3KYHWGSXQ",
  "lastModifiedDateTime": "2026-11-17T16:02:11Z",
  "name": "Budget.docx",
  "webUrl": "https://contoso.sharepoint.com/sites/Finance/Shared%20Documents/General/Budget.docx",
  "cTag": "\"c:{2246BD2D-7811-4660-BD0F-1CF36133677B},2\"",
  "size": 19001,
  "createdBy": { "user": { "email": "robin@contoso.com", "id": "8ea0e38b-efb3-4757-924a-5f94061cf8c2", "displayName": "Robin Kline" } },
  "lastModifiedBy": { "user": { "email": "jane@contoso.com", "id": "ef1c916a-3135-4417-ba27-8eb7bd084193", "displayName": "Jane Smith" } },
  "parentReference": {
    "driveType": "documentLibrary",
    "driveId": "b!2SInBlQrN0K8-GXMy9qNsPtI5ScW8C5IlZtycoy6ZpJZRRtgE4qVTrE8wrvL0-hd",
    "id": "01H7CFEKENJSSIUHGADZBKODARINQC5JMD",
    "name": "General",
    "path": "/drives/b!2SInBlQrN0K8-GXMy9qNsPtI5ScW8C5IlZtycoy6ZpJZRRtgE4qVTrE8wrvL0-hd/root:/General",
    "siteId": "contoso.sharepoint.com,0627222d-2b54-4237-bcf8-65cccbda8db0,27e548fb-f016-482e-959b-72728cba6692"
  },
  "file": {
    "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "hashes": { "quickXorHash": "S4ZBjpWQBjA3Uw0xUzRk4bn2f8I=" }
  },
  "fileSystemInfo": { "createdDateTime": "2026-11-10T09:12:44Z", "lastModifiedDateTime": "2026-11-17T16:02:11Z" },
  "shared": { "scope": "users" }
}
```

Field rules (driveItem resource, https://learn.microsoft.com/en-us/graph/api/resources/driveitem?view=graph-rest-1.0):

- **`@microsoft.graph.downloadUrl`:**
  - It is short-lived (about 1 hour, "might expire within minutes") and needs no Authorization header.
  - It is returned on GET of an item and in children listings.
  - The `download.aspx?...tempauth=` URL format above is UNVERIFIED (observed, not documented).
  - The `$select` syntax to request it is `?select=id,@microsoft.graph.downloadUrl`.
- **`cTag`:** omitted on folders in SharePoint.
- **Hashes:** `quickXorHash` is the only guaranteed hash; `sha256Hash` is not supported.
- **Facets:** folders carry `folder: {childCount}` instead of `file`.
- **`createdBy.user.email`:** not in the official schema examples (UNVERIFIED but commonly returned).

### 4.3 `GET /drives/{drive-id}/items/{item-id}` (metadata)
Source: https://learn.microsoft.com/en-us/graph/api/driveitem-get?view=graph-rest-1.0

- Supports `$select` and `$expand`.
- Permissions are the same as 4.2.

### 4.4 `GET /drives/{drive-id}/items/{item-id}/content` (download)
Source: https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0

```
HTTP/1.1 302 Found
Location: https://b0mpua-by3301.files.1drv.com/y23vmagahszhxzlcvhasdhasghasodfi
```

- Follow the `Location` header. The target is pre-authenticated, so do not send a Bearer token.
- `Range: bytes=0-1023` works on the downloadUrl and returns `206`.
- Conversion: `?format=pdf` works for docx/pptx/xlsx and others, up to **2 MB**. It needs application `Files.ReadWrite.All` and returns 302 (https://learn.microsoft.com/en-us/graph/api/driveitem-get-content-format?view=graph-rest-1.0).

### 4.5 Drive delta: `GET /drives/{drive-id}/root/delta`
Source: https://learn.microsoft.com/en-us/graph/api/driveitem-delta?view=graph-rest-1.0

- **`token` parameter:**
  - `?token=latest` gives an empty page plus a deltaLink.
  - `?token={previous}` returns changes since that token.
- **Results:**
  - Deleted items carry `"deleted": {}`.
  - `parentReference.path` is not populated, so track items by id.
  - `410 Gone` (`resyncChangesApplyDifferences`) means re-enumerate.
- **Permissions:** application `Files.Read.All`.
- **deltaLink format:** `https://graph.microsoft.com/v1.0/me/drive/root/delta?(token='MzslMjM0...')`

### 4.6 Resolving a message attachment `contentUrl` to a driveItem
Source: https://learn.microsoft.com/en-us/graph/api/shares-get?view=graph-rest-1.0

`GET /shares/{u!base64url(contentUrl)}/driveItem`. Append `/content` to download.

To encode the URL:
1. Base64-encode the URL.
2. Strip `=` padding, replace `/` with `_` and `+` with `-`.
3. Prepend `u!`.

Caveats:
- Application permission is `Files.ReadWrite.All`; this is a write scope.
- Whether spaces in `contentUrl` must be `%20`-encoded first is UNVERIFIED.
- Alternative: match the attachment `name`/`webUrl` against filesFolder children.

Verbatim:

```json
{ "id": "9FFFDB3C-5B87-4062-9606-1B008CA88E44", "name": "contoso project.docx", "eTag": "2246BD2D-7811-4660-BD0F-1CF36133677B,1", "file": {}, "size": 109112 }
```

---

## 5. Online meetings, transcripts, recordings, AI insights

### 5.1 Find a meeting by join URL
Source: https://learn.microsoft.com/en-us/graph/api/onlinemeeting-get?view=graph-rest-1.0 (updated 2026-10-28)

```
GET /users/{userId}/onlineMeetings?$filter=JoinWebUrl%20eq%20'{URL-encoded joinWebUrl}'
GET /users/{userId}/onlineMeetings?$filter=joinMeetingIdSettings/joinMeetingId%20eq%20'{joinMeetingId}'
GET /users/{userId}/onlineMeetings/{meetingId}
GET /me/onlineMeetings/...                       (delegated)
GET /communications/onlineMeetings/?$filter=VideoTeleconferenceId%20eq%20'{vtcId}'   (app only, no access policy)
```

- **Permissions:**
  - Delegated: `OnlineMeetings.Read`.
  - Application: `OnlineMeetings.Read.All`.
  - No RSC.
- **`{userId}`** may be the organizer or an invited attendee.
- **Response shape:** a filter query returns a collection with one item.
- **Application access policy is required for app-only access** (https://learn.microsoft.com/en-us/graph/cloud-communication-online-meeting-application-access-policy):
  - Admin commands: `New-CsApplicationAccessPolicy -Identity Max-policy -AppIds "{appId}"`, then `Grant-CsApplicationAccessPolicy -PolicyName Max-policy -Identity "{userId}"` (or `-Global`).
  - Propagation takes up to 30 minutes.
  - The policy governs `OnlineMeetings.Read(Write).All`, `OnlineMeetingArtifact.Read.All`, `OnlineMeetingTranscript.Read.All`, `OnlineMeetingRecording.Read.All`, and `VirtualEvent.Read.All`.
  - Without the policy you get this error (verbatim):

```json
{
    "error": {
        "code": "Forbidden",
        "message": "No application access policy found for this app",
        "innerError": { "date": "<date_redacted>", "request-id": "599d9cb0-56ac-4dc5-b6f8-1456a1414609" }
    }
}
```

Verbatim onlineMeeting from Example 3 (filter by JoinWebUrl). `chatInfo` comes from Example 1 and was merged in for completeness:

```json
{
    "value": [
        {
            "id": "dc17674c-81d9-4adb-bfb2-8f6a442e4622_19:meeting_MGQ4MDQyNTEtNTQVkODYxODYzMmY2@thread.v2",
            "creationDateTime": "2020-09-29T22:35:33.1594516Z",
            "startDateTime": "2020-09-29T22:35:31.389759Z",
            "endDateTime": "2020-09-29T23:35:31.389759Z",
            "expiryDateTime": "2025-04-12T23:57:47.6388574Z",
            "joinWebUrl": "https://teams.microsoft.com/l/meetup-join/19%3ameeting_MGQ4MDQyNTEtNTQ2NS00YjQxLTlkMYzMmY2%40thread.v2/0?context=%7b%22Tid%22%3a%22909c6581-5130-43e9-882cde37%22%2c%22Oid%22%3a%22dc17674c-81d9-4adb-bfb2-8f6a442e4622%22%7d",
            "subject": null,
            "isEntryExitAnnounced": true,
            "allowedPresenters": "everyone",
            "videoTeleconferenceId": "(redacted)",
            "chatInfo": {
                "@odata.type": "#microsoft.graph.chatInfo",
                "threadId": "19:cbee7c1c860e465cebf7bee0d@thread.skype",
                "messageId": "153367081"
            },
            "participants": {
                "organizer": {
                    "upn": "(redacted)",
                    "role": "presenter",
                    "identity": { "user": { "id": "dc17674c-81d9-4adb-bf442e4622", "displayName": null, "tenantId": "909c6581-5130-43e93582cde38", "identityProvider": "AAD" } }
                },
                "attendees": [
                    { "@odata.type": "#microsoft.graph.identitySet", "identity": { "user": { "@odata.type": "#microsoft.graph.identity", "id": "112f7296-5ca-bae8-6a692b15d4b8", "displayName": "Tyler Stein" } }, "upn": "upn-value" }
                ],
                "producers": [],
                "contributors": []
            },
            "meetingOptionsWebUrl": "https://teams.microsoft.com/meetingOptions/?meetingId=abc123",
            "meetingSpokenLanguageTag": "en-US",
            "lobbyBypassSettings": { "scope": "organization", "isDialInBypassEnabled": false },
            "joinMeetingIdSettings": { "isPasscodeRequired": false, "joinMeetingId": "1234567890", "passcode": null }
        }
    ]
}
```

- `joinWebUrl` format: `https://teams.microsoft.com/l/meetup-join/{URL-encoded 19:meeting_...@thread.v2}/0?context={"Tid":"...","Oid":"{organizerId}"}`. The `Oid` in the context is the organizer, so Max can parse it to pick `{userId}`.
- `chatInfo.threadId` is the meeting chat ID (`19:meeting_...@thread.v2`). For a channel meeting it is the channel thread, and `messageId` is the root post (inference, UNVERIFIED).

### 5.2 Transcripts (v1.0 GA)
Sources:
- https://learn.microsoft.com/en-us/graph/api/onlinemeeting-list-transcripts?view=graph-rest-1.0
- https://learn.microsoft.com/en-us/graph/api/calltranscript-get?view=graph-rest-1.0 (updated 2026-10-01)

```
GET /users/{userId}/onlineMeetings/{meetingId}/transcripts                 ($select, $filter, $top)
GET /users/{userId}/onlineMeetings/{meetingId}/transcripts/{transcriptId}
GET /users/{userId}/onlineMeetings/{meetingId}/transcripts/{transcriptId}/content?$format=text/vtt
GET /users/{userId}/onlineMeetings/{meetingId}/transcripts/{transcriptId}/metadataContent
```

**Permissions:**
- Application: `OnlineMeetingTranscript.Read.All` plus the access policy. Alternatively RSC `OnlineMeetingTranscript.Read.Chat`, which covers scheduled private-chat meetings only, **not channel meetings**.
- Delegated: `OnlineMeetingTranscript.Read.All`. There is no `.Read` scope.
- Ad hoc calls use `/adhocCalls/{callId}/transcripts` with `CallTranscripts.Read.All`.

**Content formats:**
- `text/vtt`: the default, with speaker `<v Name>` tags. Select it with `Accept: text/vtt` or `$format=text/vtt`.
- `application/vnd.microsoft.graph.transcript+text`: no speakers; Accept header only. It takes effect at the end of July 2026.
- DOCX is deprecated since 2023-05-31.

**Preconditions:**
- Transcription was started in the meeting.
- The meeting is not expired.
- The meeting is tied to a calendar event. Meetings created by `POST /onlineMeetings` alone are not supported.
- The tenant switch is on (section 0).

Verbatim callTranscript:

```json
{
    "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users('ba321e0d-79ee-478d-8e28-85a19507f456')/onlineMeetings('MSo1N2Y5ZGFjYy03MWJmLTQ3NDMtYjQxMy01M2EdFGkdRWHJlQ')/transcripts/$entity",
    "id": "MSMjMCMjNzU3ODc2ZDYtOTcwMi00MDhkLWFkNDItOTE2ZDNmZjkwZGY4",
    "meetingId": "MSo1N2Y5ZGFjYy03MWJmLTQ3NDMtYjQxMy01M2EdFGkdRWHJlQ",
    "callId": "af630fe0-04d3-4559-8cf9-91fe45e36296",
    "createdDateTime": "2021-09-17T06:09:24.8968037Z",
    "endDateTime": "2021-09-17T06:27:25.2346000Z",
    "contentCorrelationId": "bc842d7a-2f6e-4b18-a1c7-73ef91d5c8e3",
    "transcriptContentUrl": "https://graph.microsoft.com/v1.0/$metadata#users('ba321e0d-79ee-478d-8e28-85a19507f456')/onlineMeetings('MSo1N2Y5ZGFjYy03MWJmLTQ3NDMtYjQxMy01M2EdFGkdRWHJlQ')/transcripts/('MSMjMCMjNzU3ODc2ZDYtOTcwMi00MDhkLWFkNDItOTE2ZDNmZjkwZGY4')/content",
    "meetingOrganizer": {
        "application": null,
        "device": null,
        "user": {
            "@odata.type": "#Microsoft.Teams.GraphSvc.teamworkUserIdentity",
            "id": "ba321e0d-79ee-478d-8e28-85a19507f456",
            "displayName": null,
            "userIdentityType": "aadUser",
            "tenantId": "cd6cee19-2d76-4ee0-8f47-9ed12ee44331"
        }
    }
}
```

The list response wraps these as `{"@odata.context": ".../transcripts", "@odata.count": 3, "value": [...]}`.

Content (verbatim):

```
HTTP/1.1 200 OK
Content-type: text/vtt

WEBVTT

00:00:16.246 --> 00:00:17.726
<v User Name>This is a transcript test.</v>
```

metadataContent (verbatim):

```
HTTP/1.1 200 OK
Content-type: text/vtt

WEBVTT
00:00:16.246 --> 00:00:17.726
{"startDateTime":"2023-03-08T08:22:30.0461639+00:00","endDateTime":"2023-03-08T08:22:31.5261639+00:00","speakerName":"User Name","spokenText":"This is a transcription test.","spokenLanguage":"en-us"}
```

Errors (verbatim). Branch on `innerError.code`:

```json
{ "error": { "code": "Forbidden", "message": "Graph API access to transcripts is disabled for this tenant.", "innerError": { "code": "GraphAccessToTranscriptsDisabled" } } }
```
```json
{ "error": { "code": "Forbidden", "message": "Speaker-attributed transcript content is disabled for this tenant. Retry with Accept 'application/vnd.microsoft.graph.transcript+text'.", "innerError": { "code": "SpeakerAttributionNotAllowed" } } }
```

UNVERIFIED: the exact error when a transcript isn't ready yet. Expect an empty `value: []` list or a 404. Transcript generation can finish several minutes after the call, and notification latency can be up to 240 minutes.

**Organizer-wide enumeration (application only, v1.0):**
- Sources:
  - https://learn.microsoft.com/en-us/graph/api/onlinemeeting-getalltranscripts?view=graph-rest-1.0
  - https://learn.microsoft.com/en-us/graph/api/onlinemeeting-getallrecordings?view=graph-rest-1.0

```
GET /users/{userId}/onlineMeetings/getAllTranscripts(meetingOrganizerUserId='{userId}',startDateTime={ISO},endDateTime={ISO})
GET /users/{userId}/onlineMeetings/getAllRecordings(meetingOrganizerUserId='{userId}',startDateTime={ISO},endDateTime={ISO})
```

- Only `$top` is supported.
- Delta is available via the callTranscript/callRecording delta functions. Adding filters on a deltaLink returns `400 DeltaFilterNotAllowed`.
- Channel meetings are not supported.
- Items are callTranscript objects with `"@odata.type": "#microsoft.graph.callTranscript"` and an absolute `transcriptContentUrl` (`https://graph.microsoft.com/v1.0/users/{id}/onlineMeetings/{mid}/transcripts/{tid}/content`).
- Paging uses `@odata.nextLink` with `?skipToken=`.

### 5.3 Recordings
Sources:
- https://learn.microsoft.com/en-us/graph/api/onlinemeeting-list-recordings?view=graph-rest-1.0
- https://learn.microsoft.com/en-us/graph/api/callrecording-get?view=graph-rest-1.0

```
GET /users/{userId}/onlineMeetings/{meetingId}/recordings
GET /users/{userId}/onlineMeetings/{meetingId}/recordings/{recordingId}
GET /users/{userId}/onlineMeetings/{meetingId}/recordings/{recordingId}/content    -> 200 Content-Type: video/mp4
```

- **Permissions:**
  - Application: `OnlineMeetingRecording.Read.All` plus the access policy, or RSC `OnlineMeetingRecording.Read.Chat`.
- **Shape:** the same as callTranscript, with `recordingContentUrl` instead of `transcriptContentUrl`.
- **Correlation:** match a recording to its transcript with `contentCorrelationId`.
- **Tenant switch:** the transcript switch does not affect recordings.

### 5.4 Meeting AI insights (Copilot)
Sources:
- https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/api/ai-services/meeting-insights/onlinemeeting-list-aiinsights
- https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/api/ai-services/meeting-insights/callaiinsight-get

```
GET /v1.0/copilot/users/{userId}/onlineMeetings/{onlineMeetingId}/aiInsights          (list; 20/page; id, callId, contentCorrelationId, createdDateTime, endDateTime)
GET /v1.0/copilot/users/{userId}/onlineMeetings/{onlineMeetingId}/aiInsights/{id}
```

- **Permissions:** `OnlineMeetingAiInsight.Read.All` (delegated or application plus the access policy). No RSC.
- **Licensing:** every user needs a **Microsoft 365 Copilot license**; pay-as-you-go is not supported.
- **Availability:** global cloud only.
- **Max's use:** it is not a dependency for Max, which generates its own notes. It is a nice-to-have to imitate.

Verbatim (trimmed):

```json
{
  "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#copilot/users('b935e675-5e67-48b9-8d45-249d5f88e964')/onlineMeetings('YTc3OT...')/aiInsights/$entity",
  "id": "Z2HWbT...",
  "callId": "af630fe0-04d3-4559-8cf9-91fe45e36296",
  "contentCorrelationId": "bc842d7a-2f6e-4b18-a1c7-73ef91d5c8e3",
  "createdDateTime": "2024-05-27T08:17:10.7261294Z",
  "endDateTime": "2024-05-27T08:32:10.7261294Z",
  "meetingNotes": [
    { "title": "Introducing Project Objectives and Key Stakeholders",
      "text": "The stakeholders present included representatives from each department involved in the project, ensuring alignment and clear communication channels from the start.",
      "subpoints": [ { "title": "Discussion on action items", "text": "Action items were assigned to team members, and a follow-up meeting schedule was established." } ] }
  ],
  "actionItems": [
    { "title": "Finalize Project Timeline", "text": "Review and finalize the project timeline to ensure alignment with stakeholder expectations and resource availability.", "ownerDisplayName": "Bella Smith" }
  ],
  "viewpoint": {
    "mentionEvents": [
      { "speaker": { "application": null, "device": null, "user": { "@odata.type": "#Microsoft.Teams.GraphSvc.teamworkUserIdentity", "id": "9a7608d3-53e4-4a92-804f-ef43f1e5f5b5", "displayName": "John Smith", "userIdentityType": "aadUser", "tenantId": "d1aeb56e-5a25-4d91-a4f6-0f5e6a50d887" } },
        "eventDateTime": "2024-05-21T09:00:00",
        "transcriptUtterance": "We need to get approval from Sarah Johnson before proceeding with the budget allocation." }
    ]
  }
}
```

---

## 6. Calendar: finding a team's upcoming meetings

### 6.1 `GET /users/{id}/calendarView?startDateTime={ISO}&endDateTime={ISO}`
Source: https://learn.microsoft.com/en-us/graph/api/user-list-calendarview?view=graph-rest-1.0

- Both parameters are required.
- calendarView expands recurring series into occurrences. `GET /users/{id}/events` returns series masters and single instances only (https://learn.microsoft.com/en-us/graph/api/user-list-events?view=graph-rest-1.0).
- Headers:
  - `Prefer: outlook.timezone="Pacific Standard Time"`; the default is UTC.
  - `Prefer: outlook.body-content-type="text"`.
- Paging: `@odata.nextLink` with `$skip`.
- Permissions: `Calendars.ReadBasic` (least) or `Calendars.Read`, both delegated and application.
- Scope app access with **Exchange RBAC for Applications**, which replaces Exchange Application Access Policies (https://learn.microsoft.com/en-us/exchange/permissions-exo/application-rbac):
  - Commands: `New-ManagementScope`, then `New-ManagementRoleAssignment -App {spObjectId} -Role "Application Calendars.Read" -CustomResourceScope ...`.
  - Remove the tenant-wide Entra consent, or the scoping has no effect.
  - There is no `Application Calendars.ReadBasic` role.

### 6.2 Group (team) calendar
- `GET /groups/{id}/events`: delegated `Group.Read.All` only; application is **not supported** (https://learn.microsoft.com/en-us/graph/api/group-list-events?view=graph-rest-1.0).
- `GET /groups/{id}/calendarView`: the docs list application `Calendars.ReadBasic`, but community reports say app-only access to group calendars fails. Treat it as UNVERIFIED.

### 6.3 Channel meetings
- A channel meeting creates a channel post with a `meetingReference` attachment, whose `content` is `{"exchangeId":"AAMk...","organizerId":"..."}`. "You can use the Exchange ID to look up the meeting by using the calendar APIs." (https://learn.microsoft.com/en-us/graph/teams-messaging-overview)
- `GET /users/{organizerId}/events/{exchangeId}` is our inference (UNVERIFIED).

**Recommended Max algorithm:**
1. List members (RSC `TeamMember.Read.Group`).
2. For each member, read `calendarView` for the next N days (app `Calendars.Read`, RBAC-scoped).
3. Keep events with `isOnlineMeeting: true` and `onlineMeetingProvider: "teamsForBusiness"`.
4. Dedupe on `iCalUId`.
5. Resolve to an onlineMeeting through `onlineMeeting.joinUrl` (5.1).

Verbatim event (trimmed):

```json
{
    "@odata.etag":"W/\"ZlnW4RIAV06KYYwlrfNZvQAALfZeRQ==\"",
    "id":"AAMkAGI1AAAt8AHjAAA=",
    "createdDateTime":"2017-04-15T03:00:50.7579581Z",
    "lastModifiedDateTime":"2017-04-15T03:00:51.245372Z",
    "iCalUId":"040000008200E00074C5B7101A82E00800000000DA2B357D94B5D201000000000000000010000000EC4597557F0CB34EA4CC2887EA7B17C3",
    "subject":"Let's go brunch",
    "bodyPreview":"Does noon work for you?",
    "isCancelled":false,
    "isOrganizer":true,
    "showAs":"busy",
    "type":"singleInstance",
    "webLink":"https://outlook.office365.com/owa/?itemid=AAMkAGI1AAAt9AHjAAA%3D&exvsurl=1&path=/calendar/item",
    "onlineMeetingUrl":null,
    "isOnlineMeeting": true,
    "onlineMeetingProvider": "teamsForBusiness",
    "start":{ "dateTime":"2017-04-15T11:00:00.0000000", "timeZone":"Pacific Standard Time" },
    "end":{ "dateTime":"2017-04-15T12:00:00.0000000", "timeZone":"Pacific Standard Time" },
    "attendees":[
        { "type":"required", "status":{ "response":"none", "time":"0001-01-01T00:00:00Z" },
          "emailAddress":{ "name":"Samantha Booth", "address":"samanthab@contoso.com" } }
    ],
    "organizer":{ "emailAddress":{ "name":"Dana Swope", "address":"danas@contoso.com" } },
    "onlineMeeting": {
        "joinUrl": "https://teams.microsoft.com/l/meetup-join/19%3ameeting_NzIyNzhlMGEtM2YyZC00ZmY0LTlhNzUtZmZjNWFmZGNlNzE2%40thread.v2/0?context=%7b%22Tid%22%3a%2272f988bf-86f1-41af-91ab-2d7cd011db47%22%2c%22Oid%22%3a%22bc55b173-cff6-457d-b7a1-64bda7d7581a%22%7d",
        "conferenceId": "177513992",
        "tollNumber": "+1 425 555 0123"
    }
}
```

Source: user-post-events Example 4 response (https://learn.microsoft.com/en-us/graph/api/user-post-events?view=graph-rest-1.0). Event resource notes:
- `onlineMeetingUrl` will be deprecated; use `onlineMeeting.joinUrl`.
- `iCalUId` differs per occurrence.
- `onlineMeetingProvider` is one of `unknown`, `teamsForBusiness`, `skypeForBusiness`, `skypeForConsumer`.
- Source: https://learn.microsoft.com/en-us/graph/api/resources/event?view=graph-rest-1.0

---

## 7. Change notifications (webhooks)

Sources:
- **[CM]** https://learn.microsoft.com/en-us/graph/teams-changenotifications-chatmessage (updated 2026-04-03)
- **[SUB]** https://learn.microsoft.com/en-us/graph/api/resources/subscription?view=graph-rest-1.0 (updated 2026-09-17)
- **[POST]** https://learn.microsoft.com/en-us/graph/api/subscription-post-subscriptions?view=graph-rest-1.0
- **[WH]** https://learn.microsoft.com/en-us/graph/change-notifications-delivery-webhooks
- **[RD]** https://learn.microsoft.com/en-us/graph/change-notifications-with-resource-data
- **[LC]** https://learn.microsoft.com/en-us/graph/change-notifications-lifecycle-events
- **[TR]** https://learn.microsoft.com/en-us/graph/teams-changenotifications-callrecording-and-calltranscript
- **[MCE]** https://learn.microsoft.com/en-us/graph/changenotifications-for-onlinemeeting

### 7.1 Resources Max subscribes to

| Resource | changeType | Application permission | Max lifetime |
|---|---|---|---|
| `/teams/{team-id}/channels/{channel-id}/messages` (roots and replies; also supports `?$filter=mentions/any(u: u/mentioned/user/id eq '{id}')` and `?$search=`) | created, updated, deleted | **`ChannelMessage.Read.Group` (RSC)**, `ChannelMessage.Read.All` | 4,320 min (3 days) |
| `/teams/getAllMessages` (all channels in the tenant) | created, updated, deleted | `ChannelMessage.Read.All` (no delegated) | 4,320 min |
| `/chats/{chat-id}/messages` (for example a meeting chat) | created, updated, deleted | `Chat.Read.All`; `ChatMessage.Read.Chat` (RSC, beta only) | 4,320 min |
| `communications/onlineMeetings/{onlineMeetingId}/transcripts` | created | `OnlineMeetingTranscript.Read.All`; `OnlineMeetingTranscript.Read.Chat` (RSC, add `?useResourceSpecificConsentBasedAuthorization=true`) | 4,320 min |
| `communications/onlineMeetings/getAllTranscripts`, `users/{id}/onlineMeetings/getAllTranscripts` | created | `OnlineMeetingTranscript.Read.All` | 4,320 min |
| `communications/onlineMeetings/{id}/recordings`, `.../getAllRecordings` | created | `OnlineMeetingRecording.Read.All` (or `.Read.Chat` RSC) | 4,320 min |
| `communications/onlineMeetings(joinWebUrl='{encoded}')/meetingCallEvents` | updated | `OnlineMeetings.Read.All` (application only) | 3 days |

Notes:
- `/teams/{id}/channels/getAllMessages` and `.../messages/{id}/replies` are **not** documented subscription resources. A channel `/messages` subscription already includes replies.
- Quotas: one subscription per app per channel or chat, and 10,000 Teams subscriptions per organization (exceeding it returns 403).
- Teams subscriptions are no longer metered.
- [TOV] still says "maximum 60 minutes". That is stale; [SUB] gives 4,320 minutes.
- Transcript notifications fire only if the subscription exists **before transcription starts**.
- Private channel meetings are not supported for transcript notifications [TR].

### 7.2 `POST /subscriptions`

Verbatim from [CM], with `lifecycleNotificationUrl` added. It is required when the expiry is more than 1 hour out:

```http
POST https://graph.microsoft.com/v1.0/subscriptions
Content-Type: application/json

{
  "changeType": "created,updated",
  "notificationUrl": "https://webhook.azurewebsites.net/api/resourceNotifications",
  "lifecycleNotificationUrl": "https://webhook.azurewebsites.net/api/lifecycleNotifications",
  "resource": "/teams/{team-id}/channels/{channel-id}/messages",
  "includeResourceData": true,
  "encryptionCertificate": "{base64encodedCertificate}",
  "encryptionCertificateId": "{customId}",
  "expirationDateTime": "2019-09-19T11:00:00.0000000Z",
  "clientState": "{secretClientState}"
}
```

Field rules:
- `clientState`: at most 128 characters.
- `expirationDateTime`: values less than 45 minutes out are bumped to 45 minutes.
- `includeResourceData: true` requires `encryptionCertificate` (RSA 2048-4096, self-signed is fine).
- `lifecycleNotificationUrl` cannot be added later with PATCH.
- `latestSupportedTlsVersion` defaults to `v1_2`.

Errors:
- `400` if validation fails.
- `409 Conflict` for a duplicate subscription: "Subscription Id <> already exists for the requested combination".
- If `lifecycleNotificationUrl` is missing with an expiry over 1 hour: "lifecycleNotificationUrl is a required property for subscription creation on this resource when the expirationDateTime value is set to greater than 1 hour".

`201 Created` response (generic shape from [POST]):

```json
{
  "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#subscriptions/$entity",
  "id": "7f105c7d-2dc5-4530-97cd-4e7ae6534c07",
  "resource": "/teams/{team-id}/channels/{channel-id}/messages",
  "applicationId": "24d3b144-21ae-4080-943f-7067b395b913",
  "changeType": "created,updated",
  "clientState": "secretClientValue",
  "notificationUrl": "https://webhook.azurewebsites.net/api/resourceNotifications",
  "lifecycleNotificationUrl": "https://webhook.azurewebsites.net/api/lifecycleNotifications",
  "expirationDateTime": "2016-11-20T18:23:45.9356913Z",
  "creatorId": "8ee44408-0679-472c-bc2a-692812af3437",
  "includeResourceData": true,
  "encryptionCertificateId": "{customId}",
  "latestSupportedTlsVersion": "v1_2",
  "notificationContentType": "application/json"
}
```

Other subscription operations:
- **Renew:** `PATCH /subscriptions/{id}` with `{"expirationDateTime": "..."}`. Returns `200` and the subscription; `404` means it is gone, so recreate it [UPD: https://learn.microsoft.com/en-us/graph/api/subscription-update?view=graph-rest-1.0].
- **Reauthorize:** `POST /subscriptions/{id}/reauthorize`.
- **Delete:** `DELETE /subscriptions/{id}` returns `204`.
- **Read:** `GET /subscriptions` and `GET /subscriptions/{id}`.

### 7.3 Validation handshake [WH]
Graph sends:

```http
POST https://{notificationUrl}?validationToken={opaqueTokenCreatedByMicrosoftGraph}
Content-Type: text/plain; charset=utf-8
```

The app must reply within **10 seconds** with `200 OK`, `Content-Type: text/plain`, and the **URL-decoded** token as the body. The lifecycle URL is validated the same way; if both URLs are equal you get two validation requests.

Delivery rules:
- Respond to every notification with a 2xx within **3 seconds**: `202 Accepted` if queued, `200` if processed. Return 5xx to request a retry.
- Retries use exponential backoff for up to 4 hours, with a 10-second timeout per retry.
- Graph throttles slow endpoints:
  - "Slow": more than 10% of responses over 3 s in 10 minutes delays notifications by 10 minutes.
  - "Drop": more than 15% over 10 s drops notifications for 10 minutes, unrecoverably.
- Verify `clientState` on every notification.

### 7.4 Notification payloads

Without resource data (verbatim [CM] item; the delivered POST body wraps it in `{"value":[...]}`):

```json
{
  "value": [
    {
      "subscriptionId": "9f9d1ed0-c9cc-42e7-8d80-a7fc4b0cda3c",
      "changeType": "created",
      "tenantId": "<<--TenantForWhichNotificationWasSent-->>",
      "clientState": "<<--SpecifiedClientState-->>",
      "subscriptionExpirationDateTime": "2021-02-02T11:26:41.0537895-08:00",
      "resource": "teams('fbe2bf47-16c8-47cf-b4a5-4b9b187c508b')/channels('19:4a95f7d8db4c4e7fae857bcebe0623e6@thread.tacv2')/messages('1612293113399')",
      "resourceData": {
        "id": "1612293113399",
        "@odata.type": "#Microsoft.Graph.chatMessage",
        "@odata.id": "teams('fbe2bf47-16c8-47cf-b4a5-4b9b187c508b')/channels('19:4a95f7d8db4c4e7fae857bcebe0623e6@thread.tacv2')/messages('1612293113399')"
      }
    }
  ]
}
```

- Replies use `resource: "teams('..')/channels('..')/messages('{rootId}')/replies('{replyId}')"`.
- `@odata.type` casing varies (`chatMessage` / `ChatMessage`), so compare case-insensitively.

With encrypted resource data (verbatim [RD]):

```json
{
  "value": [
    {
      "subscriptionId": "76222963-cc7b-42d2-882d-8aaa69cb2ba3",
      "changeType": "created",
      "resource": "teams('d29828b8-c04d-4e2a-b2f6-07da6982f0f0')/channels('19:f127a8c55ad949d1a238464d22f0f99e@thread.skype')/messages('1565045424600')/replies('1565047490246')",
      "resourceData": {
        "id": "1565293727947",
        "@odata.type": "#Microsoft.Graph.ChatMessage",
        "@odata.id": "teams('88cbc8fc-164b-44f0-b6a6-b59b4a1559d3')/channels('19:8d9da062ec7647d4bb1976126e788b47@thread.tacv2')/messages('1565293727947')/replies('1565293727947')"
      },
      "encryptedContent": {
        "data": "{encrypted data that produces a full resource}",
        "dataSignature": "<HMAC-SHA256 hash>",
        "dataKey": "{encrypted symmetric key from Microsoft Graph}",
        "encryptionCertificateId": "MySelfSignedCert/DDC9651A-D7BC-4D74-86BC-A8923584B0AB",
        "encryptionCertificateThumbprint": "07293748CC064953A3052FB978C735FB89E61C3D"
      }
    }
  ],
  "validationTokens": [ "eyJ0eXAiOiJKV1QiLCJhbGciOiJSU..." ]
}
```

Real payloads also carry `tenantId`, `clientState` and `subscriptionExpirationDateTime`.

Decryption [RD]. The simulator must implement the inverse.
1. Select the private key by `encryptionCertificateId`.
2. Base64-decode `dataKey` and RSA-OAEP decrypt it (SHA-1 OAEP in the samples) to get the symmetric key (32 bytes).
3. Compute HMAC-SHA256 over the base64-decoded `data`, keyed with the symmetric key. It must equal base64-decoded `dataSignature`; if not, reject.
4. AES-256-CBC with PKCS7 padding. The IV is the **first 16 bytes of the symmetric key**.
5. The result is UTF-8 JSON of the full chatMessage, the same shape as GET (section 3.1). rich chatMessage notifications don't support `$select`.

`validationTokens` (JWT) checks [RD]:
- Not expired.
- Signature valid against Microsoft identity keys (`https://login.microsoftonline.com/common/discovery/v2.0/keys`).
- `aud` equals the app's client ID.
- `azp` (v2) or `appid` (v1) equals `0bf30f3b-4a52-48df-9a82-234910c4a086` (the "Microsoft Graph Change Tracking" app).
- `iss` is `https://login.microsoftonline.com/{tid}/v2.0` or `https://sts.windows.net/{tid}/`.
- Example claims: `{"aud": "925bff9f-...", "iss": "https://login.microsoftonline.com/9f4ebab6-.../v2.0", "azp": "0bf30f3b-4a52-48df-9a82-234910c4a086", "tid": "9f4ebab6-...", "ver": "2.0", "exp": ..., "nbf": ...}`.

Transcript notification (verbatim [TR]):

```json
{
  "subscriptionId": "0cc28c98-4d2a-4a34-b850-815d7e6486ea",
  "changeType": "created",
  "tenantId": "<<--TenantForWhichNotificationWasSent-->>",
  "clientState": "<<--SpecifiedClientState-->>",
  "subscriptionExpirationDateTime": "2023-09-17T08:29:11.3173971+00:00",
  "resource": "users/{organizer-id}/onlineMeetings('Mso...')/transcripts('MSM...')",
  "resourceData": {
    "id": "MSM...",
    "@odata.type": "#Microsoft.Graph.callTranscript",
    "@odata.id": "users/{organizer-id}/onlineMeetings('Mso...')/transcripts('MSM...')"
  }
}
```

Meeting call event (decrypted, verbatim [MCE]). `eventType` is `callStarted`, `callEnded` or `rosterUpdated`:

```json
{
  "@odata.type": "#microsoft.graph.callevent",
  "@odata.id": "communications/onlineMeetings(joinWebUrl='{joinWebUrl}')/meetingCallEvents",
  "id": "{notificationId}",
  "eventType": "rosterUpdated",
  "eventDateTime": "2022-02-28T00:00:00.0000000Z",
  "participants@delta": [
    { "info": { "identity": { "user": { "id": "e98eb11c-8385-445e-8b19-4a2f169ac5bc", "displayName": "User that is leaving the call", "tenantId": "f69f5191-20ae-4093-8dae-3ec09edeb253" } } },
      "isInLobby": false, "removedState": { "reason": "Participant has left the meeting call." }, "id": "347040dd-aa51-4ada-8a44-510c65a3a2d3" }
  ]
}
```

### 7.5 Lifecycle notifications [LC]

```json
{
  "value": [
    {
      "subscriptionId":"<subscription_guid>",
      "subscriptionExpirationDateTime":"2019-03-20T11:00:00.0000000Z",
      "tenantId": "<tenant_guid>",
      "clientState":"<secretClientState>",
      "lifecycleEvent": "subscriptionRemoved or missed or reauthorizationRequired"
    }
  ]
}
```

- Teams chatMessage supports `reauthorizationRequired` and `subscriptionRemoved`. `missed` is Outlook only.
- Handling:
  - `reauthorizationRequired`: call `POST /subscriptions/{id}/reauthorize` or `PATCH` a new expiry.
  - `subscriptionRemoved`: recreate the subscription, then resync with delta or GET.
- Respond `202`.

---

## 8. Auth

### 8.1 App-only (client credentials)
Sources:
- https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-client-creds-grant-flow
- https://learn.microsoft.com/en-us/graph/auth-v2-service

```http
POST https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token
Content-Type: application/x-www-form-urlencoded

client_id={appId}&scope=https%3A%2F%2Fgraph.microsoft.com%2F.default&client_secret={secret}&grant_type=client_credentials
```

- For a certificate, replace `client_secret` with `client_assertion_type=urn%3Aietf%3Aparams%3Aoauth%3Aclient-assertion-type%3Ajwt-bearer&client_assertion={signed JWT}`.
- No refresh token is issued.

Response (verbatim):

```json
{ "token_type": "Bearer", "expires_in": 3599, "ext_expires_in":3599, "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsIng1dCI6Ik1uQ19WWmNBVGZNNXBP..." }
```

Error (verbatim):

```json
{ "error": "invalid_scope", "error_description": "AADSTS70011: The provided value for the input parameter 'scope' is not valid. ...", "error_codes": [70011], "timestamp": "YYYY-MM-DD HH:MM:SSZ", "trace_id": "0000aaaa-11bb-cccc-dd22-eeeeee333333", "correlation_id": "aaaa0000-bb11-2222-33cc-444444dddddd" }
```

Token claims:
- `aud`: Graph. In practice `https://graph.microsoft.com` (v1 tokens) or `00000003-0000-0000-c000-000000000000` (UNVERIFIED which form).
- `iss`: `https://sts.windows.net/{tid}/`.
- `roles[]`: the application permissions. It may be absent when only RSC is used; in that case RSC grants are evaluated per team or chat.
- `appid`, `tid`, `idtyp: "app"` (UNVERIFIED value).
- No `scp`.

Admin consent URL: `https://login.microsoftonline.com/{tenant}/adminconsent?client_id=...`. All application permissions require admin consent.

Delegated flows (authorization code, Teams SSO plus on-behalf-of) are used only if Max ever acts as a user. Max's design is app-only plus RSC.

### 8.2 Resource-specific consent (RSC)
Sources:
- https://learn.microsoft.com/en-us/microsoftteams/platform/graph-api/rsc/resource-specific-consent (updated 2026-11-02)
- https://learn.microsoft.com/en-us/microsoftteams/platform/graph-api/rsc/declare-resource-specific-consent-requirements

Manifest (v1.12+):

```json
{
  "webApplicationInfo": { "id": "{Entra app id}", "resource": "https://RscBasedStoreApp" },
  "authorization": { "permissions": { "resourceSpecific": [
    { "name": "ChannelMessage.Read.Group", "type": "Application" },
    { "name": "TeamMember.Read.Group", "type": "Application" },
    { "name": "ChannelSettings.Read.Group", "type": "Application" },
    { "name": "TeamSettings.Read.Group", "type": "Application" },
    { "name": "File.Read.Group", "type": "Application" },
    { "name": "OnlineMeetingTranscript.Read.Chat", "type": "Application" },
    { "name": "OnlineMeeting.ReadBasic.Chat", "type": "Application" },
    { "name": "ChatMessage.Read.Chat", "type": "Application" }
  ] } }
}
```

- At most 16 RSC permissions per app.
- RSC is granted when a team owner (or member, subject to policy) installs the app in the team, or a meeting organizer installs it in the meeting.
- Tenant admins can gate it.
- Check grants with `GET /teams/{team-id}/permissionGrants`.
- Channel RSC covers all channels except private and shared ones, which need the app added explicitly.

### 8.3 Permission matrix for Max (application context)

| API | Least privileged (RSC) | Tenant-wide (admin consent) | Extra gate |
|---|---|---|---|
| GET team | TeamSettings.Read.Group | Team.ReadBasic.All / TeamSettings.Read.All | - |
| GET channels / channel | ChannelSettings.Read.Group | Channel.ReadBasic.All | - |
| GET members | TeamMember.Read.Group | TeamMember.Read.All | - |
| GET messages / replies / delta | ChannelMessage.Read.Group | ChannelMessage.Read.All | Owner tenant only (federation) |
| GET channels/getAllMessages | - | ChannelMessage.Read.All | - |
| POST messages / replies (Graph) | - | Teamwork.Migrate.All (migration only) | **Use Bot Connector instead** |
| filesFolder | File.Read.Group | Files.Read.All | - |
| drive children / content | (RSC UNVERIFIED) | Files.Read.All / Sites.Read.All / Sites.Selected | Sites.Selected needs a per-site grant |
| /shares/{id}/driveItem | - | Files.ReadWrite.All | Write scope |
| onlineMeetings get/filter | - (OnlineMeeting.ReadBasic.Chat exists in RSC) | OnlineMeetings.Read.All | **CsApplicationAccessPolicy** |
| transcripts | OnlineMeetingTranscript.Read.Chat (chat meetings only) | OnlineMeetingTranscript.Read.All | **Access policy + tenant "Transcript API access" ON** |
| recordings | OnlineMeetingRecording.Read.Chat | OnlineMeetingRecording.Read.All | Access policy |
| aiInsights | - | OnlineMeetingAiInsight.Read.All | Access policy + Copilot license |
| calendarView / events | - | Calendars.ReadBasic / Calendars.Read | Exchange RBAC for Applications to scope |
| subscriptions: channel messages | ChannelMessage.Read.Group | ChannelMessage.Read.All | Encryption cert if includeResourceData |
| subscriptions: /teams/getAllMessages | - | ChannelMessage.Read.All | - |
| subscriptions: transcripts | OnlineMeetingTranscript.Read.Chat | OnlineMeetingTranscript.Read.All | Tenant transcript switch |
| subscriptions: meetingCallEvents | - | OnlineMeetings.Read.All | - |

Notes:
- Protected API form: none appears required as of 2026-11 (section 0).
- Metering: none since 2025-08-25.

---

## 9. Paging, throttling, errors

### 9.1 Paging
Source: https://learn.microsoft.com/en-us/graph/paging

- Follow `@odata.nextLink` until it is absent.
- Use the whole URL. Don't extract or modify `$skiptoken`; it already encodes the original parameters.
- A page can have zero items.
- Page sizes differ per API:
  - messages: default 20, max 50
  - replies: max 50
  - members: default 100, max 999
  - drive children: 200
  - aiInsights: 20
- A `$top` above the max may be capped or rejected.
- Delta APIs end with `@odata.deltaLink`.
- `@odata.count` appears on Teams lists.

### 9.2 Throttling
Sources:
- https://learn.microsoft.com/en-us/graph/throttling
- https://learn.microsoft.com/en-us/graph/throttling-limits

Verbatim 429:

```http
HTTP/1.1 429 Too Many Requests
Content-Length: 312
Content-Type: application/json
Retry-After: 10

{
  "error": {
    "code": "TooManyRequests",
    "innerError": {
      "code": "429",
      "date": "2020-08-18T12:51:51",
      "message": "Please retry after",
      "request-id": "94fb3b52-452a-4535-a601-69e0a90e3aa2",
      "status": "429"
    },
    "message": "Please retry again later."
  }
}
```

- Honor `Retry-After` (seconds). Without it, use exponential backoff.
- `503` may also carry `Retry-After`.
- In JSON `$batch`, each item is throttled individually.

Teams limits (per app / per app per tenant / per resource / per user). A sustained limit of about 83% of these values is evaluated over a longer window.

| Request | Per app | Per app per tenant | Per resource | Per user |
|---|---|---|---|---|
| GET channel messages | 200 rps | 20 rps | 1 rps per channel | - |
| POST channel messages / replies | 500 rps | 50 rps | 1 rps per channel | 1 rps |
| GET /teams/{id}/channels, /members | 1200 rps | 60 rps | 4 rps per team | - |
| getAllMessages (channels/chats) | 1000 rps | 200 rps | - | - |
| Default GET | 1500 rps | 30 rps | 1 rps per chat/channel | 1 rps |
| Subscriptions POST/PATCH/DELETE | 2000 / 20 s | 500 / 20 s | - | - |

**1 rps per channel** matters most for Max. Backfilling one channel with `$top=50` pages is limited to one request per second.

### 9.3 Error format
Source: https://learn.microsoft.com/en-us/graph/errors

```json
{
  "error": {
    "code": "badRequest",
    "message": "Uploaded fragment overlaps with existing data.",
    "innerError": { "code": "invalidRange", "request-id": "request-id", "date": "date-time" }
  }
}
```

- Code against `error.code` and `innerError.code`, never `message`. `innerError` can nest.
- `details[]` is used for batch operations.
- Response headers include `request-id` and `client-request-id`. `x-ms-ags-diagnostic` is observed (UNVERIFIED in docs).
- Status codes in use: 400, 401, 403, 404, 409, 410, 412, 429, 500, 503, 504.
- Codes Max should handle (UNVERIFIED as a list; the current docs page no longer tabulates them):
  - `InvalidAuthenticationToken` (401)
  - `Forbidden` / `accessDenied` (403), plus the special 403s in sections 5.1 and 5.2
  - `NotFound` / `itemNotFound` (404)
  - `BadRequest` (400)
  - `TooManyRequests` (429)
  - `resyncRequired` (410 on drive delta)

---

## 10. What our simulator must imitate

General rules for every mock:
- Host the simulator at a configurable base. Max's Graph client should only swap `https://graph.microsoft.com` for `http://localhost:{port}/graph` and `https://login.microsoftonline.com` for `http://localhost:{port}/login`. Keep the `/v1.0/...` path prefix identical.
- Accept channel IDs raw (`19:x@thread.tacv2`) and percent-encoded.
- Accept and ignore unknown OData parameters only where Graph does. Reject `$filter` on messages list with `400`, as Graph does.
- Every JSON response includes `@odata.context`. Every response sets the `request-id` and `client-request-id` headers. Errors use the section 9.3 envelope.
- Validate `Authorization: Bearer` on every call. Return `401 InvalidAuthenticationToken` if it is missing or expired. Enforce per-team RSC grants or tenant-wide `roles` and return `403` accordingly. This lets Max's error handling be tested.
- Fault injection toggles:
  - `429` with `Retry-After`, including the 1 rps per channel rule
  - `503`
  - `403 No application access policy found for this app`
  - `403 GraphAccessToTranscriptsDisabled`
  - `403 SpeakerAttributionNotAllowed`
  - `404` for an expired meeting
  - `410` on drive delta
  - `400 DeltaFilterNotAllowed`

### 10.1 MUST-HAVE for Max (P0)

| # | Endpoint | Behavior to mock |
|---|---|---|
| 1 | `POST /{tenant}/oauth2/v2.0/token` (login host) | client_credentials (secret and certificate assertion); returns `{token_type, expires_in: 3599, ext_expires_in, access_token}` as a JWT with `aud`, `iss`, `tid`, `appid`, `roles`; `invalid_client` / `invalid_scope` errors in AADSTS shape |
| 2 | `GET /v1.0/teams/{id}` | team object (section 2.1) |
| 3 | `GET /v1.0/teams/{id}/channels` (+`$filter=membershipType eq '...'`, `$select`) and `GET /v1.0/teams/{id}/channels/{id}` | channel objects (section 2.2) |
| 4 | `GET /v1.0/teams/{id}/members` (+`$filter`, `$top`) | aadUserConversationMember list (section 2.3) |
| 5 | `GET /v1.0/teams/{id}/channels/{id}/messages?$top=N&$expand=replies` | roots only, sorted by reply-chain last-modified; `$top` max 50; `@odata.count`; opaque `$skiptoken` nextLink; `replies@odata.nextLink` when there are more than 200 replies |
| 6 | `GET .../messages/{id}` and `GET .../messages/{id}/replies[/{replyId}]` | chatMessage (section 3.1.4) with mentions, file `reference` attachments, reactions, `replyToId`, `webUrl` with `parentMessageId` |
| 7 | `GET .../messages/delta` (+`$filter=lastModifiedDateTime gt`, `$top`, `$expand=replies`) | nextLink/deltaLink token cycle; 8-month window; deleted messages appear with `deletedDateTime` set |
| 8 | `POST /v1.0/subscriptions`, `PATCH /subscriptions/{id}`, `DELETE`, `GET`, `POST /subscriptions/{id}/reauthorize` | validationToken handshake (10 s, plain text), 45-minute minimum and 4,320-minute maximum expiry, lifecycle URL required above 1 h, 409 on duplicate, `clientState` echo |
| 9 | Outbound webhook POSTs to Max | `{"value":[...]}` change notifications for channel messages (created/updated/deleted, roots and replies, mention filter), **with encrypted resource data** (RSA-OAEP plus AES-CBC plus HMAC, `validationTokens` JWT with `azp=0bf30f3b-...`) and without it; retry on non-2xx; lifecycle `reauthorizationRequired` and `subscriptionRemoved` |
| 10 | `GET /v1.0/teams/{id}/channels/{id}/filesFolder` | folder driveItem with `parentReference.driveId` |
| 11 | `GET /v1.0/drives/{driveId}/items/{itemId}/children` and `GET /v1.0/drives/{driveId}/items/{itemId}` | file/folder driveItems (section 4.2 COMPOSITE), `@microsoft.graph.downloadUrl` that expires after 1 h, 200-item pages |
| 12 | `GET /v1.0/drives/{driveId}/items/{itemId}/content` | `302 Found` with `Location` set to a simulator pre-auth URL (no Bearer needed); `Range` gives 206 |
| 13 | `GET /v1.0/users/{userId}/onlineMeetings?$filter=JoinWebUrl eq '...'` and `GET .../onlineMeetings/{id}` | onlineMeeting (section 5.1) with `chatInfo.threadId`, participants, `joinMeetingIdSettings`; access-policy 403 toggle |
| 14 | `GET /v1.0/users/{userId}/onlineMeetings/{id}/transcripts`, `/{tid}`, `/{tid}/content` (`$format=text/vtt` or `Accept`), `/{tid}/metadataContent` | callTranscript JSON and WEBVTT with `<v Speaker>` tags; tenant-switch 403s; empty list until "transcript ready" |
| 15 | Transcript change notification (`communications/onlineMeetings/{id}/transcripts` or `users/{id}/onlineMeetings/getAllTranscripts`, `created`) | notify Max when the simulated meeting ends and the transcript becomes available |
| 16 | `GET /v1.0/users/{id}/calendarView?startDateTime&endDateTime` (+`Prefer: outlook.timezone`) | events with `isOnlineMeeting`, `onlineMeetingProvider: "teamsForBusiness"`, `onlineMeeting.joinUrl`, `iCalUId`; recurring series expanded |
| 17 | Error, throttling and paging behavior | sections 9.1-9.3 envelopes on all of the above |

The Bot Framework connector is not Graph and is covered in the bot research doc. The simulator still must provide `POST {serviceUrl}/v3/conversations` and `.../activities[/{id}]` for Max to post. Messages posted through it must then appear in the Graph messages, replies and delta endpoints with `from.application` set to the bot, and fire channel-message change notifications. This round-trip is essential.

### 10.2 NICE-TO-HAVE (P1/P2)

| Priority | Endpoint | Why |
|---|---|---|
| P1 | `GET /v1.0/teams/{id}/channels/getAllMessages` | Faster initial backfill |
| P1 | `/teams/getAllMessages` subscription resource | Tenant-wide listening instead of per-channel |
| P1 | `GET /v1.0/shares/u!{b64}/driveItem[/content]` | Resolve attachment `contentUrl` to a driveItem |
| P1 | `GET /v1.0/drives/{id}/root/delta` (`token=latest`, deleted facet, 410 resync) | Incremental file indexing |
| P1 | `GET .../recordings`, `.../recordings/{id}/content` (video/mp4) | Recording links in summaries |
| P1 | `getAllTranscripts(...)` / `getAllRecordings(...)` plus delta | Organizer-wide sweep |
| P1 | `communications/onlineMeetings(joinWebUrl='...')/meetingCallEvents` notifications (`callStarted`, `callEnded`, `rosterUpdated`) | Know when a meeting starts or ends without the bot joining |
| P1 | `GET /v1.0/teams/{id}/permissionGrants` | Max can verify its RSC grants |
| P1 | `meetingReference` attachments in channel posts, plus `GET /users/{id}/events/{exchangeId}` | Channel meeting discovery |
| P2 | `GET /v1.0/copilot/users/{id}/onlineMeetings/{id}/aiInsights[/{id}]` | Copilot interop; not needed by Max |
| P2 | `POST .../messages` and `.../replies` via Graph (delegated `ChannelMessage.Send` only; app-only returns 403 unless `Teamwork.Migrate.All`) | Emulate correctly so Max doesn't accidentally depend on it |
| P2 | `?format=pdf` conversion (2 MB limit) | Document preview |
| P2 | `/chats/{id}/messages` (meeting chat) list and subscription | Meeting-chat context |
| P2 | `GET /groups/{id}/calendarView` | Mirror the doc ambiguity: 403 for app-only by default |
| P2 | JSON `$batch` (`POST /v1.0/$batch`) with per-item 429 | Only if Max adopts batching |

### 10.3 Simulator data model implied
- `Tenant` holds Users, Teams (= Groups), Channels (standard, private, shared), Messages (root and replies, a tree), Reactions, and Mentions (user, bot, channel, team, "everyone").
- `Drive` holds Folders (one per channel) and Files (bytes, mimeType, quickXorHash).
- `OnlineMeetings` link to calendar Events (organizer mailbox plus attendee copies sharing `iCalUId`), Transcripts (VTT), and Recordings.
- `AppRegistration` holds appId, secrets/certs, and granted `roles`. Separately, per-team `RSC grants`, access policies (`CsApplicationAccessPolicy` per user or global), and tenant flags (`EnableGraphTranscriptAccess`, `EnableAttributedTranscripts`).
- `Subscriptions` carry an expiry timer, a lifecycle timer, an encryption certificate, and a delivery queue with retry/backoff.

---

## 11. Open questions / to verify against a real tenant
1. Whether RSC `File.Read.Group` alone allows `/drives/{id}/items/{id}/children` and `/content`, or only `filesFolder`.
2. The current v1.0 reference for `GET /teams/{id}/channels/{id}/messages/delta`. The docs page now shows only chats; check whether the 8-month and `$filter` rules still hold for channels.
3. The exact status and body when a transcript isn't ready yet: empty list or 404.
4. Whether the Bot Connector `activityId` always equals the Graph `chatMessage.id`, and the `;messageid=` conversation ID with `@thread.tacv2`.
5. App-only access to `/groups/{id}/calendarView`.
6. Whether `ChannelMessage.Send.Group` (RSC) authorizes any Graph POST in app-only context.
7. Exact `aud` and `idtyp` claim values in Graph app-only tokens, so simulator tokens look identical.
8. Whether the transcript change notification for channel meetings works with only `OnlineMeetingTranscript.Read.All` plus the access policy (it does not work with RSC).
