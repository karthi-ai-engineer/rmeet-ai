# Handover: rmeet-ai / Max

Last updated: 20 Nov 2026. Read with `CLAUDE.md` (rules) and `README.md` (overview).

## 1. The idea in one minute

**Max** is an AI teammate for Microsoft Teams:
- lives in a team channel: reads posts, replies and files; answers `@Max` in threads
- joins the team's meetings like a person: hears who says what, answers out loud when someone says "Max…"
- writes notes (summary, decisions, action items, risks) and remembers them for the next meeting

We can't use a real company Teams tenant yet, so we built **rmeet-ai**: a Teams-like web app plus a
**fake Microsoft cloud** that speaks the same contracts as real Microsoft (sign-in tokens, Bot Connector,
Graph, change notifications, calling API, media). Max talks only to those contracts, so moving to real
Teams = change config (endpoints + real app registration), not code. The one real-Teams gap is media
(see 6).

The simulated team: **Planning Department, Kestrel Home Goods**.
- Karthi M (Planning Manager, the user, host) · Prince Raj (finance) · Daniel Ito (operations) ·
  Jacob Thomas (marketing), all AI colleagues driven by Qwen with their own Gemini voices
- the channel thread has 15 posts, 10+ documents (xlsx/pdf/docx/md), and 3 past meetings
  (minutes in the channel, transcripts in Graph)
- the live meeting is the **H1 FY2027 Budget Review** (16 scripted beats + answer key); autopilot scores
  Max's notes out of 40

## 2. Status by phase

| Phase | What | Status |
|---|---|---|
| Avatar | Cloud avatar, eyes-only, emotions (`bot-avatar/`) | Done |
| Voice test | Gemini push-to-talk test (`voice-chat/`) | Done |
| World + simulator | Planning Department world, rmeet-ai UI, AI colleagues, scoring | Done (40/40) |
| 1. Messaging | Max as separate program (Teams SDK), install/RSC consent, `@Max` thread answers | Done, `tests/e2e_phase1_messaging.py` 17/17 |
| 2. Graph knowledge | Change notifications, files + delta, calendars/onlineMeetings/VTT transcripts, admin gates, lifecycle recovery | Done, `tests/e2e_phase2_graph.py` 27/27 |
| 3. Meetings via calling | meetingStart → Graph `POST /communications/calls` → callbacks → recording status → media; voices | **Text mode done**: `tests/e2e_phase3_meeting_call.py` 16/16 (notes 40/40), `tests/e2e_phase3_live_and_edges.py` 13/13 (you host, interjections, end early, Max remembers the meeting), `tests/test_quota_guard.py` 7/7 (offline). **Voice mode works but is limited by the free Gemini TTS quota** (see 5) |
| 4. Agentic | Adaptive cards, Max drafts Budget v3, reminders/follow-ups | Not started |

## 3. How a meeting works now (Phase 3)

1. Host clicks **Meet** → a "Meeting started" post appears in the channel (its thread = meeting chat).
2. Teams sends Max `application/vnd.microsoft.meetingStart` (needs RSC `ChannelMeeting.ReadBasic.Group`).
   Channel meetings have `JoinUrl = null`, so Max calls `GET {serviceUrl}/v1/meetings/{id}`.
3. Max joins: Graph `POST /communications/calls` (needs admin consent for `Calls.JoinGroupCall.All` +
   `Calls.AccessMedia.All`). Without consent Max posts in the meeting chat why it can't join.
4. Max connects the **media stand-in** WebSocket `ws://localhost:8100/media/{callId}` (Graph token).
   The call becomes `established`; Max calls `updateRecordingStatus: recording` → red banner in the UI.
   Notes are only kept if recording status was set (Microsoft media policy).
5. Two modes (chosen in the Join dialog):
   - **Voice**: colleagues speak with Gemini TTS; Max gets 20 ms PCM16k frames tagged per speaker (MSI)
     → segments → Gemini speech-to-text → Qwen → Gemini TTS (voice **Charon**) → frames back up the call.
     Browser plays clips + Max's streamed audio. If TTS fails, colleague lines go as text and Max answers
     in chat (fallback).
   - **Text**: Max gets a live transcript (Work IQ-style) and answers in the meeting chat. Qwen only, fast.
6. End: call `terminated` (200/5001) + `meetingEnd` → Max posts notes in the meeting thread → the official
   VTT transcript appears in Graph (Max subscribes to `getAllTranscripts` and learns it).

Voices (`simulations/planning-department/team.yaml`): Karthi = Alnilam, Prince = Iapetus,
Daniel = Achird, Jacob = Puck; Max = Charon (`MAX_VOICE` in `max/.env`). UI has a **🎧 Voices** panel.

## 4. Setup on a new machine

1. Install Python 3.12+ (developed on 3.13) and Git; clone this repo.
2. `python -m venv .venv` then `.venv\Scripts\pip install -r requirements.txt`
   (macOS/Linux: `.venv/bin/pip ...`).
