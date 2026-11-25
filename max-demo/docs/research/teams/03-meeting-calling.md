# 03: Teams meeting and calling integration (Graph Cloud Communications and the Real-time Media Platform)

Research date: 2026-11-20. Scope: how a bot ("Max") joins and takes part in a Teams meeting, and which meeting-side app features it can use. The goal is to tell the rmeet-ai simulator exactly what contracts to imitate.

**Legend**
- **[Verified]**: read directly from an official Microsoft Learn page or the official sample repo on 2026-11-20 (URL given inline).
- **[Secondary]**: from community Q&A, a roadmap mirror, or press coverage. Treat as likely but not authoritative.
- **[Unverified]**: my inference or memory. Not confirmed against a current source.

---

## 0. TL;DR

1. **Joining.** The bot joins with `POST https://graph.microsoft.com/v1.0/communications/calls` using `chatInfo` and `meetingInfo`, or `joinMeetingIdMeetingInfo`. It passes `mediaConfig` set to `appHostedMediaConfig` (raw media, through the Windows-only .NET media SDK) or `serviceHostedMediaConfig` (Microsoft does the media; IVR only). The response is `201 Created` with `state: "establishing"`. [Verified]
2. **Signalling.** All later signalling arrives as `commsNotifications` POSTs to the `callbackUri`, carrying a bearer JWT (`iss = https://api.botframework.com`, `aud =` the bot app ID). There are three kinds: call state (`establishing` → `established` → `terminating` → `terminated`), roster (`/participants`, full or delta), and operation completions (`/operations/{id}`). [Verified]
3. **Media.** Audio is PCM 16 kHz, 16-bit mono, in 20 ms frames (320 samples, 640 bytes), 50 per second. Mixed audio arrives with `ActiveSpeakers` (an array of MSIs, the media source IDs). Unmixed audio covers up to 4 top speakers at once, each tagged with `ActiveSpeakerId`. To find the speaker, match the MSI to `participant.mediaStreams[].sourceId` in the roster. The bot sends audio with `AudioSocket.Send(AudioMediaBuffer)`, one 640-byte frame per 20 ms. [Verified]
4. **Hosting.** App-hosted media still needs, in November 2026, C#/.NET on **Windows Server in Azure**, an instance-level public IP, a certificate and a per-instance media port. There is **no Linux support**. Microsoft now says on Learn that real-time media bots are **"not recommended for AI agent scenarios"** (updated 2026-05-29). [Verified]
5. **Recording rule.** Before persisting any media or anything derived from it (including transcripts), the bot must call `updateRecordingStatus` with `recording` and receive a success reply. [Verified]
6. **Lobby.** 2026 "external bot detection" (`ExternalBotAccessMode = RequireApprovalWhenDetected`, the default) holds *external* bots in the lobby. A same-tenant, app-identity Graph bot is reportedly treated as trusted and is not affected. [Secondary] Guest-identity joins (`Calls.JoinGroupCallAsGuest.All`) land in the lobby under normal lobby rules. [Verified, sample comment]
7. **Meeting chat and apps.** These go through the Bot Connector (`{serviceUrl}/v3/conversations/{19:meeting_...@thread.v2}/activities`) plus the meeting APIs `GET /v1/meetings/{id}`, `GET /v1/meetings/{id}/participants/{pid}` and `POST /v1/meetings/{id}/notification`. Lifecycle events are `application/vnd.microsoft.meetingStart`, `...meetingEnd`, `...meetingParticipantJoin` and `...meetingParticipantLeave`. [Verified]
8. **Real-time alternatives.** Work IQ real-time transcripts (delegated, admin toggle `-EnableWorkIQTranscriptAccess`, enforced from 2026-11-14; roadmap RM570651 says GA November 2026) is the Microsoft-blessed path for AI agents. It gives text only, with no audio and no way to speak back. [Verified, admin doc; Secondary, roadmap]

---

## 1. Joining a meeting

### 1.1 Endpoint

```
POST https://graph.microsoft.com/v1.0/communications/calls
Authorization: Bearer {app-only token, scope https://graph.microsoft.com/.default}
Content-Type: application/json
```

