# Simulations: a fake Microsoft Teams for testing Max

rmeet-ai is two things in one server (http://localhost:8100):

1. **A Teams-style client**: the Planning Department channel (posts, replies, files,
   past meetings, @mentions, adding apps) and a meeting room with AI colleagues.
2. **A fake Microsoft** (`teams/`) that speaks the real contracts to Max:

| Fake service | Real equivalent | Path |
|---|---|---|
| Entra ID token endpoint | `login.microsoftonline.com` | `/login/{tenant}/oauth2/v2.0/token` |
| Bot Framework OpenID + keys | `login.botframework.com` | `/botframework/v1/.well-known/...` |
| Bot Connector REST API | `smba.trafficmanager.net/teams` | `/teams/v3/conversations/...` |
| Microsoft Graph: channel, files, delta | `graph.microsoft.com/v1.0` | `/graph/v1.0/teams/...`, `/drives/...` |
| Microsoft Graph: calendar, meetings, transcripts | `graph.microsoft.com/v1.0` | `/graph/v1.0/users/{id}/calendarView`, `.../onlineMeetings/...` |
| Microsoft Graph: change notifications | `graph.microsoft.com/v1.0` | `/graph/v1.0/subscriptions` (+ webhooks to Max) |
| Tenant admin (Entra consent, Teams policies) | Entra / Teams admin center | **Admin** button in the left rail |

Max (`../max/`) is a **separate program** and only reaches the world through these.

## Run (3 steps)

```
.venv\Scripts\python simulations\teams\register_app.py   # once: Max's app identity, app package, max/.env
.venv\Scripts\python simulations\rmeet\server.py         # terminal 1: rmeet-ai
.venv\Scripts\python max\app.py                          # terminal 2: Max
```

Open http://localhost:8100 → **Add Max** (consent screen) → Max reads the channel and posts a welcome →
write `@Max …` in any thread → **Join** the meeting (Live or Autopilot).

Meetings and transcripts start **blocked**, like a fresh real tenant. Open **Admin** (left rail) and
grant admin consent, assign the access policy, and turn on transcript access; within ~90 s Max notices
and announces it. Upload files in **Files**; Max learns them through change notifications.

## Folders

| Path | What |
|---|---|
| `teams/` | Fake Microsoft: `identity.py`, `store.py` (tenant/team/channel/files/install state), `connector.py` (incl. meetingStart/End events), `graph.py`, `meetings.py`, `subscriptions.py`, `register_app.py`. Runtime state (keys, registration, new posts) in `teams/state/` |
| `rmeet/` | Server, meeting director (AI colleagues via Qwen), scoring, UI (`static/`) |
| `teams/calls.py`, `teams/ws.py`, `teams/audio.py` | Fake Graph calling (`/communications/calls`, signed callbacks, roster) + the media stand-in WebSocket `/media/{callId}` (20 ms PCM frames, or a live transcript in text mode) |
| `rmeet/voices.py` | Gemini TTS for the colleagues' voices (cached in `.tts_cache/`) |
| `planning-department/` | The world: `team.yaml`, `WORLD.md`, thread seed + 10 documents, 3 past meetings, budget-review beats + answer key |

## Keeping Max honest

- Max never reads `planning-department/` directly. It reads the channel through fake Graph after it is
  installed with resource-specific consent, exactly like a real Teams bot.
- The colleagues see `WORLD.md` without the answer key; scoring uses `expected.yaml`.
- Security is real: signed JWTs both ways, bad secrets/tokens get 401, Graph before install gets 403.
