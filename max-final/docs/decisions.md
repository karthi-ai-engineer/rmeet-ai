# Max final: decisions

**Status: APPROVED by Karthi, 25 Nov 2026.** Open questions in section 7 use the defaults shown there until Karthi says otherwise.
Based on `docs/research/` (teams-access, storage, ai-stack, app-stack, prototype-review), 25 Nov 2026.

## 1. Big decisions (already agreed)

| Topic | Decision |
|---|---|
| Teams | **Simulated now** (fake Microsoft cloud with real contracts). Real Teams later: own Microsoft 365 organisation first, then one test team in the company. |
| Scope | Chat first (channel, @Max, files, notes from transcripts). Live meetings later, through the same brain. |
| Database | **Our own**, switchable to the central project's database later |
| Git | Same repo (`rmeet-ai`) for now |

## 2. Tech stack (proposed)

| Part | Choice | Why |
|---|---|---|
| Language | Python 3.13 | Same as the prototype; the Teams SDK supports it |
| Teams bot | Microsoft **Teams SDK for Python** (pinned version) | Official; makes the later move to real Teams a config change |
| Web server | **FastAPI** + uvicorn (both programs) | The Teams SDK already uses it, so nothing extra |
| Database | **SQLite**, plain SQL in one `store` module, no ORM | Zero setup, search built in, easy to export |
| Live updates to UI | One WebSocket per browser tab | Works with many open tabs |
| Frontend | **React + Vite + TypeScript + Fluent UI v9** (Teams theme), Motion for animation | Fluent is what real Teams is built with, so it **looks like Teams** |
| Max's cards | Microsoft's own Adaptive Cards renderer | Cards look exactly like they do in Teams |
| Installs | pip with exact versions | Simple |
| Launcher | `python run.py` (start), `run.py test`, `run.py e2e`, `run.py stop` | One command for everything |
| Config | One root `.env`, checked at startup, values never printed | |
| Tests | pytest (unit, offline, free) + Playwright (full demo in a browser) | One "run all" command |

## 3. AI stack (proposed)

| Job | Choice | Fallback |
|---|---|---|
| Agent framework | **Pydantic AI** (pinned): built-in approval pause/resume, fake models for tests | Plain hand-written loop |
| Thinking / answers / tools | **Gemini `gemini-3.1-flash-lite`** | `gemini-3.5-flash-lite` (separate limits; 2.5-flash-lite is blocked for new users) |
| Meeting notes | Gemini flash-lite | `gemini-3.5-flash-lite` |

**Change 25 Nov 2026: Gemini only for now.** There is no Qwen access at the moment (its limits were reduced).
The model client stays provider-neutral, so Qwen can come back later as a settings change.
Risk: Gemini free-tier limits (HTTP 429). A paid key with a daily cap is strongly advised.
| Hearing (speech to text) | **Local faster-whisper `small.en`** (1.9 s per 5 s of speech on this PC) | Gemini |
| Voice (text to speech) | **Local Kokoro**, sentence by sentence (about 1 s per sentence) | Gemini TTS |
| Live meeting pipeline (later) | Small hand-written pipeline + Silero (voice detection) | |
| Search | Keyword search (SQLite FTS5) first | Local `bge-small` "meaning search" only if tests show it's needed |
| Simulated colleagues | **Scripted replay by default** (same every demo); live Gemini as an option | |

Cost per demo run: about $0.15 on Gemini (estimated in the research while Qwen was still the main model; to be re-measured).

**Swap-ready agent framework.** Karthi may want LangGraph later. So Pydantic AI is used in **one file only**
(`max/agent/runner.py`). Everything else is plain Python that any framework can call:

| Piece | Where | Framework-free? |
|---|---|---|
| Tools (search, files, email, meeting...) | `max/agent/tools.py`: plain functions with type hints | ✅ |
| Prompts | `max/agent/prompts/*.md`: plain text | ✅ |
| Model clients, time limits, fallback | `max/llm/` | ✅ |
| Approvals (pending, approve/deny, expiry) | our own code + `store/` | ✅ |
| Conversation history | our own tables in `store/` | ✅ |
| The agent loop | `max/agent/runner.py` | ❌ The only Pydantic AI file |

Switching to LangGraph means rewriting `runner.py` only. The same tests check both.

**Final choice: Pydantic AI.** LangGraph only if long multi-step or multi-agent flows become a real need.

**Other tools later (Slack, Notion, ...):** these will be added through **MCP**, the standard way to plug tools
into AI agents. Pydantic AI supports it, and so does LangGraph. Each connector comes with its own
permissions and approval rules. Not now.

## 4. Storage design (proposed)

| Group | What | Rule |
|---|---|---|
| **Raw** | Exact Teams/Graph data (posts, replies, files, meetings, transcripts) | Only added to; deleted content is purged after N days, leaving only a marker |
| **Working** | Clean tables + search index | Can be wiped and rebuilt from Raw any time |
| **App** | Max's tasks, approvals, audit log | Cannot be rebuilt, so it is backed up |

- **Sync:** every Teams notification triggers a catch-up (delta), plus a safety check every ~15 minutes. The fake Teams misbehaves on purpose (duplicates, drops, throttling) so we catch problems early.
- **Files:** original files in a folder, extracted text in the database (MarkItDown).
- **Max reads data through search tools**, never by dumping everything into the prompt.
- **Hand-off to the central database:** an export of Raw.

## 5. Reliability rules (from the prototype review)

1. Every model call has a time limit and a fallback message. Max never goes silent.
2. A question is never dropped. If Max is busy, it queues the question.
3. If notes fail, Max says so in the chat.
4. Tests never touch the demo's data (separate test data folder).
5. Timeouts line up end to end (the UI waits longer than Max).
6. No `sys.path` hacks and no global state. Runtime files only go in `data/`.
7. A test fails if `max/` imports anything from `teams_sim/` or `world/`.

## 6. Folder layout (proposed)

```
run.py           one command: setup, start, test, stop
max/             the bot (real Microsoft contracts only)
  app.py         starts Max
  config.py      settings from .env
  teams/         chat messages, cards, approvals
  graph/         reads channel, files, meetings, transcripts from Graph
  calls/         meetings: join, audio (later)
  agent/         the brain: agent loop, tools, prompts
  llm/           model clients (Gemini now), time limits, fallback
  store/         database (raw, working, app) + search
teams_sim/       demo only: fake Teams
  server.py      starts the fake Teams
  cloud/         fake Microsoft: sign-in, bot messages, Graph, calls
  actors/        simulated colleagues (scripted or live)
  web/           the Teams-like interface (React)
world/           demo data: team, posts, files, past meetings
voice/           local voice server (Kokoro)
tests/unit/      fast, offline, free
tests/e2e/       full demo runs in a browser
docs/            decisions, research, plans
data/            runtime: database, logs, files (not in git)
```

## 7. Open questions

| Question | Default until Karthi decides |
|---|---|
| Scripted colleagues by default | Yes (live Gemini is an option) |
| Local hearing model (faster-whisper) | Yes, re-test on a real voice recording first |
| 4-5 s spoken reply in live meetings | Accepted for now, improve later |
| Paid Gemini key with daily cap | Open: Karthi to check |
| Language / private channels | English only, no private channels in the simulation |
| Deleted content purge | After 7 days |
| Max's avatar | Later: redesigned as its own step. For now Max is a normal Teams app with a bot icon. |
| Demo world | Designed fresh (not copied from max-demo) |