3. `copy voice-chat\.env.example voice-chat\.env` and fill in: `GEMINI_API_KEY`, `TW_API_KEY`
   (company Qwen gateway). Never commit `.env` files.
4. `.venv\Scripts\python simulations\teams\register_app.py`: creates the fake app registration
   (`simulations/teams/state/`), the Teams app package (`max/appPackage/`) and `max/.env`
   (copies the model keys). Re-run it whenever `voice-chat/.env` changes.
5. Start: `.venv\Scripts\python simulations\rmeet\server.py` (http://localhost:8100) and in a second
   terminal `.venv\Scripts\python max\app.py` (port 3978). On Windows set `PYTHONIOENCODING=utf-8` for Max.
6. In the UI: **Apps → Add Max**, then **Admin** (left rail): grant admin consent, access policy, transcript
   switch. Then **Meet → Join** (Live = you host, Autopilot = all simulated + scored; Voice/Text).

Tests (both servers running): `.venv\Scripts\python tests\e2e_phase3_meeting_call.py`, `tests\e2e_phase3_live_and_edges.py`
(add `--voice` or `--only-voice` for the voice run), `tests\e2e_phase2_graph.py`,
`tests\e2e_phase1_messaging.py`, `tests\check_voice_pipeline.py` (Gemini only), `tests\test_quota_guard.py` (offline).
Note: the tests reset the channel (Max is reinstalled).

## 5. Known issues / gotchas

- **Gemini free tier TTS quota (HTTP 429 "exceeded your current quota")**: only ~3 of 8 lines got a voice
  in the voice run. Karthi will get a better API key; then re-run `--only-voice`. A quota guard now pauses
  TTS/STT until Google's `retryDelay` passes (no stalling); colleagues fall back to the browser voice +
  text to Max, Max falls back to the meeting chat. Note: in voice mode Max's *hearing* is also Gemini (STT).
- First Gemini TTS call can stall ~20-60 s; calls are capped and retried.
- Qwen: always send `enable_thinking: false` (1.5-2 s vs 5-6 s); the first call after idle can hang
  → warmup + per-try timeout + retry are in place.
- Teams SDK reads `CLIENT_SECRET` from the env and forces MSAL (https only) → `max/config.py` pops it and
  Max passes its own `token=` provider (`max/auth.py`).
- App-only tokens keep the roles they were issued with → Max refreshes its token once on any Graph 403.
- WebSocket upgrade must answer `HTTP/1.1 101` (the stdlib server defaults to 1.0): fixed in `ws.py`.
- Media connects while the call is `establishing`; the call is `established` once media is up.
- Store times are wall-clock-as-UTC; the UI formats with `timeZone: 'UTC'`.

## 6. Moving to real Teams later

- Real app registration in Entra + Azure Bot; delete the `TEAMS_*` / `GRAPH_BASE_URL` overrides in
  `max/.env`; public https URLs for `/api/messages`, `/graph/notifications`, `/api/calling`.
- Media: real Teams app-hosted media needs Microsoft's Real-time Media SDK (**Windows + .NET**). Plan: a thin
  .NET "media worker" that relays the same frame protocol Max already uses (`MEDIA_RELAY_URL`).
- Real-time transcript (text mode) maps to Microsoft's meeting transcript APIs / Work IQ when available.
- Research notes: `docs/research/teams/01-03`.

## 7. Next steps

1. Voice run with the new Gemini key (`tests/e2e_phase3_meeting_call.py --only-voice`), tune segmenting
   (`END_SILENCE` in `max/calling.py`) and the TTS throttle if needed.
2. Phase 4 (agentic): adaptive cards in threads, Max drafts "Budget v3", reminders on action items,
   follow-up posts before the next meeting.
3. Later: real Teams (section 6) or a Daily.co demo (the original free-demo plan).

## 8. File map (most important)

| File | What |
|---|---|
| `max/app.py` | Max entry: Teams SDK handlers, Graph notifications, `/api/calling` callbacks, background jobs |
| `max/calling.py` | Meeting call: join, callbacks, recording, media, STT segments, speaking with barge-in, notes |
| `max/brain.py` | Qwen prompts: thread answers, meeting answers, notes |
| `max/knowledge.py`, `meetings_sync.py`, `subscriptions.py` | Channel/files/meetings knowledge from Graph |
| `max/voice.py`, `max/audio.py` | Gemini TTS/STT for Max, PCM helpers |
| `simulations/rmeet/server.py` | rmeet-ai server: UI APIs + fake Microsoft routes + media WebSocket |
| `simulations/rmeet/director.py` | Runs the meeting: colleagues' lines (Qwen), voices, call/media, scoring |
| `simulations/teams/*.py` | Fake Microsoft: identity, store, connector, graph, meetings, subscriptions, calls, ws, audio |
| `simulations/planning-department/` | World: team.yaml, WORLD.md, thread + files, past meetings, budget-review beats + answer key |
