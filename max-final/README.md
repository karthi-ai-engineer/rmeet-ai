# Max final

**Max** is an AI teammate for Microsoft Teams. It reads the team channel and files, answers
`@Max` questions, joins meetings, speaks when asked, and writes meeting notes it remembers.

This is the professional rebuild of the prototype in `../max-demo`.
Rules for Claude: `CLAUDE.md`. Approved stack: `docs/decisions.md`. Step plans: `docs/plans/`.

**Status:** Step 0 (foundation) built: settings, model client with fallback, database, Gemini cost meter, tests.

## Setup

1. Python 3.12+ (developed on 3.13).
2. Copy `.env.example` to `.env` and paste your Gemini key. Never commit `.env`.
3. `python run.py setup` creates `.venv` and installs the exact library versions.

## Commands

| Command | What |
|---|---|
| `python run.py test` | All offline tests (free, no key needed) |
| `python run.py check` | Live check with the real key: main model, backup model, fallback drill, today's cost |
| `python run.py dashboard` | Gemini cost dashboard on http://localhost:8600 (daily cap, pause switch) |

## Folders

| Folder | What |
|---|---|
| `max/` | Max, the bot (`config`, `log`, `llm/` model client, `store/` database) |
| `gemini_cost/` | Gemini usage meter, prices, cost dashboard (shared by every program) |
| `teams_sim/` | Simulated Teams + fake Microsoft cloud for development (later step) |
| `world/` | Simulated team data (later step) |
| `voice/` | Local voice server (later step) |
| `tests/unit/` | Offline tests · `tests/e2e/` full end-to-end runs (later) |
| `docs/` | Decisions, research, step plans |
| `data/` | Runtime data: database, logs, cost log (not in git) |
