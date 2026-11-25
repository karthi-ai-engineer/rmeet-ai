# Step 0 plan: the foundation

**Status: BUILT and tested, 25 Nov 2026** (waiting for Karthi's commit). Branch: `max-final`.

## Goal
Build the base pieces every later step uses. No Teams screen yet.
At the end: `python run.py test` passes, and `python run.py check` shows that Gemini answers.

## What we build

| # | Piece | File(s) | What it does |
|---|---|---|---|
| 1 | Launcher | `run.py` | `setup` (create `.venv`, install exact versions), `test` (all offline tests), `check` (live Gemini check) |
| 2 | Settings | `max/config.py` | Reads `.env`, checks the key exists, **never prints key values** |
| 3 | Logs | `max/log.py` | One log file per program in `data/logs/` |
| 4 | Model client | `max/llm/` | One simple `ask()` for the whole project. Gemini now, provider-neutral for later. |
| 5 | Database | `max/store/` | SQLite file in `data/`, version-numbered schema, first tables only |
| 6 | Tests | `tests/unit/` | Offline, free, fast |
| 7 | Gemini cost | `gemini_cost/` | Usage meter (every Gemini call goes through it), daily cap, pause switch, live dashboard on http://localhost:8600 (carried over from the demo) |

## The model client: how it stays reliable

```
ask() ─► main model (flash-lite) ── ok ──► answer
            │ timeout / server error ─► retry once
            │ limit hit (429) ─────────► wait the time Google says, or go straight to the backup
            ▼
         backup model ── ok ──► answer
            ▼ fails too
         clear error ─► caller shows a friendly fallback message (Max never goes silent)
```

- Every call has a **time limit**.
- Every call is **logged** by `gemini_cost/`: model, time taken, tokens, estimated cost (one line per call in `data/gemini_cost/`). The dashboard shows it live.
- A **daily spend cap** in our own code. When it's reached, calls stop with a clear message.

## Database: first tables only

| Table | Group | Why now |
|---|---|---|
| `schema_version` | system | Safe upgrades later |
| `raw_items` | Raw | The never-changed store (unique on kind + id + content hash) |

Working tables (messages, files, meetings, search) come in Step 2, when data starts arriving.

## Tests (written first)

| Test | Checks |
|---|---|
| Settings | A missing key gives a clear error, and the key value never appears in errors or logs |
| Model client (fake Gemini) | Timeout → retry → backup → clear error; 429 waits or switches; spend cap blocks calls |
| Database | Creates from empty; re-running is safe; storing the same raw item twice does nothing |
| Boundaries | `max/` never imports `teams_sim/` or `world/` |

Live check (`run.py check`, uses the real key, costs a fraction of a cent): main and backup model answer,
response time, how much text each model can take at once, and the list of available Gemini models.

## Not in Step 0
Fake Teams, the interface, Max's bot, the agent (Pydantic AI comes in Step 3), voice.

## Libraries (exact versions pinned when installed)
`google-genai` (official Gemini SDK) · `pydantic-settings` · `httpx` · `pytest`

## "Done" means
`run.py test` all pass · `run.py check` works with the real key · a reviewer sub-agent has checked the code · docs updated · Karthi commits.

## Decisions (25 Nov 2026)
| Question | Answer |
|---|---|
| Backup model | `gemini-3.5-flash-lite` ($0.30 in / $2.50 out per 1M tokens; main is $0.25 / $1.50). The cheaper `gemini-2.5-flash-lite` was the first choice, but the live check showed Google blocks it for new users (404). Only used when the main model fails, so the extra cost is tiny. |
| Daily cap | $1/day to start, changeable on the dashboard |
| Cost dashboard | Carry over the demo's dashboard into `gemini_cost/` |
| Gemini key | Paid |
| Note | Main model `gemini-3.1-flash-lite` has an earliest shutdown of 7 May 2027; Google's replacement is `gemini-3.5-flash-lite` |

## Result (25 Nov 2026)
- `run.py test`: 59 offline tests pass (run 3 times in a row, no flaky tests).
- `run.py check` with the real key: main and backup answer (about 0.6-0.8 s); fallback drill passes; the key never appears in logs.
- A wrong key gives "Gemini refused the API key. Check GEMINI_API_KEY." (Gemini sends 400 API_KEY_INVALID).

Fixed after the code review:
| Problem | Fix |
|---|---|
| Cost log lost about 20% of lines when 2 programs wrote at once (Windows) | One log file per process; the dashboard merges them; test with 4 processes |
| A delete with the same content, or an edit back to old text, was silently dropped | Only skip if equal to the item's *latest* version; the delete flag is part of the hash |
| A wrong key showed a confusing "bad request" error | 400 + API_KEY_INVALID is treated as a key problem |
| Models without a price escaped the $ cap | Counted at the highest known price, marked "(est.)" on the dashboard |
| Two programs creating the database at once crashed | Migrations run under a write lock; WAL switch retries |
| Dashboard and Max could use different cost folders | One project-wide cost folder |
| Odd SDK errors or a cost-log write error could escape `ask()` | Turned into normal failures; a log error never loses an answer |
| Smaller | Rate-limit wait respects the deadline; `LOG_LEVEL` any case; timeouts must be positive |

Known limit: a call stopped by our own time limit is logged at $0, though Google may still bill it.
