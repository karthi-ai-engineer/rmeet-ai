# Max final

**Max** is an AI teammate for Microsoft Teams. It reads the team channel and files, answers
`@Max` questions, joins meetings, speaks when asked, and writes meeting notes it remembers.

This is the professional rebuild of the prototype in `../max-demo`.
Rules for Claude: `CLAUDE.md`. Approved stack: `docs/decisions.md`. Step plans: `docs/plans/`.

**Status:** Step 0 (foundation) and Step 1 (any AI provider + one limits file) built and tested.

## Setup

1. Python 3.12+ (developed on 3.13).
2. Copy `.env.example` to `.env` and paste your AI key (Gemini by default). Never commit `.env`.
3. `python run.py setup` creates `.venv` and installs the exact library versions.

## Commands

| Command | What |
|---|---|
| `python run.py test` | All offline tests (free, no key needed) |
| `python run.py check` | Live check with the real key: main model, backup model, fallback drill, today's cost |
| `python run.py settings` | Shows the AI provider, models and every limit in use (keys hidden) |
| `python run.py dashboard` | AI usage dashboard on http://localhost:8600 (daily budget, pause switch) |

## Folders

| Folder | What |
|---|---|
| `max/` | Max, the bot (`config`, `log`, `llm/` model client, `store/` database) |
| `ai_usage/` | AI usage meter, prices, dashboard for any provider (shared by every program) |
| `limits.toml` | Every limit in one place (starting values); your own edits go in `data/limits.toml` |
| `teams_sim/` | Simulated Teams + fake Microsoft cloud for development (later step) |
| `world/` | Simulated team data (later step) |
| `voice/` | Local voice server (later step) |
| `tests/unit/` | Offline tests · `tests/e2e/` full end-to-end runs (later) |
| `docs/` | Decisions, research, step plans |
| `data/` | Runtime data: database, logs, cost log (not in git) |
