# Max: AI teammate for Microsoft Teams

Max is its **own program**. It talks to "Microsoft" only through the real Teams
contracts, so the same code runs against the rmeet-ai simulator today and real
Microsoft Teams later (only `max/.env` changes).

```
            rmeet-ai = fake Microsoft (simulations/teams)        real Microsoft (later)
                 │  Bot Connector  │  Graph  │  Entra login           same contracts
                 ▼                 ▼         ▼
            ┌──────────────────────────────────────────┐
            │ Max (this folder) – Teams SDK for Python │
            │  app.py        handlers: install, @Max   │
            │  knowledge.py  reads channel via Graph    │
            │  brain.py      Qwen: answers, notes       │
            └──────────────────────────────────────────┘
```

## What Max does

| Event | What Max does |
|---|---|
| Added to a team (`installationUpdate`) | Reads every post, reply and file through Graph; finds the team's Teams meetings (members' calendars) and their official transcripts; subscribes to change notifications; posts a welcome (with an admin heads-up if a permission is missing) |
| `@Max …` in a channel thread | Shows "typing", reads the thread through Graph, answers with Qwen **in the same thread** (replyChains API) |
| New / edited / deleted message | Graph change notification → Max GETs the message and updates its knowledge (RSC bot delivery is a second path) |
| File uploaded or changed | Drive notification → `root/delta` → downloads only what changed |
| Meeting transcript created | `getAllTranscripts` notification → reads the WebVTT transcript (speaker-attributed) |
| Admin grants consent / policy / transcript switch later | Background re-check notices, reads meetings + transcripts, announces it in the channel |
| `reauthorizationRequired` / `subscriptionRemoved` | Reauthorizes / resubscribes and resyncs (one recovery per team) |
| Removed from the team | Deletes that team's knowledge and subscriptions |
| Channel meeting starts (`meetingStart` event) | Gets the join URL (`GET {serviceUrl}/v1/meetings/{id}`), joins with Graph `POST /communications/calls`, sets `updateRecordingStatus`, connects media |
| In the call | Voice: hears 20 ms PCM frames per speaker (MSI) → Gemini speech-to-text; answers out loud (Gemini TTS, voice Charon), stops if interrupted. Text: reads the live transcript, answers in the meeting chat. If voice fails, answers in chat |
| Call ends (`terminated` / `meetingEnd`) | Writes notes with Qwen and posts them in the meeting thread (only if recording status was set) |

### Permissions Max needs

| Kind | Permissions | Who grants |
|---|---|---|
| Team-level (RSC, in the manifest) | `ChannelMessage.Read.Group`, `File.Read.Group`, `TeamMember.Read.Group`, `ChannelSettings.Read.Group`, `TeamSettings.Read.Group`, `ChannelMeeting.ReadBasic.Group` | Team owner when adding Max |
| Tenant-wide Graph application permissions | `Calendars.Read`, `OnlineMeetings.Read.All`, `OnlineMeetingTranscript.Read.All`, `Calls.JoinGroupCall.All`, `Calls.AccessMedia.All` | Admin consent (Entra) |
| Teams admin | Application access policy for Max; "Graph API access to transcripts" switch | Teams admin (PowerShell / admin center) |

## Files

| File | Purpose |
|---|---|
| `app.py` | Entry point: Microsoft Teams SDK `App`, activity handlers, Graph notifications, call callbacks (`/api/calling`) |
| `calling.py` | Meeting call: join, callbacks, recording status, media WebSocket, per-speaker segmenting, speaking with barge-in |
| `voice.py` | Gemini text-to-speech (Max's voice) and speech-to-text (Max's hearing) |
| `audio.py` | 16 kHz PCM helpers (resample, 20 ms frames, media frame header) |
| `config.py` | Settings from `.env` (app identity + which Microsoft endpoints to use) |
| `auth.py` | OAuth 2.0 client-credentials token provider (plugged into the SDK's `token=` hook) |
| `graph_client.py` | Microsoft Graph calls (paging, 429 retry, 302 file downloads) |
| `knowledge.py` | Builds and updates the channel knowledge from Graph |
| `meetings_sync.py` | Calendars → online meetings → WebVTT transcripts, with clear reasons when access is blocked |
| `subscriptions.py` | Graph change-notification subscriptions: create, renew, reauthorize, recover |
| `docs.py` | Text from xlsx / docx / pdf / md files |
| `brain.py` | Qwen prompts: thread answers, meeting answers, meeting notes |
| `llm.py` | Qwen client (thinking off, retries) |
| `appPackage/` | Teams app package: `manifest.json` (bot + RSC permissions) and icons |

## Run

```
.venv\Scripts\python simulations\teams\register_app.py   # once: creates the app identity + max/.env
.venv\Scripts\python max\app.py                          # Max on http://localhost:3978
```

## Moving to real Teams

1. Register a real Entra app + Azure Bot (single-tenant), messaging endpoint `https://<host>/api/messages`.
2. In `.env`: real `CLIENT_ID` / `CLIENT_SECRET` / `TENANT_ID`, and **delete** `TEAMS_LOGIN_ENDPOINT`,
   `TEAMS_OPENID_METADATA_URL`, `GRAPH_BASE_URL` (public-cloud defaults apply). Set `MAX_PUBLIC_URL` to Max's
   public **https** address (Graph must reach `/graph/notifications` and `/graph/lifecycle`).
3. Upload `appPackage/` (zip) to Teams. No code changes.

See `docs/research/teams/` for the contracts and the open questions to verify on a real tenant.
