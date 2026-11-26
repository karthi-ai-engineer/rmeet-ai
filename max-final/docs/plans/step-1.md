# Step 1 plan: any AI provider + all limits in one settings file

**Status: PROPOSED (26 Nov 2026), waiting for Karthi's OK.** Branch: `step-1` (from `max-final`).
Build plan: `12-build-plan.md`. Rules: model stays swappable; every price, budget and limit is a setting.

## Goal
Max can talk to **any AI provider** by changing settings only, and **every limit lives in one settings file**
that can be edited at any time (no restart). Nothing new is visible to team members yet; this is foundation work.

## What we build
| # | Piece | Where | What it does |
|---|---|---|---|
| 1 | Provider-neutral settings | `max/config.py`, `.env.example` | `LLM_PROVIDER` (`gemini` or `openai_compatible`), `LLM_API_KEY`, `LLM_MODEL`, `LLM_FALLBACK_MODEL`, `LLM_BASE_URL`. **The old `GEMINI_*` names keep working**, so your `.env` doesn't have to change |
| 2 | Second backend | `max/llm/openai_compat.py` | Talks to any OpenAI-style server (company Qwen on vLLM, other open models, Gemini's own OpenAI-style door). Same error handling as the Gemini backend: time limit, retry, backup model |
| 3 | Neutral usage meter | `gemini_cost/` → **`ai_usage/`** | Same meter and dashboard, renamed. Counts tokens and time for every provider; price per model (local / company models = $0, still counted) |
| 4 | One limits file | `limits.toml` (defaults, in git) + `data/limits.toml` (your edits, not in git) | All agreed limits with their starting values (below). Checked on load (a wrong value gets a clear message, never a crash). **Re-read when changed: no restart** |
| 5 | Show the settings | `python run.py settings` | Prints the provider, models and every limit (keys hidden as `***`) |

**Limits in the file (starting values):** daily AI budget $1 · test budget $5/week · private messages per person 3/day ·
chases per task 1/day · jobs per person 40 · approval expiry 24 h · follow-up window 10 min · searches per question 3 ·
history window 30 days · model time limit 20 s · whole-answer deadline 60 s. The cost dashboard reads and writes the same file.

## How we check it (tests first)
- **Offline tests (free):** old and new setting names; provider switch; the OpenAI-style backend against a fake server
  (good answer, time-out, rate limit, bad key, server error → the same error kinds as Gemini); limits file loads,
  rejects bad values with a clear message, and is re-read after an edit; the meter works for any provider.
- **Live check (`run.py check`, ~$0.002):** Gemini through its own backend **and** through the OpenAI-style backend
  (Gemini offers that door), so the second backend is proven for real. Also confirms the main model is still offered
  (one research report said `gemini-3.1-flash-lite` may be on its way out; if so I bring a proposal, no silent switch).
- **Review:** a separate reviewer checks the code. **Done** = all tests pass (59 old + new), live check passes,
  dashboard works with the limits file, docs updated, Karthi commits.

## Karthi's answers (26 Nov 2026)
1. Rename `gemini_cost/` → `ai_usage/`: **yes**.
2. `limits.toml` (defaults, in git) + `data/limits.toml` (own edits, per machine): **yes**.

## Results (26 Nov 2026)
- **Built:** `max/config.py` (provider-neutral `LLM_*` settings, old `GEMINI_*` names still work, `python run.py settings`),
  `max/llm/openai_compat.py` + `max/llm/backends.py` (OpenAI-style backend, picked by `LLM_PROVIDER`),
  `ai_usage/` (renamed from `gemini_cost/`; old `data/gemini_cost` moved once to `data/ai_usage`, history kept),
  `limits.toml` + `limits.py` (every agreed limit; own edits in `data/limits.toml`; re-read on change; bad values →
  clear message + last good values), dashboard reads/writes the same limits file and shows a limits-file problem.
- **Offline tests:** 103 passed (59 from Step 0 + 44 new: limits file, settings, OpenAI-style backend, provider switch,
  live limits, usage meter, folder rules).
- **Live check** (`python run.py check`, $0.00002): main + backup answered, fallback drill passed, **the same model
  answered through the OpenAI-style backend (Gemini's door)**, main model still offered by Google.
- **Review:** independent reviewer found 4 important + 5 smaller problems; **all fixed, each with a test**:
  1. an old `GEMINI_API_KEY` could be sent to another provider's server → old `GEMINI_*` names now apply to Gemini only;
  2. a limits file not saved as UTF-8 crashed every AI call → clear message, last good values;
  3. a short file lock (antivirus) was remembered → the next call reads again;
  4. saving while the file was open failed on Windows → retries, then a clear "file in use" message (dashboard 503);
  5. saving with a broken own file wiped other edits → refused until the file is fixed;
  6. a second limits file when `AI_USAGE_DIR` was set → one limits file for everyone (`LIMITS_FILE` to move it);
  7. odd server answers / bad address escaped as crashes → always a clean error; list-style content joined;
  8. the live check printed PASS for a broken limits file → fixed order;
  9. thinking tokens were counted twice in cost → split correctly.
  Nits fixed too: key hidden before shortening error text; old usage folder moved file by file if locked (with a
  warning); empty `.env` lines no longer hide old values; provider name in any case; http(s) address checked;
  infinite / useless limits rejected; `run.py settings` hides user:password in addresses and extra-field values.
- **After fixes:** 125 tests pass; live check passes again (both backends).