- The response is `201 Created`, with a `Location: https://graph.microsoft.com/v1.0/communications/calls/{callId}` header and a body containing the `call` resource with `"state": "establishing"` and `myParticipantId`. [Verified: https://learn.microsoft.com/en-us/graph/api/application-post-calls?view=graph-rest-1.0]
- The call has a `mediaConfig` property: either `appHostedMediaConfig` or `serviceHostedMediaConfig` (required). `meetingInfo` can be `organizerMeetingInfo`, `tokenMeetingInfo` or `joinMeetingIdMeetingInfo`. [Verified: https://learn.microsoft.com/en-us/graph/api/resources/call?view=graph-rest-1.0]
- The same app can join the same meeting more than once, but each join needs a separate identity. Inviting more than one bot into a meeting is not allowed. [Verified: call resource page; https://learn.microsoft.com/en-us/graph/api/participant-invite?view=graph-rest-1.0]

### 1.2 Example A: scheduled meeting, app-hosted media (Max's real target)

This is the request from Example 6 of the create-call page. The `blob` is produced by the .NET media SDK (`ICommunicationsClient.CreateMediaSession(...)`). It is an opaque serialized media-session configuration, which the docs show only as `"<Media Session Configuration>"`. [Verified]

```json
POST https://graph.microsoft.com/v1.0/communications/calls
Content-Type: application/json

{
  "@odata.type": "#microsoft.graph.call",
  "direction": "outgoing",
  "callbackUri": "https://bot.contoso.com/callback",
  "requestedModalities": [ "audio" ],
  "mediaConfig": {
    "@odata.type": "#microsoft.graph.appHostedMediaConfig",
    "blob": "<Media Session Configuration>"
  },
  "chatInfo": {
    "@odata.type": "#microsoft.graph.chatInfo",
    "threadId": "19:meeting_Win6Ydo4wsMijFjZS00ZGVjLTk5MGUtOTRjNWY2NmNkYTFm@thread.v2",
    "messageId": "0"
  },
  "meetingInfo": {
    "@odata.type": "#microsoft.graph.organizerMeetingInfo",
    "organizer": {
      "@odata.type": "#microsoft.graph.identitySet",
      "user": {
        "@odata.type": "#microsoft.graph.identity",
        "id": "5810cede-f3cc-42eb-b2c1-e9bd5d53ec96",
        "tenantId": "aa67bd4c-8475-432d-bd41-39f255720e0a",
        "displayName": "Bob"
      }
    },
    "allowConversationWithoutHost": true
  },
  "tenantId": "aa67bd4c-8475-432d-bd41-39f255720e0a"
}
```

The response is abridged here to the fields that matter. It comes from Example 6 on the same page. [Verified]

```json
HTTP/1.1 201 Created
Location: https://graph.microsoft.com/v1.0/communications/calls/2f1a1100-b174-40a0-aba7-0b405e01ed92

{
  "@odata.type": "#microsoft.graph.call",
  "state": "establishing",
  "direction": "outgoing",
  "callbackUri": "https://bot.contoso.com/callback",
  "requestedModalities": [ "audio" ],
  "mediaConfig": { "@odata.type": "#microsoft.graph.appHostedMediaConfig", "blob": "<Media Session Configuration>" },
  "chatInfo": { "threadId": "19:meeting_Win6Ydo4wsMijFjZS00ZGVjLTk5MGUtOTRjNWY2NmNkYTFm@thread.v2", "messageId": "0", "replyChainMessageId": null },
  "meetingInfo": { "@odata.type": "#microsoft.graph.organizerMeetingInfo", "organizer": { "user": { "id": "5810cede-...", "tenantId": "aa67bd4c-...", "displayName": "Bob" } }, "allowConversationWithoutHost": true },
  "tenantId": "aa67bd4c-8475-432d-bd41-39f255720e0a",
  "myParticipantId": "05491616-385f-44a8-9974-18cc5f9933c1",
  "id": "2f1a1100-b174-40a0-aba7-0b405e01ed92",
  "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#app/calls/$entity",
  "resultInfo": null,
  "mediaState": null,
  "toneInfo": null
}
```

Media-session options the SDK encodes into that blob, taken from the official EchoBot sample (`BotService.CreateLocalMediaSession`). [Verified: https://github.com/microsoftgraph/microsoft-graph-comms-samples/blob/master/Samples/PublicSamples/EchoBot/src/EchoBot/Bot/BotService.cs]

```csharp
this.Client.CreateMediaSession(
    new AudioSocketSettings {
        StreamDirections = StreamDirection.Sendrecv,
        // "Currently, the only audio format supported when receiving unmixed audio is Pcm16K"
        SupportedAudioFormat = AudioFormat.Pcm16K,
        ReceiveUnmixedMeetingAudio = false   // true => per-speaker buffers
    },
    new VideoSocketSettings { StreamDirections = StreamDirection.Inactive },
    mediaSessionId: mediaSessionId);
```

### 1.3 Example B: the same meeting with service-hosted media (for comparison)

This is Example 5 of the create-call page. The published JSON has trailing commas, which are removed here. [Verified]

```json
{
  "@odata.type": "#microsoft.graph.call",
  "callbackUri": "https://bot.contoso.com/callback",
  "requestedModalities": [ "audio" ],
  "mediaConfig": {
    "@odata.type": "#microsoft.graph.serviceHostedMediaConfig",
    "preFetchMedia": [
      { "uri": "https://cdn.contoso.com/beep.wav", "resourceId": "f8971b04-b53e-418c-9222-c82ce681a582" },
      { "uri": "https://cdn.contoso.com/cool.wav", "resourceId": "86dc814b-c172-4428-9112-60f8ecae1edb" }
    ]
  },
  "chatInfo": {
    "@odata.type": "#microsoft.graph.chatInfo",
    "threadId": "19:meeting_Win6Ydo4wsMijFjZS00ZGVjLTk5MGUtOTRjNWY2NmNkYTFm@thread.v2",
    "messageId": "0"
  },
  "meetingInfo": {
    "@odata.type": "#microsoft.graph.organizerMeetingInfo",
    "organizer": {
      "@odata.type": "#microsoft.graph.identitySet",
      "user": {
        "@odata.type": "#microsoft.graph.identity",
        "id": "5810cede-f3cc-42eb-b2c1-e9bd5d53ec96",
        "displayName": "Bob",
        "tenantId": "86dc81db-c112-4228-9222-63f3esaa1edb"
      }
    },
    "allowConversationWithoutHost": true
  },
  "tenantId": "86dc81db-c112-4228-9222-63f3esaa1edb"
}
```

Service-hosted media gives the bot **no raw audio**. It can only use `playPrompt`, `recordResponse` (at most 2 minutes, one prompt), `subscribeToTone` and `cancelMediaProcessing`. It is useless for an AI note-taker that needs per-speaker audio, but it is cheap to imitate.

### 1.4 Example C: join by joinMeetingId and passcode (no chatInfo)

This is Example 7 of the create-call page. Example 8 is the same with `"passcode": null`. [Verified]

```json
{
  "@odata.type": "#microsoft.graph.call",
  "callbackUri": "https://bot.contoso.com/callback",
  "requestedModalities": [ "audio" ],
  "mediaConfig": { "@odata.type": "#microsoft.graph.serviceHostedMediaConfig", "preFetchMedia": [] },
  "meetingInfo": {
    "@odata.type": "#microsoft.graph.joinMeetingIdMeetingInfo",
    "joinMeetingId": "1234567",
    "passcode": "psw123"
  },
  "tenantId": "86dc81db-c112-4228-9222-63f3esaa1edb"
}
```

### 1.5 Guest-identity join

With `Calls.JoinGroupCallAsGuest.All`, the SDK sets `JoinMeetingParameters.GuestIdentity = new Identity { Id = Guid.NewGuid(), DisplayName = "..." }`. The sample's comment says: *"If display name is specified, we join as anonymous (guest) user with the specified display name. This will put bot into lobby unless lobby bypass is disabled."* [Verified: EchoBot BotService.cs] (The phrase "lobby bypass is disabled" is the sample's wording and reads ambiguously. In practice the guest goes to the lobby unless the meeting lets anonymous users bypass it. [Unverified])

### 1.6 Parsing the join URL into threadId, organizer and tenant

**Long form.** [Verified: call resource page; sample `JoinInfo.cs` at https://github.com/microsoftgraph/microsoft-graph-comms-samples/blob/master/Samples/Common/Sample.Common.V1/Meetings/JoinInfo.cs]

```
https://teams.microsoft.com/l/meetup-join/19%3ameeting_NTg0NmQ3NTctZDVkZC00YzRhLThmNmEtOGQ3M2E0ODdmZDZk%40thread.v2/0?context=%7b%22Tid%22%3a%2272f988bf-86f1-41af-91ab-2d7cd011db47%22%2c%22Oid%22%3a%224b444206-207c-42f8-92a6-e332b41c88a2%22%7d
```

After URL-decoding:

```
https://teams.microsoft.com/l/meetup-join/19:meeting_NTg0...@thread.v2/0?context={"Tid":"72f988bf-...","Oid":"4b444206-..."}
```

The URL maps to the request fields as follows:

| URL part | Maps to |
|---|---|
| path segment `19:meeting_...@thread.v2` | `chatInfo.threadId` |
| next path segment (`0`, or a message id for channel meetings) | `chatInfo.messageId` |
| `context.Tid` | `tenantId` and `meetingInfo.organizer.user.tenantId` |
| `context.Oid` | `meetingInfo.organizer.user.id` (the organizer's Entra object ID) |
| `context.MessageId` (optional) | `chatInfo.replyChainMessageId` |

The sample's regex is `https://teams\.microsoft\.com.*/(?<thread>[^/]+)/(?<message>[^/]+)\?context=(?<context>{.*})`.

**Short form (new in 2026).** The repo's latest commit (2026-10-28, "Accept the short Teams meeting URL in JoinInfo.ParseJoinURL (#874)") adds handling for `https://<host>/meet/<joinMeetingId>?p=<passcode>`. The host varies by cloud, for example `teams.cloud.microsoft`. This form maps to `joinMeetingIdMeetingInfo { joinMeetingId, passcode }` with `chatInfo = null`. The tenant **cannot** be derived from it and must be supplied separately. The passcode must be parsed from the raw URL, because URL-decoding corrupts `+` and `%26`. [Verified: JoinInfo.cs and EchoBot BotService.cs at commit 4dd98c4]

**Lookup through Graph.** You can resolve a URL or ID to an `onlineMeeting`, whose `chatInfo` carries threadId and messageId, with these requests:
- `GET /users/{userId}/onlineMeetings?$filter=JoinWebUrl eq '{joinWebUrl}'`
- `GET /users/{userId}/onlineMeetings?$filter=joinMeetingIdSettings/joinMeetingId eq '{id}'`

Both need `OnlineMeetings.Read.All` (application), **plus an application access policy** granted to that user. `joinWebUrl` must be URL-encoded. [Verified: https://learn.microsoft.com/en-us/graph/api/onlinemeeting-get?view=graph-rest-1.0]

---

## 2. Callback notifications to `callbackUri`

### 2.1 Transport and authentication

These rules come from https://learn.microsoft.com/en-us/microsoftteams/platform/bots/calls-and-meetings/call-notifications. [Verified]

- Every notification is an HTTPS `POST` to the `callbackUri` given on the call, or to the bot's calling webhook for incoming calls. The `callbackUri` must be HTTPS.
- The `Authorization: Bearer <JWT>` header carries the claims `iss = "https://api.botframework.com"`, `aud = <bot app ID>` and `tid = <tenant>`, plus `iat`, `nbf` and `exp`. Validate the signature against the OpenID config at `https://api.aps.skype.com/v1/.well-known/OpenIdConfiguration`. (The page's sample misspells the header as "Authentication:". The real header is Authorization.)
- The first incoming-call notification can arrive in a **legacy** format. Reply `204 No Content` and it is re-sent in Graph format.
- If the bot needs a different region or instance, it replies `302 Found` with a `Location` header.
- How fast to answer is not stated on that page. The SDK replies `202 Accepted` and processes the notification asynchronously. [Unverified]

### 2.2 Envelope

```json
{
  "@odata.type": "#microsoft.graph.commsNotifications",
  "value": [
    {
      "@odata.type": "#microsoft.graph.commsNotification",
      "changeType": "created | updated | deleted",
      "resource": "/app/calls/{id}...",          // legacy-style path, present on some payloads
      "resourceUrl": "/communications/calls/{id}[/participants | /operations/{opId}]",
      "callbackUri": "https://bot.contoso.com/callback",
      "resourceData": { ... }                     // object (call/operation) OR array (participants)
    }
  ]
}
```

`resourceData` is an **object** for call and operation notifications and an **array** for participant notifications. [Verified, from the examples below]

### 2.3 Call state transitions

The `callState` enum has these values: `incoming`, `establishing`, `ringing`, `established`, `hold`, `transferring`, `transferAccepted`, `redirecting`, `terminating`, `terminated`. [Verified: call resource]

The meeting-join path is `establishing` → `established` → (`terminating`) → `terminated`. The docs warn: *"Call establishing/established notifications may arrive out of order."* [Verified]

**establishing** [Verified: create-call Example 1]
```json
{
  "@odata.type": "#microsoft.graph.commsNotifications",
  "value": [{
    "@odata.type": "#microsoft.graph.commsNotification",
    "changeType": "updated",
    "resourceUrl": "/communications/calls/2e1a0b00-2db4-4022-9570-243709c565ab",
    "callbackUri": "https://bot.contoso.com/callback",
    "resourceData": { "@odata.type": "#microsoft.graph.call", "state": "establishing", "id": "2e1a0b00-2db4-4022-9570-243709c565ab" }
  }]
}
```

**established** [Verified]
```json
{
  "@odata.type": "#microsoft.graph.commsNotifications",
  "value": [{
    "@odata.type": "#microsoft.graph.commsNotification",
    "changeType": "updated",
    "resourceUrl": "/communications/calls/2e1a0b00-b3c5-4b0f-99b3-c133bc1e6116",
    "callbackUri": "https://bot.contoso.com/callback",
    "resourceData": { "@odata.type": "#microsoft.graph.call", "state": "established", "direction": "outgoing", "id": "2e1a0b00-b3c5-4b0f-99b3-c133bc1e6116" }
  }]
}
```

**terminating, then terminated** (after `DELETE`, or when the meeting ends). Note that `changeType` is `"deleted"` on the terminated notification. [Verified: https://learn.microsoft.com/en-us/graph/api/call-delete?view=graph-rest-1.0]
```json
{ "@odata.type": "#microsoft.graph.commsNotifications", "value": [{
    "@odata.type": "#microsoft.graph.commsNotification", "changeType": "updated",
    "resourceUrl": "/communications/calls/57dab8b1-894c-409a-b240-bd8beae78896",
    "resourceData": { "@odata.type": "#microsoft.graph.call", "state": "terminating" } }]}
```
```json
{ "@odata.type": "#microsoft.graph.commsNotifications", "value": [{
    "@odata.type": "#microsoft.graph.commsNotification", "changeType": "deleted",
    "resourceUrl": "/communications/calls/57dab8b1-894c-409a-b240-bd8beae78896",
    "resourceData": { "@odata.type": "#microsoft.graph.call", "state": "terminated",
      "resultInfo": { "@odata.type": "#microsoft.graph.resultInfo", "code": "200", "subcode": "5001", "message": "The conversation has ended." } } }]}
```

These termination codes are the ones most worth simulating. [Verified: call-delete page]

| code | subcode | meaning |
|---|---|---|
| 200 | 4097 | Ended by other participant |
| 200 | 5000 / 5300 | Removed from the conversation by another participant |
| 200 | 5001 / 5003 | The conversation has ended |
| 200 | 5002 | All other participants left |
| 200 | 5855 | Lobby inactivity timeout (the bot was waiting in the lobby) |
| 200 | 7000 / 10550 | Ended by bot |
| 408 | 8537 | Keep-alive timeout |
| 410 | 301005 | Media connectivity failure |
| 500 | 1005 | Server connectivity error with the bot's media |

### 2.4 Roster (participants) notifications

*"For join meeting scenarios apart from call state notifications, we receive roster notifications."* [Verified]

**Delta roster disabled (the default)**: the full roster. This example is from create-call Example 5. [Verified]
```json
{
  "@odata.type": "#microsoft.graph.commsNotifications",
  "value": [{
    "@odata.type": "#microsoft.graph.commsNotification",
    "changeType": "updated",
    "resourceUrl": "/communications/calls/2f1a1100-b174-40a0-aba7-0b405e01ed92/participants",
    "callbackUri": "https://bot.contoso.com/callback",
    "resourceData": [
      {
        "@odata.type": "#microsoft.graph.participant",
        "info": {
          "@odata.type": "#microsoft.graph.participantInfo",
          "identity": {
            "@odata.type": "#microsoft.graph.identitySet",
            "user": { "@odata.type": "#microsoft.graph.identity", "displayName": "John", "id": "112f7296-5fa4-42ca-bae8-6a692b15d4b8" }
          },
          "languageId": "en-US"
        },
        "mediaStreams": [
          { "@odata.type": "#microsoft.graph.mediaStream", "mediaType": "audio", "sourceId": "1", "direction": "sendReceive", "serverMuted": false },
          { "@odata.type": "#microsoft.graph.mediaStream", "mediaType": "video", "sourceId": "2", "direction": "receiveOnly", "serverMuted": false },
          { "@odata.type": "#microsoft.graph.mediaStream", "mediaType": "videoBasedScreenSharing", "sourceId": "8", "direction": "receiveOnly", "serverMuted": false }
        ],
        "isMuted": true,
        "isInLobby": false,
        "id": "0d7664b6-6432-43ed-8d27-d9e7adec188c"
      },
      {
        "@odata.type": "#microsoft.graph.participant",
        "info": {
          "@odata.type": "#microsoft.graph.participantInfo",
          "identity": {
            "@odata.type": "#microsoft.graph.identitySet",
            "application": { "@odata.type": "#microsoft.graph.identity", "displayName": "Calling Bot", "id": "2891555a-92ff-42e6-80fa-6e1300c6b5c6" }
          }
        },
        "mediaStreams": [
          { "@odata.type": "#microsoft.graph.mediaStream", "mediaType": "audio", "sourceId": "10", "direction": "sendReceive", "serverMuted": false }
        ],
        "isMuted": false,
        "isInLobby": false,
        "id": "05491616-385f-44a8-9974-18cc5f9933c1"
      }
    ]
  }]
}
```

**Delta roster enabled**: `resourceData` is `[{ "@odata.type": "#microsoft.graph.deltaParticipants", "sequenceNumber": N, "participants": [ ...participant + "rosterSequenceNumber", optional "removedState": { "reason": "Removed from roster" } ] }]`. Delta mode is enabled through `callOptions` (`outgoingCallOptions.isDeltaRosterEnabled`, seen in the create-call responses) and has a known multi-endpoint issue. [Verified: create-call page; call resource known issues]

The mute notification shows that a stream may carry `"label": "main-audio"`, and that `isMuted` flips to true. [Verified: https://learn.microsoft.com/en-us/graph/api/call-mute?view=graph-rest-1.0]

**Participant properties** are `id`, `info` (participantInfo: identity, languageId, region, ...), `isInLobby`, `isMuted`, `mediaStreams[]`, `metadata`, `recordingInfo`, `removedState`, `restrictedExperience` and `rosterSequenceNumber`. [Verified: https://learn.microsoft.com/en-us/graph/api/resources/participant?view=graph-rest-1.0]

`identitySet` can carry `user`, `application`, `device`, `phone` and, in practice, `guest` or other variants. [Verified for user, application, device and phone in the invite response. The others are Unverified.]

### 2.5 Mapping audio to a participant

Each audio buffer in the media SDK carries **MSIs** (media source IDs, `uint`):

- `AudioMediaBuffer.ActiveSpeakers : uint[]` is the set of MSIs heard in this (mixed) frame. It excludes the bot.
- `UnmixedAudioBuffer.ActiveSpeakerId : uint` is the MSI for one per-speaker buffer.
- `DominantSpeakerChangedEventArgs.CurrentDominantSpeaker : uint`, where `0xFFFFFFFF` means none.

The mapping rule is the official sample's own code. [Verified: teams-recording-bot `SerializableAudioMediaBuffer.cs`; PolicyRecordingBot `CallHandler.GetParticipantFromMSI`]
```csharp
participants.SingleOrDefault(x => x.Resource.IsInLobby == false &&
    x.Resource.MediaStreams.Any(y => y.SourceId == msi.ToString()));
```
In words: compare `msi.ToString()` with `participant.mediaStreams[*].sourceId`, where `mediaType == "audio"`, skipping anyone who is still in the lobby. Then read `participant.info.identity.user.{id, displayName}`. `user.id` is the Entra object ID, which the recording sample calls `AdId`.

### 2.6 Operation notifications

Any async action (playPrompt, recordResponse, invite, ...) returns an operation object (`id`, `status: running|completed|failed`, `clientContext`, `resultInfo`) plus a `Location: .../operations/{opId}` header. Completion arrives as `changeType: "deleted"` on `/communications/calls/{id}/operations/{opId}`. See §4 for examples. [Verified]

---

## 3. Media: what the Real-time Media SDK delivers

### 3.1 Formats and frame timing

These figures come from https://learn.microsoft.com/en-us/microsoftteams/platform/bots/calls-and-meetings/real-time-media-concepts (updated 2026-05-29). [Verified]

- **Audio**: 16,000 samples per second, 16-bit, so a 20 ms frame is 320 samples or 640 bytes. That is 50 frames per second. The codecs on the wire (SILK, G.722) are handled by the platform.
- **Video**: 30 fps. Sizes 640x360, 1280x720 or 1920x1080. Colour formats NV12 or RGB24. The bot can also send or receive encoded H.264. It can receive up to **10** main video streams at once in a meeting, and it must explicitly *subscribe* to each participant's video. VBSS (video-based screen sharing) is a separate modality, `videoBasedScreenSharing`.
- **Active versus dominant speakers**: "Active speakers identify which participants are being heard in each received audio frame. Dominant speakers identify which participants are most active or dominant in the group conversation."

### 3.2 SDK surface (Microsoft.Skype.Bots.Media and Microsoft.Graph.Communications.Calls.Media)

API reference: https://microsoftgraph.github.io/microsoft-graph-comms-samples/docs/bot_media/. [Verified]

| Type / member | Facts |
|---|---|
| `AudioSocketSettings.ReceiveUnmixedMeetingAudio` | "When set to true, up to four audio buffers, each corresponding to the top four active speakers, will be received at a time." Unmixed audio requires `Pcm16K`. |
| `AudioSocket.AudioMediaReceived` | Raised once per 20 ms frame. The app must handle at least 50 per second, must `Dispose()` each buffer, and should keep handlers fast because events are serialized. |
| `AudioMediaBuffer` | `Data` (IntPtr), `Length` (bytes), `Timestamp` (100 ns units; for sending, use `MediaPlatform.GetCurrentTimestamp()`), `IsSilence`, `AudioFormat`, `ActiveSpeakers: uint[]`, `UnmixedAudioBuffers: UnmixedAudioBuffer[]` (receive only; null unless requested). |
| `UnmixedAudioBuffer` | `ActiveSpeakerId` (MSI), `Data`, `Length`, `OriginalSenderTimestamp` [Verified from the sample's use]. |
| `AudioSocket.DominantSpeakerChanged` | `CurrentDominantSpeaker`, where `0xFFFFFFFF` means none. |
| `AudioSocket.AudioSendStatusChanged` | Media sent before `MediaSendStatus.Active` is discarded. |
| `AudioSocket.Send(AudioMediaBuffer)` | "Sends one frame containing 20 ms of PCM audio." You subclass `AudioMediaBuffer`, for example `AudioSendBuffer(IntPtr, 640, AudioFormat.Pcm16K, timestamp)`. Don't free the data until the platform calls `Dispose()`. Pace at 50 frames per second. |
| `AudioSocket.ToneReceived`, `SendDtmfTone(s)` | DTMF. |
| `AudioSocket.MediaStreamFailure` | A network failure. Recovering means a new call or a rejoin. |
| `AudioVideoFramePlayer` | A helper that paces queued `AudioMediaBuffer`s and `VideoMediaBuffer`s (EchoBot uses `new AudioSettings(20)`). |

**How a bot speaks**: EchoBot chops TTS output into 640-byte PCM frames, timestamping each one by adding `20 * 10000` ticks (20 ms in 100 ns units), and enqueues them on `AudioVideoFramePlayer`, which calls `AudioSocket.Send`. [Verified: EchoBot `Utilities.CreateAudioMediaBuffers`, `BotMediaStream.cs`]

### 3.3 Hosting constraints (still true in November 2026)

These come from https://learn.microsoft.com/en-us/microsoftteams/platform/bots/calls-and-meetings/requirements-considerations-application-hosted-media-bots (updated 2026-07-22). [Verified]

- **Language and OS**: C#/.NET (".NET Core and SDK support for .NET 6.0"). Production must run on a **Windows Server** guest OS in **Azure**; on-premises Windows Server is allowed for dev and test only. "C++ and Node.js APIs don't support access to real-time media."
- **Allowed Azure hosts**: Cloud Service, Service Fabric with VMSS, IaaS VM, and AKS (Windows nodes). Azure Web App is **not** allowed.
- **SDK freshness**: the bot must use the newest `Microsoft.Graph.Communications.Calls.Media` NuGet or one **no more than three months old**. Older versions stop working. On 2026-11-20 the latest is `1.2.0.18742` (published 2026-10-30), and `Microsoft.Skype.Bots.Media` is at `1.34.0.2-preview` (targets net472, net8.0, net10.0). [Verified: NuGet API]
- **Networking**: each VM needs an **instance-level public IP** plus a per-instance public media port (a NAT rule or an instance input endpoint). The call is **pinned to the VM** that created it. Configuration goes in `MediaPlatformInstanceSettings { CertificateThumbprint, InstanceInternalPort, InstancePublicIPAddress, InstancePublicPort, ServiceFqdn }`, and the certificate must match the `ServiceFqdn` (media DNS name). [Verified: EchoBot BotService.cs] Typical ports are 443 for signalling and around 8445 for media, but the ports are your choice. [Unverified]
- **Compute**: at least 2 cores (Dv2 recommended, or 4 vCPU). Video is encoded in software on the CPU. The Bot Framework Emulator is not supported.
- **Platform status**: the docs still say "the Microsoft Real-time Media Platform for bots is in developer preview".
- **Linux**: no support. A Microsoft Q&A answer from March 2026 says no other language or OS support is on the near-term roadmap. [Secondary: https://learn.microsoft.com/en-au/answers/questions/5807336/bot-joining-teams-meetings-and-receiving-real-time] The repo's AKS sample is now in a folder called `AksSamples(Deprecated)`. [Verified: repo tree]
- **Microsoft's position for AI agents** (real-time-media-concepts page, updated 2026-05-29), quoted verbatim:
  > "**Building AI agents for meetings?** Real-time Media bots are not recommended for AI agent scenarios. Instead, use: Microsoft Copilot Studio agents ... Graph API meeting transcripts ... Meeting transcripts overview ..."

  The same page lists the intended use cases as Cloud Video Interop, Compliance Recording and Contact Center, "provided via managed partners and in some cases certified by Microsoft". [Verified]

---

## 4. Call actions

All of these act on `https://graph.microsoft.com/v1.0/communications/calls/{id}`. Unless noted, "Permissions are checked when the call is created; no additional permission check is made when calling this API."

| Action | HTTP | Body | Returns | Constraint |
|---|---|---|---|---|
| Hang up | `DELETE /communications/calls/{id}` | none | `204` | Removes only the bot's leg; the meeting continues |
| Keep alive | `POST .../keepAlive` | none | `200` | **Required every 15 to 45 minutes.** After 45 minutes without one, the call ends (408/8537). After the call ends it returns `404`. |
| Update recording status | `POST .../updateRecordingStatus` | `{"clientContext":"...","status":"recording"\|"notRecording"\|"failed"}` | `200` + `updateRecordingStatusOperation` | Permission `Calls.AccessMedia.All`. Must succeed **before** persisting media. |
| Mute self | `POST .../mute` | `{"clientContext":"..."}` | `200` + `muteParticipantOperation` (`status: completed`) | Server mute. Group calls only. A roster update follows. |
| Unmute self | `POST .../unmute` | `{"clientContext":"..."}` | `200` + `unmuteParticipantOperation` | Same rules as mute |
| Mute other | `POST .../participants/{pid}/mute` | `{"clientContext":"..."}` | `muteParticipantOperation` | [Unverified body] |
| Play prompt | `POST .../playPrompt` | `{"clientContext":"...","prompts":[{"@odata.type":"#microsoft.graph.mediaPrompt","mediaInfo":{"uri":"https://.../x.wav","resourceId":"..."}}]}` (at most 20 prompts) | `200` + `playPromptOperation` (`running`) | **Service-hosted only** |
| Record response | `POST .../recordResponse` | `prompts` (at most 1), `bargeInAllowed`, `initialSilenceTimeoutInSeconds`, `maxSilenceTimeoutInSeconds`, `maxRecordDurationInSeconds` (1 to 120), `playBeep`, `stopTones`, `clientContext` | `200` + `recordOperation` | **Service-hosted only.** At most 2 minutes. Download through `recordingLocation` with `recordingAccessToken`. |
| Subscribe to tone | `POST .../subscribeToTone` | `{"clientContext":"..."}` | `200` + `subscribeToToneOperation` | **Service-hosted only.** Tones then arrive as call `updated` notifications with `toneInfo {sequenceId, tone:"tone1"}`. |
| Invite participants | `POST .../participants/invite` | `{"participants":[{ "@odata.type":"#microsoft.graph.invitationParticipantInfo","identity":{"user":{"id":"...","displayName":"..."}}}],"clientContext":"..."}` | `200` + `inviteParticipantsOperation` (`Running`) | Permission `Calls.InitiateGroupCall.All`. At most 5 per request. Never more than one bot. |
| Remove participant | `DELETE .../participants/{pid}` | none | `204` [Unverified code] | |
| Change screen-sharing role | `POST .../changeScreenSharingRole` | `{"role":"viewer"\|"sharer"}` [Unverified body] | `204` | |

Sources: call-delete, call-keepalive, call-updaterecordingstatus, call-mute, call-playprompt, call-record, call-subscribetotone and participant-invite, all under https://learn.microsoft.com/en-us/graph/api/ (v1.0). [Verified except where marked]

**updateRecordingStatus rule**, quoted verbatim from the API page:
> "You may NOT use the Media Access API to record or otherwise persist media content from calls or meetings that your application accesses, or data derived from that media content ("record" or "recording"), without first calling the **updateRecordingStatus** API to indicate that recording has begun, and receiving a success reply from that API. If your application begins recording any meeting, it must end the recording prior to calling the **updateRecordingStatus** API to indicate that the recording has ended."

The same page also says the API "requires the use of the Teams policy-based recording solution". Whether a non-compliance-recording bot can call it successfully in its own tenant is **unclear** from the docs. Plan for it to succeed, and test it on a real tenant. [Unverified] Teams shows a recording banner to participants once the status is `recording`. [Unverified]

**Operation completion example** (playPrompt). [Verified]
```json
{
  "@odata.type": "#microsoft.graph.commsNotifications",
  "value": [{
    "@odata.type": "#microsoft.graph.commsNotification",
    "changeType": "deleted",
    "resourceUrl": "/communications/calls/57DAB8B1894C409AB240BD8BEAE78896/operations/0FE0623FD62842EDB4BD8AC290072CC5",
    "resourceData": {
      "@odata.type": "#microsoft.graph.playPromptOperation",
      "@odata.id": "/communications/calls/57DAB8B1894C409AB240BD8BEAE78896/operations/0FE0623FD62842EDB4BD8AC290072CC5",
      "@odata.etag": "W/\"54451\"",
      "resultInfo": { "@odata.type": "#microsoft.graph.resultInfo", "code": 200, "subcode": 0, "message": "Action completed successfully." },
      "clientContext": "d45324c1-fcb5-430a-902c-f20af696537c",
      "status": "completed"
    }
  }]
}
```
Note that the IDs in this `resourceUrl` are upper-case with hyphens stripped, unlike the IDs in the response body. A tolerant client should compare IDs case-insensitively with hyphens removed. [Verified: present in the doc examples]

### 4.1 Lobby and bot-detection behaviour in 2026

- **Policy**: Teams meeting policy setting `ExternalBotAccessMode`, labelled "Manage external bots and their access to meetings". The values are `AllowBots` and `RequireApprovalWhenDetected`, which is the **default**. Detected bots "are placed in the meeting lobby irrespective of the lobby configuration" and must be explicitly admitted. Detection uses "infrastructural and behavioral signals". [Verified: https://learn.microsoft.com/en-us/microsoftteams/manage-external-bots (ms.date 2026-05-22)]
- **Blocking**: an admin option to automatically **block** identified external bots appears in Teams release notes around September 2026. The Learn page above still lists only two modes. There is also a "Teams Bot Identification Program" for ISVs. [Secondary: https://learn.microsoft.com/en-us/officeupdates/teams-admin, https://learn.microsoft.com/en-us/microsoftteams/teams-bot-identification, both from search summaries and not fetched in full]
- **Same-tenant app-identity bots** (Max joining through Graph with `Calls.JoinGroupCall.All` in its own tenant) are "treated as trusted and bypass the lobby by design". There is no setting to force approval for them, and a feature request is open. [Secondary: Microsoft External Staff moderator, 2026-06-24, https://learn.microsoft.com/en-sg/answers/questions/5929235/can-same-tenant-teams-meeting-bots-also-be-subject]
- **Guest-identity joins** follow the meeting's anonymous and guest lobby rules, and normally land in the lobby. A bot left waiting is eventually dropped with code `200/5855`. [Verified: termination code table; sample comment]
- **Cross-tenant**: the permission descriptions say "meetings **in your organization**". Joining another tenant's meeting needs a multi-tenant app consented in *that* tenant. Otherwise you get `403` with code `7505` ("Request authorization tenant mismatch"). [Secondary: several Q&A threads, e.g. https://learn.microsoft.com/en-us/answers/questions/5772325/azure-bot-calling-403-forbidden-7505-tenant-mismat] An external bot is also subject to the other tenant's bot detection.

---

## 5. Meeting chat and in-meeting apps (Bot Framework / Teams SDK side)

The meeting chat is a Teams **group chat** whose conversation ID equals the call's `chatInfo.threadId`, for example `19:meeting_...@thread.v2`. The participant events below show `conversation.id: "19:meeting_threadId@thread.v2"`. [Verified]

### 5.1 Posting into the meeting chat

```
POST {serviceUrl}/v3/conversations/{19:meeting_...@thread.v2}/activities
Authorization: Bearer {token from login.microsoftonline.com, scope https://api.botframework.com/.default}
{ "type": "message", "text": "Meeting notes: ...", "attachments": [ /* Adaptive Card */ ] }
```

- The app containing the bot must be **installed in that chat or meeting**. Use the `serviceUrl` from an incoming activity. The fallback global URL for the public cloud is `https://smba.trafficmanager.net/teams/`. [Verified: https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/conversations/send-proactive-messages]
- Edit a posted message with `PUT {serviceUrl}/v3/conversations/{conversationId}/activities/{activityId}`. [Verified: same page]
- If the app is blocked or uninstalled, the call returns `403` with `subCode: MessageWritesBlocked`. [Verified]
- Reading every chat message, not just @mentions, needs the RSC permission `ChatMessage.Read.Chat`. [Verified: RSC page]

### 5.2 Meeting lifecycle events (bot receives `type: "event"` activities)

These need RSC `OnlineMeeting.ReadBasic.Chat`, plus `ChannelMeeting.ReadBasic.Group` for channel meetings. Participant join and leave events also need `OnlineMeetingParticipant.Read.Chat` and a Developer Portal subscription, and the bot must already be in the meeting. Supported for scheduled meetings. [Verified: https://learn.microsoft.com/en-us/microsoftteams/platform/apps-in-teams-meetings/meeting-apps-apis]

```json
{
  "name": "application/vnd.microsoft.meetingStart",
  "type": "event",
  "timestamp": "2023-02-23T19:34:07.478Z",
  "channelId": "msteams",
  "serviceUrl": "https://smba.trafficmanager.net/teams/",
  "from": { "id": "user_id" },
  "conversation": { "isGroup": true, "conversationType": "groupchat", "id": "conversation_id" },
  "recipient": { "id": "28:65f50003-e15d-434a-9e14-0fcfeb3d7817" },
  "value": {
    "Id": "meeting_id", "JoinUrl": "join_url", "Title": "Example meeting",
    "MeetingType": "Scheduled", "StartTime": "2023-02-23T19:34:07.478Z", "EndTime": null
  },
  "channelData": { "tenant": { "id": "tenant_id" } }
}
```

- `application/vnd.microsoft.meetingEnd` has the same shape, with `StartTime: null` and `EndTime` set. (The doc sample has a stray leading space in `" application/vnd..."`. Don't copy that.)
- `application/vnd.microsoft.meetingParticipantJoin` and `...meetingParticipantLeave` carry `value.members[]: { user: { tenantId, objectId, id: "29:...", name, aadObjectId }, meeting: { inMeeting, role: "Organizer|Presenter|Attendee" } }` and `channelData.meeting.id`. [Verified]
- MeetingType values: `OneToOneCall`, `GroupCall`, `Scheduled`, `Recurring`, `MeetNow`, `ChannelScheduled`, `ChannelRecurring`.

**Max's trigger**: the `meetingStart` event gives `JoinUrl`. Parse it (§1.6) and `POST /communications/calls`.

### 5.3 Meeting info and participant APIs (Bot Connector, using the bot token)

**`GET {serviceUrl}/v1/meetings/{meetingId}`** returns static metadata. It needs RSC `OnlineMeeting.ReadBasic.Chat` (or `ChannelMeeting.ReadBasic.Group`). [Verified]
```json
{
  "details": {
    "id": "<meeting ID (base64)>",
    "msGraphResourceId": "MSowYmQ0M2I4OS1lN2QxLTQxNzAtOGZhYi00OWJjYjkwOTk1YWYqMCoqMTk6bWVldGluZ19OVEkyT0RjM01qUXROV1UyW",
    "scheduledStartTime": "2022-04-24T22:00:00Z",
    "scheduledEndTime": "2022-04-24T23:00:00Z",
    "joinUrl": "https://teams.microsoft.com/l/xx",
    "title": "All Hands",
    "type": "Scheduled"
  },
  "conversation": { "isGroup": true, "conversationType": "groupChat", "id": "meeting chat ID" },
  "organizer": { "id": "<organizer user ID>", "aadObjectId": "<AAD object ID>", "objectId": "<organizer object ID>", "tenantId": "<Tenant ID>" }
}
```
`msGraphResourceId` is the Graph `onlineMeeting` ID.

**`GET {serviceUrl}/v1/meetings/{meetingId}/participants/{participantId}?tenantId={tenantId}`** returns the shape below. It is supported only for rosters under 350 participants. Errors: 403 (app not installed), 404 (meeting expired). [Verified]
```json
{
  "user": {
    "id": "29:1JKiJGPAX9TTxtGxhVo0wLx_...",
    "aadObjectId": "e236c4bf-88b1-4f3a-b1d7-8891dfc332b5",
    "name": "Bob Young", "givenName": "Bob", "surname": "Young",
    "email": "Bob.young@microsoft.com", "userPrincipalName": "Bob.young@microsoft.com",
    "tenantId": "2fe477ab-0efc-4dfd-bde2-484374e2c373", "userRole": "user"
  },
  "meeting": { "role": "Presenter", "inMeeting": true },
  "conversation": { "id": "<conversation id>", "conversationType": "groupChat", "isGroup": true }
}
```
The doc sample's key is `"role "`, with a trailing space. Treat `role` as canonical.

**Joining the two worlds**: `aadObjectId` (Bot Framework) equals `info.identity.user.id` (Graph calls roster). This is how Max can combine role and email with the MSI-to-speaker mapping. [Verified field semantics; the join itself is my inference]

### 5.4 In-meeting notifications (bubbles)

- **For everyone**: a normal chat message whose `channelData.notification` contains `alertInMeeting: true` and `externalResourceUrl: "https://teams.microsoft.com/l/bubble/APP_ID?url=<url>&height=<h>&width=<w>&title=<t>&completionBotId=BOT_APP_ID"`, posted to `/v3/conversations/{conversationId}/activities`. Returns 201. [Verified]
- **Targeted**: `POST {serviceUrl}/v1/meetings/{meetingId}/notification`. Needs RSC `OnlineMeetingNotification.Send.Chat`. [Verified]
```json
{
  "type": "targetedMeetingNotification",
  "value": {
    "recipients": [ "29:1I12M_iy2wTa97T6LbjTh4rJCWrtw2PZ3lxpD3yFv8j2YPnweY2lpCPPAn3RI0PP7rghfHauUz48I1t7ANhj4CA" ],
    "surfaces": [ {
      "surface": "meetingStage",
      "contentType": "task",
      "content": { "value": { "height": "300", "width": "400", "title": "Targeted meeting Notification", "url": "https://somevalidurl.com" } }
    } ]
  }
}
```
Responses: 202 (sent), 207 (partial), 400 (validation; also an empty recipients list), 401, 403, 404. Surfaces are `meetingStage` and `meetingTabIcon`. Recipients must be `29:` IDs, not AAD IDs or UPNs. [Verified]

### 5.5 Side panel and stage apps

These are tabs with manifest `context` values `meetingSidePanel`, `meetingStage`, `meetingChatTab` and `meetingDetailsTab`. TeamsJS provides `meeting.shareAppContentToStage(cb, url, {sharingProtocol: Collaborative|ScreenShare})`, which needs Delegated RSC `MeetingStage.Write.Chat`, plus `getAppContentStageSharingState`, `getAppContentStageSharingCapabilities` and `stopSharingAppContentToStage`. Only presenters and organizers can share. A Max live-notes side panel is feasible here, but it is a web app inside the Teams client, not part of the calling bot. [Verified: https://learn.microsoft.com/en-us/microsoftteams/platform/apps-in-teams-meetings/build-apps-for-teams-meeting-stage] (I did not separately verify the `meetingChatTab` and `meetingDetailsTab` names in this session; they come from the established manifest schema. [Unverified])

---

## 6. Real-time alternatives in 2026 (status)

| Option | What you get | Status (2026-11-20) | Source |
|---|---|---|---|
| **Work IQ real-time transcripts** | Live transcript text with **speaker names**, while the meeting is in progress | Admin toggle `Set-CsTeamsMeetingConfiguration -EnableWorkIQTranscriptAccess $true`, off by default, "takes effect on November 14, 2026". Also needs: AI allowed in the meeting, **transcription running** (Work IQ doesn't start it), the app acting **on behalf of a signed-in user** (delegated), and Work IQ enabled for the tenant. The **organizer's** tenant setting decides. | [Verified: https://learn.microsoft.com/en-us/microsoftteams/meeting-transcript-api-access (ms.date 2026-10-20)] |
| Roadmap RM570651, "Work IQ: Real Time Transcripts" | "Enable applications and agents to access Microsoft Teams meeting transcripts in real time" | In development. Preview September 2026, GA November 2026 (published 2026-10-19) | [Secondary: https://mc.merill.net/message/RM570651] |
| RM572674, "Work IQ Real Time Transcription for Meetings and Calls" | Possibly the same feature or an extension | Preview reportedly December 2026 | [Secondary / Unverified: windowsforum coverage only] |
| Work IQ API surface | MCP (`https://workiq.svc.cloud.microsoft/mcp`), REST and A2A | Work IQ APIs GA 16 June 2026 (third-party claim). **No public per-meeting real-time-transcript endpoint schema found.** | [Secondary: https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/work-iq/api-overview, from a search summary] |
| Graph meeting transcripts / recordings | `.../onlineMeetings/{id}/transcripts` (VTT) | **Post-meeting only.** Since 2026 there is also a tenant toggle: `-EnableGraphTranscriptAccess` (default off) and `-EnableAttributedTranscripts`. | [Verified: same admin page] |
| Live captions (CART) | **Send** human captions into a meeting: `POST https://api.captions.office.microsoft.com/cartcaption?meetingid=...&token=...&lang=en-us`, text body of 80 to 120 characters per line | GA. This is send-only; there is no public API to **read** Teams live captions. | [Verified for CART: meeting-apps-apis page. "No read API" is Unverified, absence of evidence only] |
| Interactive Agents for Teams Meetings and Calls (RM490564 / MC1087634) | Copilot Studio / BizChat agents in meetings | Announced June 2025, delayed in September 2025. The roadmap mirror now reportedly says "not able to continue rolling this out at this time", while also saying agents from BizChat or Copilot Studio are usable in meetings. Contradictory. | [Secondary / Unverified] |
| Real-time media bot (this doc) | Raw per-speaker audio and the ability to speak back | Works, but Windows/.NET/Azure only, labelled "developer preview", and "not recommended for AI agent scenarios" | [Verified] |

**Implication for Max.** Only the real-time media bot gives **audio in and audio out**. Work IQ gives near-real-time text with speaker names but no voice output, and it depends on delegated auth, tenant toggles and transcription being switched on. A hybrid Max could listen through Work IQ, speak through a minimal media bot, and post through the Bot Connector. The simulator should therefore keep the "transcript stream" interface separate from the "audio frame" interface.

---

## 7. Permissions

Sources: https://learn.microsoft.com/en-us/microsoftteams/platform/bots/calls-and-meetings/registering-calling-bot (2026-06-10), the RSC page (https://learn.microsoft.com/en-us/microsoftteams/platform/graph-api/rsc/resource-specific-consent, 2026-10-18) and the create-call page. [Verified]

| Permission | Type | Use | Consent |
|---|---|---|---|
| `Calls.JoinGroupCall.All` | Application | Join group calls and scheduled meetings "in your organization" as the app, "with the privileges of a directory user" | Admin |
| `Calls.JoinGroupCallAsGuest.All` | Application | Join anonymously as a guest. Lands in the lobby under normal rules. | Admin |
| `Calls.AccessMedia.All` | Application | **Required in addition** for app-hosted media | Admin |
| `Calls.Initiate.All` / `Calls.InitiateGroupCall.All` | Application | Outbound calls; invite and add participants (`invite` needs `InitiateGroupCall.All`) | Admin |
| `Calls.JoinGroupCalls.Chat` | RSC, app-only | Join calls tied to *this* chat or meeting. Listed as least-privileged for create-call. | Meeting organizer or presenter at app install |
| `Calls.AccessMedia.Chat` | RSC, app-only | Media access scoped to the chat or meeting | Same as above |
| `OnlineMeetings.Read.All` | Application | Read onlineMeeting (joinUrl to threadId). Needs an **application access policy** per user. | Admin |
| `OnlineMeeting.ReadBasic.Chat` | RSC | Meeting details API and meetingStart/End events | Install |
| `OnlineMeetingParticipant.Read.Chat` | RSC (delegated or app) | Participant API and join/leave events | Install |
| `OnlineMeetingNotification.Send.Chat` | RSC | Targeted in-meeting notifications | Install |
| `ChatMessage.Read.Chat` | RSC | Receive all meeting-chat messages | Install |
| `OnlineMeetingTranscript.Read.Chat` / `OnlineMeetingRecording.Read.Chat` | RSC | Post-meeting artifacts | Install (plus the tenant Graph transcript toggle) |
| `MeetingStage.Write.Chat` | RSC, delegated | Share to stage | Install |

- The Teams app manifest needs `bots[0].supportsCalling: true` (and `supportsVideo` for video). The Azure Bot needs the Teams channel with **Calling enabled** and a **Webhook (for calling)** HTTPS URL. [Verified]
- App-only RSC for meetings can be granted by "a meeting organizer or presenter". [Verified]
- After any change to application permissions, admin consent must be granted again. [Verified]
- **Cross-tenant**: Microsoft documents no cross-tenant path. In practice you need a multi-tenant app plus admin consent in the meeting's tenant, or a guest join. [Secondary]

---

## 8. End-to-end sequence: from "bot told to join" to "notes posted"

```
 Organizer/Teams        Teams Bot Connector          Max (bot svc + media VM)            Graph Comms API            Media Platform (MP)
      |                        |                              |                                |                            |
 (1)  | schedules meeting; Max app installed in meeting chat (RSC consent: OnlineMeeting.ReadBasic.Chat, Calls.JoinGroupCalls.Chat, ...)
      |                        |                              |                                |                            |
 (2)  |--meeting starts------->|                              |                                |                            |
      |                        |--POST /api/messages--------->|  event name=application/vnd.microsoft.meetingStart
      |                        |  value.JoinUrl, conv.id=19:meeting_..@thread.v2               |                            |
 (3)  |                        |                              |--parse JoinUrl -> chatInfo{threadId,messageId},
      |                        |                              |  meetingInfo{organizer.user{id=Oid,tenantId=Tid}}       |
      |                        |                              |  (optional) GET {serviceUrl}/v1/meetings/{id}           |
 (4)  |                        |                              |--CreateMediaSession(AudioSocketSettings{Sendrecv,Pcm16K,ReceiveUnmixed=true})
      |                        |                              |--POST /v1.0/communications/calls (appHostedMediaConfig.blob)-->|
      |                        |                              |<-201 Created {id, state:"establishing", myParticipantId}       |
 (5)  |                        |                              |<-POST callbackUri commsNotifications {state:"establishing"} (JWT iss=api.botframework.com)
      |                        |                              |   (bot replies 202)            |                            |
      |                        |                              |<========== ICE/DTLS/SRTP media connect to VM public IP:port ===============>|
 (6)  |                        |                              |<-POST callbackUri {state:"established"}  (may arrive before "establishing")
 (7)  |                        |                              |<-POST callbackUri .../participants  resourceData=[participant{info.identity.user{id,displayName}, mediaStreams[{audio,sourceId:"1"}], isInLobby,isMuted}...]
      |                        |                              |   build map: sourceId(MSI) -> {aadId, displayName}      |                            |
 (8)  |                        |                              |--POST /calls/{id}/updateRecordingStatus {status:"recording"}->|
      |                        |                              |<-200 updateRecordingStatusOperation{status:"completed"}       |
      |  (Teams shows recording/transcribing indicator)       |                                |                            |
 (9)  |                        |                              |<--------- AudioMediaReceived every 20 ms (640 B PCM16k mixed + ActiveSpeakers[] + UnmixedAudioBuffers[<=4]{ActiveSpeakerId}) --|
      |                        |                              |<--------- DominantSpeakerChanged(CurrentDominantSpeaker=MSI) -----------------------------------|
      |                        |                              |   ASR per MSI -> attributed transcript                  |                            |
(10)  |                        |                              |<-roster updates on join/leave/mute (full or delta)     |                            |
(11)  | user: "Max, summarize?"|                              |   LLM -> TTS -> 640 B frames @50fps                     |                            |
      |                        |                              |---------- AudioSocket.Send(AudioSendBuffer) x N (after AudioSendStatus=Active) -------------->|
      |  hears Max             |                              |                                |                            |
(12)  |                        |<-POST {serviceUrl}/v3/conversations/19:meeting_..@thread.v2/activities (interim notes card)
      |                        |                              |--POST /calls/{id}/keepAlive every <=45 min (15 recommended)-->|
(13)  |--meeting ends--------->|--event application/vnd.microsoft.meetingEnd->|                |                            |
      |                        |                              |<-POST callbackUri {changeType:"deleted", state:"terminated", resultInfo{200/5001}}
      |                        |                              |   (or Max: updateRecordingStatus{notRecording}; DELETE /calls/{id} -> 204 -> terminating/terminated 200/7000)
(14)  |                        |<-POST /v3/conversations/{threadId}/activities  (final notes Adaptive Card)
      |                        |                              |  (optional) POST /v1/meetings/{id}/notification targeted bubble to organizer
```

---

## 9. What our simulator must imitate

Principle: **the Graph Comms REST and webhook layer, and the Bot Connector meeting layer, are plain HTTPS+JSON and should be imitated byte for byte.** The real-time media layer is a proprietary binary SDK (SRTP/ICE, SILK/G.722, Windows native DLLs), so it cannot be imitated directly. Replace it with a stand-in at the SDK's *semantic* level: 20 ms PCM16k frames tagged with MSIs.

### 9.1 Must-have (P0)

1. **`POST /v1.0/communications/calls`** on a configurable base URL (default `https://graph.microsoft.com` becomes `http://localhost:XXXX`).
   - Accept all three `meetingInfo` shapes (`organizerMeetingInfo`, `joinMeetingIdMeetingInfo`, `tokenMeetingInfo`), `chatInfo`, `tenantId`, `callbackUri`, `requestedModalities` and both `mediaConfig` types.
   - Return `201` with a `Location` header and a call body (`state: "establishing"`, `id`, `myParticipantId`, `@odata.context`).
   - Validate: HTTPS `callbackUri` (allow an `http://localhost` override flag), a known threadId or joinMeetingId (else `404`), and tenant match (else `403` with code `7505`).
2. **Webhook delivery** of `commsNotifications` with the exact envelope (§2.2):
   - `establishing` then `established`, optionally out of order (a test flag);
   - full roster on join;
   - `terminating` then `terminated` with `changeType: "deleted"` and `resultInfo{code,subcode,message}`;
   - send a signed JWT `Authorization` header (`iss=https://api.botframework.com`, `aud=<appId>`, `tid`). Expose a local JWKS / OpenID config endpoint mirroring `https://api.aps.skype.com/v1/.well-known/OpenIdConfiguration`, so Max's validation code runs unchanged with only the URL swapped.
3. **Roster model**: participants with `id`, `info.identity.{user|application|guest}{id,displayName,tenantId}`, `mediaStreams[{mediaType,sourceId,direction,serverMuted,label}]`, `isMuted` and `isInLobby`. Push an update on every join, leave, mute or lobby change. Support **full** mode by default and **delta** mode (`deltaParticipants`, `sequenceNumber`, `rosterSequenceNumber`, `removedState`) behind `callOptions.isDeltaRosterEnabled`.
4. **Media stand-in (WebSocket)**: this is the faithful replacement for the media SDK.
   - Have the SDK emulation shim, not Max's core, open `wss://sim/media/{callId}` authenticated with the same app token. The shim should expose the same *shape* of API Max will later bind to the real SDK (`OnAudioMediaReceived`, `OnDominantSpeakerChanged`, `OnAudioSendStatusChanged`, `Send(frame)`), so swapping the shim for the real `Microsoft.Skype.Bots.Media` is mechanical.
   - **Downlink frame** (binary, little-endian) every 20 ms:
     ```
     header (JSON or fixed struct):
       { "t":"audio", "ts":<100ns ticks>, "isSilence":bool,
         "activeSpeakers":[<uint MSI>...],                // excludes bot
         "unmixed":[{"msi":<uint>,"len":640,"origTs":<ticks>}...]  // <=4, only if ReceiveUnmixedMeetingAudio
       }
     payload: 640 B mixed PCM s16le 16kHz mono, followed by 640 B per unmixed entry
     ```
   - Uplink: binary 640-byte PCM frames (optionally with a timestamp header). The simulator must enforce **50 fps pacing** (drop or queue the excess, as the real platform would) and must **discard frames sent before it emits `{"t":"sendStatus","status":"Active"}`**.
   - Control messages: `{"t":"dominantSpeaker","msi":<uint|4294967295>}`, `{"t":"mediaStreamFailure"}`, and later `{"t":"tone","id":N}`.
   - **sourceId consistency**: the MSI in audio frames must equal `mediaStreams[audio].sourceId` (a string) in the roster. This is the single most important invariant for Max's speaker attribution. Assign MSIs as small integers, as in the docs ("1", "10"), and never reuse one within a call.
   - Mix the bot's uplink audio into what simulated humans hear, and exclude it from `activeSpeakers`.
5. **`updateRecordingStatus`**: return `200`, a `Location` header and an `updateRecordingStatusOperation{status:"completed"}`. Track the status per call and expose it in the simulator UI as the "recording banner". **Policy hook**: optionally refuse to stream unmixed audio, or flag a violation, if Max persists transcripts while the status is `notRecording`, to catch compliance bugs early.
6. **`DELETE /communications/calls/{id}`** returning `204`, then terminating and terminated `200/7000`. Meeting end gives `200/5001`. Last human leaving gives `5002`.
7. **`keepAlive`**: `200`. Enforce a configurable timeout (default 45 minutes, compressible for tests) that terminates the call with `408/8537`. Return `404` on ended calls.
8. **Bot Connector meeting surface**:
   - inbound `event` activities `application/vnd.microsoft.meetingStart`, `...meetingEnd`, `...meetingParticipantJoin` and `...meetingParticipantLeave`, with exact payloads (§5.2);
   - `POST /v3/conversations/{19:meeting_...@thread.v2}/activities` (messages and Adaptive Cards) returning `{"id":"<activityId>"}`;
   - `PUT .../activities/{activityId}`;
   - `GET /v1/meetings/{meetingId}`;
   - `GET /v1/meetings/{meetingId}/participants/{participantId}?tenantId=`.
   The meeting chat ID must be the same string as `chatInfo.threadId`.
9. **Join URL generation**: the simulator's "meeting" must emit both a long-form `meetup-join` URL (with the `context` JSON carrying `Tid`/`Oid`) and a short `/meet/<digits>?p=<passcode>` URL, so Max's parser is exercised exactly as in §1.6.
10. **Identity mapping fixtures**: each simulated human has a Graph `user.id` (GUID, which also serves as `aadObjectId`), a Bot Framework `29:` ID and a display name, so Max can join the roster and the Bot Connector data.

### 9.2 Should-have (P1)

- Mute and unmute self (`POST .../mute|unmute` → operation completed, plus a roster update with `isMuted:true`). Server mute should silence the bot's uplink in the mix.
- Lobby simulation:
  - guest-identity joins go to `isInLobby:true`; an organizer action admits them; the `5855` timeout applies;
  - an "external bot detection" switch (`ExternalBotAccessMode`) puts non-same-tenant app joins in the lobby;
  - same-tenant app joins bypass it.
- Operations model: `/communications/calls/{id}/operations/{opId}`, `status: running → completed|failed`, completion notifications with `changeType:"deleted"`, `clientContext` echoed. Mirror the upper-case, hyphen-stripped IDs in `resourceUrl` as an optional "realism" flag.
- `participants/invite` → `inviteParticipantsOperation` (`Running`), then completed, then a roster add. Reject a second bot.
- Targeted meeting notification `POST /v1/meetings/{id}/notification` with response codes 202, 207, 400 and 404. In-meeting bubble through `channelData.notification.alertInMeeting`.
- `GET /communications/calls/{id}` and `GET /communications/calls/{id}/participants`.
- Error-injection knobs: `410/301005` media failure (with a `mediaStreamFailure` on the WebSocket), `500/1005`, and `403/7505` tenant mismatch.
- **Work IQ-style transcript stream** (a separate, optional interface): a WebSocket or SSE of `{speakerName, text, offset, isFinal}`, gated by simulated toggles (AI allowed, transcription running, Work IQ access, delegated user). This lets Max's "text-only listening" mode be developed now. Its exact wire format is **unknown**; label it a placeholder.

### 9.3 Nice-to-have (P2)

- Service-hosted IVR: `playPrompt` (fetch the WAV and inject it into the mix), `recordResponse` (`recordingLocation` + token download), `subscribeToTone` + `toneInfo` notifications, and `cancelMediaProcessing`.
- Video and VBSS: roster `video`/`videoBasedScreenSharing` streams, a subscription API, NV12 or RGB24 frames at a low fps over the same WebSocket. Content-sharing session notifications.
- Region redirect (`302`), the legacy-format first notification (expect `204`), and the incoming-call path (`answer`, `reject`).
- Side-panel and stage host page (an iframe plus a stub TeamsJS `meeting.shareAppContentToStage`).
- QoE stats endpoint, and `GetQualityOfExperienceData` at most every 30 s.

### 9.4 Impractical to imitate exactly, and the faithful stand-ins

| Real thing | Why not | Stand-in |
|---|---|---|
| `appHostedMediaConfig.blob` (opaque, SDK-generated) | Undocumented binary or serialized format | Accept any string. The shim generates `{"simMediaSession":{"audio":{"dir":"sendrecv","format":"Pcm16K","unmixed":true},"video":{"dir":"inactive"}}}` as base64, and the simulator decodes it to configure the WebSocket. Max never touches the blob directly; the SDK or shim makes it. |
| ICE/DTLS/SRTP transport, SILK/G.722/H.264, VM public IP and port, certificate | Proprietary, and pointless locally | The WebSocket in §9.1.4. Optionally inject jitter, loss or late frames to test robustness. |
| Windows-only `Microsoft.Skype.Bots.Media` DLLs | Platform lock-in | Define a small `IMediaSession` interface in Max (`audio frames in`, `send frame`, `dominant speaker`, `send status`) with two adapters: `SimWebSocketMediaAdapter` (any OS) and `TeamsRtmAdapter` (Windows/.NET worker). This is the main seam for "minimal change". |
| Bot detection heuristics | Signal-based and undocumented | A boolean per joiner ("detected as bot") driven by config |
| Exact timing, ordering and out-of-order quirks | Nondeterministic | Seeded randomisation flags: out-of-order establishing/established, duplicate roster updates, notification delay |
| Work IQ real-time transcript wire protocol | Not publicly documented as of 2026-11-20 | A placeholder schema, explicitly versioned `sim-v0` |
| Real recording banner and compliance enforcement | Client UI | A simulator UI indicator plus audit log |

### 9.5 Architecture note for "minimal change later"

Max's meeting code should depend on three ports:
1. **CallControl**, which speaks Graph REST JSON. The simulator gives exact parity, so only the base URL changes.
2. **CallbackReceiver**, which validates the JWT and parses `commsNotifications`. Exact parity; only the OpenID URL changes.
3. **MediaSession**, which is SDK-shaped. With the simulator it is a WebSocket adapter. In production it is a Windows/.NET media worker that hosts the real SDK and relays frames to Max over the same WebSocket protocol, so the simulator's media protocol becomes Max's *internal* production protocol too.

Option 3 is my recommendation: it keeps Max OS-agnostic and confines Windows to a thin media relay. [Unverified design proposal]

---

## 10. Open questions and items to verify on a real tenant

1. Does `updateRecordingStatus` succeed for a non-policy-recording app-hosted bot that joined through `Calls.JoinGroupCall.All`? The doc says it "requires the use of the Teams policy-based recording solution".
2. Exact UI and roster representation of a same-tenant app bot in 2026. Is it "trusted, bypasses lobby" as the forum moderator said, and is it ever subject to `BlockDetectedBots`?
3. The real-time transcript wire format, auth scopes and endpoint for Work IQ, and whether app-only access is ever supported. The admin docs currently say delegated only.
4. Whether `Calls.JoinGroupCalls.Chat` (RSC) alone, without tenant-wide `Calls.JoinGroupCall.All`, is enough for app-hosted joins when combined with `Calls.AccessMedia.Chat`. The create-call page lists it as least-privileged.
5. Whether `participant.info.identity` for anonymous or external users uses `guest`, `user` with a different `tenantId`, or other `identitySet` variants. The simulator should support all of them.
6. Current status of RM490564 (Interactive Agents) and RM572674. I could not reach primary pages.

---

## Sources (all accessed 2026-11-20)

**Graph Cloud Communications (v1.0)**
- Create call: https://learn.microsoft.com/en-us/graph/api/application-post-calls?view=graph-rest-1.0
- call resource: https://learn.microsoft.com/en-us/graph/api/resources/call?view=graph-rest-1.0
- participant resource: https://learn.microsoft.com/en-us/graph/api/resources/participant?view=graph-rest-1.0
- Delete call: https://learn.microsoft.com/en-us/graph/api/call-delete?view=graph-rest-1.0
- keepAlive: https://learn.microsoft.com/en-us/graph/api/call-keepalive?view=graph-rest-1.0
- updateRecordingStatus: https://learn.microsoft.com/en-us/graph/api/call-updaterecordingstatus?view=graph-rest-1.0
- mute: https://learn.microsoft.com/en-us/graph/api/call-mute?view=graph-rest-1.0
- playPrompt: https://learn.microsoft.com/en-us/graph/api/call-playprompt?view=graph-rest-1.0
- recordResponse: https://learn.microsoft.com/en-us/graph/api/call-record?view=graph-rest-1.0
- subscribeToTone: https://learn.microsoft.com/en-us/graph/api/call-subscribetotone?view=graph-rest-1.0
- invite: https://learn.microsoft.com/en-us/graph/api/participant-invite?view=graph-rest-1.0
- Get onlineMeeting: https://learn.microsoft.com/en-us/graph/api/onlinemeeting-get?view=graph-rest-1.0

**Teams platform: calls, meetings and media**
- Real-time media concepts: https://learn.microsoft.com/en-us/microsoftteams/platform/bots/calls-and-meetings/real-time-media-concepts
- App-hosted media requirements: https://learn.microsoft.com/en-us/microsoftteams/platform/bots/calls-and-meetings/requirements-considerations-application-hosted-media-bots
- Call notifications and auth: https://learn.microsoft.com/en-us/microsoftteams/platform/bots/calls-and-meetings/call-notifications
- Register a calling bot and permissions: https://learn.microsoft.com/en-us/microsoftteams/platform/bots/calls-and-meetings/registering-calling-bot
- Meeting apps APIs: https://learn.microsoft.com/en-us/microsoftteams/platform/apps-in-teams-meetings/meeting-apps-apis
- Meeting stage: https://learn.microsoft.com/en-us/microsoftteams/platform/apps-in-teams-meetings/build-apps-for-teams-meeting-stage
- RSC permissions: https://learn.microsoft.com/en-us/microsoftteams/platform/graph-api/rsc/resource-specific-consent
- Proactive messages: https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/conversations/send-proactive-messages

**Admin, policy and roadmap**
- Manage external bots: https://learn.microsoft.com/en-us/microsoftteams/manage-external-bots
- Transcript API access and Work IQ: https://learn.microsoft.com/en-us/microsoftteams/meeting-transcript-api-access
- Same-tenant bot lobby Q&A (Secondary): https://learn.microsoft.com/en-sg/answers/questions/5929235/can-same-tenant-teams-meeting-bots-also-be-subject
- Linux and alternative-language Q&A (Secondary): https://learn.microsoft.com/en-au/answers/questions/5807336/bot-joining-teams-meetings-and-receiving-real-time
- Tenant mismatch 7505 Q&A (Secondary): https://learn.microsoft.com/en-us/answers/questions/5772325/azure-bot-calling-403-forbidden-7505-tenant-mismat
- RM570651 mirror (Secondary): https://mc.merill.net/message/RM570651
- Work IQ at Ignite 2026: https://techcommunity.microsoft.com/blog/microsoft_365blog/whats-new-in-work-iq-at-ignite-2026-agents-that-get-work-done/4572219

**Official samples and SDK**
- Repo: https://github.com/microsoftgraph/microsoft-graph-comms-samples (latest commit 2026-10-28, `4dd98c4`)
- JoinInfo.cs: https://github.com/microsoftgraph/microsoft-graph-comms-samples/blob/master/Samples/Common/Sample.Common.V1/Meetings/JoinInfo.cs
- EchoBot BotService and BotMediaStream: https://github.com/microsoftgraph/microsoft-graph-comms-samples/tree/master/Samples/PublicSamples/EchoBot/src/EchoBot/Bot
- PolicyRecordingBot CallHandler: https://github.com/microsoftgraph/microsoft-graph-comms-samples/blob/master/Samples/V1.0Samples/LocalMediaSamples/PolicyRecordingBot/FrontEnd/Bot/CallHandler.cs
- Media SDK API reference: https://microsoftgraph.github.io/microsoft-graph-comms-samples/docs/bot_media/Microsoft.Skype.Bots.Media.AudioSocket.html (also AudioMediaBuffer and AudioSocketSettings)
- NuGet: https://www.nuget.org/packages/Microsoft.Graph.Communications.Calls.Media/
