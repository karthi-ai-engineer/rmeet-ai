# Research: app stack for Max final (25 Nov 2026)

Short version first, details after. Unverified items are marked **(?)**.

## Recommendation in one table

| Topic | Pick | Why, in one line |
|---|---|---|
| Python web | **FastAPI + uvicorn** for both programs | The Teams SDK for Python already runs on it, so it adds nothing new |
| Background jobs | **asyncio tasks** started at app startup | No Celery or Redis needed for a single-PC demo |
| Frontend | **React 19 + Vite 8 + TypeScript** | Most common stack, and the one AI assistants write best |
| Teams look | **Fluent UI React v9** with its built-in `teamsLightTheme` | Microsoft builds Teams itself with Fluent v9 |
| Cards | **`adaptivecards` JS renderer** (v3.0.6) | Max's real Adaptive Card JSON shows exactly as Teams would show it |
| Animation | **CSS** for small effects, **Motion** (`motion/react`) for lists, panels and springs | Apple-style motion with very little code |
| UI state | **Zustand** (one small store) | Fed by the live connection, simple to follow |
| Live updates | **One WebSocket per tab**, plus REST for actions | No connection limit across many tabs, resyncs on reconnect |
| Serving | `npm run build`, then Python serves `teams_sim/web/dist` | Node is needed only to build, not at demo time |
| Tests | **pytest** plus **Playwright for Python** | One language and one test runner |
| Launcher | **`run.py`** (Python standard library only) | One command: setup, build, start, open browser, stop |

## 1. Python web framework

| Option | WebSockets | Async | Fit |
|---|---|---|---|
| Standard library `http.server` | Hand-written (the prototype's `ws.py`) | No (threads) | Already caused bugs (HTTP/1.0 upgrade). Drop it. |
| **FastAPI** | Yes | Yes | **The Teams SDK depends on it.** `microsoft-teams-apps` 2.2.1 requires `fastapi` + `uvicorn` and ships a `FastAPIAdapter` that accepts our own FastAPI app (checked in the prototype's installed package). |
| Starlette | Yes | Yes | FastAPI is Starlette plus validation and docs. No gain in going lower. |
| aiohttp | Yes | Yes | A second web stack next to the one the SDK already brings in. |

- **Both programs use FastAPI.** The fake cloud needs typed request bodies (Graph and Bot Framework JSON), and FastAPI handles that well.
- FastAPI has **built-in Server-Sent Events** since 0.135 ([docs](https://fastapi.tiangolo.com/tutorial/server-sent-events/)), in case we need them.
- **Jobs:** use `asyncio.create_task` inside the FastAPI `lifespan`, plus one small scheduler loop for reminders and follow-ups. Store job state in SQLite so it survives a restart.
- Keep **two processes** (Max on :3978, teams_sim on :8100). Max must reach the fake cloud only over HTTP, as it would reach real Microsoft. A shared process would make it easy to cheat by accident.

## 2. Frontend

| Option | Teams look | Speed of building with AI | Maintainable at more than 3k lines | Verdict |
|---|---|---|---|---|
| Vanilla JS (the prototype) | Built by hand | Fast at first, slow later | No (`app.js` reached 1518 lines) | Drop |
| **React + Vite + Fluent UI v9** | **Real Fluent controls, Teams theme tokens** | Best | Yes | **Pick** |
| Svelte / SvelteKit | Built by hand (no official Fluent kit) | Good | Yes | Nice, but every Teams control must be rebuilt |
| Vue | Community Fluent kits only | Good | Yes | No advantage here |
| Fluent web components v3 | Fluent 2, any framework | Fewer examples to learn from | OK | Fewer components; the Fluent 2 site still labels them "Preview" ([link](https://fluent2.microsoft.design/components/web/react/)) |

- **Fluent UI React v9** (`@fluentui/react-components` 9.75.3 today) is current. The older Northstar kit reached end of life in July 2025 ([README](https://raw.githubusercontent.com/microsoft/fluentui/HEAD/README.md)). Its `teamsLightTheme` and `teamsDarkTheme` give us Teams colours, fonts, radii and shadows for free.
- **Our own CSS** is still needed for Teams-specific layout: the left app rail, the chat list, the meeting stage. Use Fluent tokens only and no hard-coded colours.
- **Motion** ([motion.dev](https://motion.dev), v14) handles message arrival, panel slides and the approval-card "pop". Use CSS for hover and focus states. Leave out View Transitions for now, because they add little in a single-page app and are harder to test.
- **Admin page:** a second route (`/admin`) in the same app, not a separate project.
- **Vite 8** is stable (March 2026, Rolldown bundler) ([blog](https://vite.dev/blog/announcing-vite8)). Builds take seconds.

## 3. Live updates: WebSocket or SSE

| | SSE | **WebSocket** |
|---|---|---|
| Direction | Server to browser only | Both ways |
| Reconnect | Built into the browser | About 20 lines of our own code |
| Many tabs on localhost | **Max 6 connections per site over HTTP/1.1**. A 7th tab (user, admin, colleague views) hangs silently. | No such limit |
| Needed anyway? | No | Yes, the calls/media stream is a WebSocket |

**Pick WebSocket**, one per browser tab. The server sends `{seq, type, data}`. The browser sends actions as plain REST POSTs, which are easy to test. On reconnect, or when it sees a gap in `seq`, the browser fetches a fresh snapshot. This rules out a UI that is quietly out of date.

## 4. Testing

| Layer | Tool | Runs |
|---|---|---|
| Unit (Max logic, fake-cloud contracts) | pytest + `httpx.ASGITransport` (in-process, no ports) | Every change, offline, free |
| Contract | pytest: Max talks to the real teams_sim over HTTP using recorded real Microsoft payloads | Every change |
| UI flows | **pytest-playwright** (Python): post a message, approve a card, start a meeting | Before each demo |
| Visual | Save screenshots for review; add `pytest-playwright-visual-snapshot` only if we need pixel diffs | On demand |

- Python Playwright has **no built-in `to_have_screenshot`**; only the Node test runner has it ([docs](https://playwright.dev/docs/test-snapshots)). Saved screenshots plus a human look are enough for a demo.
- **Scripted LLM mode** (`LLM_MODE=replay`): fixed answers for tests and as a fallback on stage. `LLM_MODE=live` uses Qwen and Gemini.
- **One command for the full demo end to end:** `python run.py e2e` starts everything headless, plays the demo script through Playwright, saves screenshots and logs to `data/runs/<time>/`, and prints pass or fail.

## 5. Folder layout

The draft is good. Three changes: the launcher lives at the root, the React source lives inside `teams_sim/web/`, and **a test fails if `max/` imports `teams_sim/` or `world/`** (or the other way round).

```
run.py              one command: setup, build, start, test, stop
max/                the bot (real Microsoft contracts only)
  app.py            starts the Teams SDK App, wires everything
  config.py         settings from .env
  teams/            message, card and invoke handlers (Bot Framework activities)
  graph/            Microsoft Graph client: files, channel posts, transcripts, subscriptions
  calls/            calling API and media socket
  agent/            the LLM loop, tools, prompts
  memory/           SQLite: notes, tasks, knowledge search
  llm/              Qwen and Gemini clients, quota guard
  cards/            Adaptive Card templates (JSON)
teams_sim/          demo only: fake Microsoft cloud + Teams-like UI
  server.py         starts FastAPI, mounts everything below
  cloud/            identity, connector, graph, subscriptions, calls (one file each)
  actors/           AI colleagues who chat and speak in the fake Teams
  ui_api.py         the UI's own REST + WebSocket
  web/              React source (src/) -> built to web/dist/
world/              demo data (team, posts, files, past meetings)
voice/              local Kokoro TTS server
tests/unit/  tests/e2e/
docs/               decisions, research, plans
data/               runtime: db, logs, runs (gitignored)
```

## 6. Launcher, config, logging

- **`run.py`** uses only the standard library, like the prototype. It creates `.venv`, installs the pinned `requirements.txt`, runs `npm ci && npm run build` only when `web/src` changed, then starts voice, teams_sim and Max. It waits for each `/health`, opens the browser, and stops everything on Ctrl+C. Sub-commands: `run.py`, `run.py test`, `run.py e2e`, `run.py stop`.
- **Config:** one root `.env`, read through **pydantic-settings**, which the Teams SDK already installs. Each program gets its own settings class with a prefix (`MAX_`, `SIM_`). Values are checked at startup, and a clear message names any missing key without ever printing it.
- **Logging:** standard-library `logging`, one file per program in `data/logs/`. Every line carries a conversation or meeting id. The console shows only important lines, and `/admin` shows a live tail.

## Top 5 risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | **The Teams SDK fights a fake cloud.** In the prototype, MSAL forced https and `CLIENT_SECRET` was hijacked. | Pin the SDK version. Use our own token provider. Add contract tests that use recorded real Microsoft payloads. |
| 2 | **Live models stall on stage** (Qwen cold start, Gemini 429 quota, first TTS call taking 20-60 s) | Warm up at start. Use timeouts and retries. Keep a one-switch fallback to `LLM_MODE=replay`. |
| 3 | **The UI "looks fake"** to stakeholders | Fluent v9 Teams theme and the real Adaptive Card renderer. Review screenshots side by side with real Teams. |
| 4 | **The frontend build breaks right before the demo**, or Node is missing on the demo PC | Keep the last good `dist/` and pin npm versions with `package-lock`. Optionally commit `dist/` on a demo tag. |
| 5 | **Windows process issues:** leftover servers holding ports, antivirus slowing first start | `run.py stop`, a port check with a clear message, and a PID file (all proven in the prototype). |

## Sources
- Teams SDK for Python GA: [devblogs, May 2026](https://devblogs.microsoft.com/microsoft365dev/python-support-for-the-microsoft-teams-sdk-is-now-generally-available/), [github.com/microsoft/teams.py](https://github.com/microsoft/teams.py)
- FastAPI SSE: [fastapi.tiangolo.com](https://fastapi.tiangolo.com/tutorial/server-sent-events/)
- Fluent UI: [fluent2.microsoft.design](https://fluent2.microsoft.design/components/web/react/), [Fluent web components](https://learn.microsoft.com/en-us/fluent-ui/web-components/)
- Vite 8: [vite.dev](https://vite.dev/blog/announcing-vite8)
- Playwright snapshots: [playwright.dev](https://playwright.dev/docs/test-snapshots), [pytest-playwright-visual-snapshot](https://pypi.org/project/pytest-playwright-visual-snapshot/0.2.0/)
- Local checks: `microsoft-teams-apps` 2.2.1 (requires fastapi, uvicorn, pydantic-settings), npm versions as of today.
