# Max final: handover

Last updated: 26 Nov 2026. Read with `CLAUDE.md` (rules for Claude).

## 1. Where we are in one minute

- **Max** = a semi-autonomous AI teammate for Microsoft Teams. This is the **real product** (not a demo).
- **Step 0 (foundation) is built, tested and committed**: settings, Gemini client with time limits + backup
  model, SQLite store (raw layer), AI usage meter + dashboard, `run.py`. **Step 1** (branch `step-1`): any AI
  provider via settings (`LLM_PROVIDER`: gemini or openai_compatible), all limits in `limits.toml`.
- **The design phase is DONE (26 Nov 2026).** All topics in `docs/plans/01-open-topics.md` are agreed, except
  **Max Meeting** (topic 7), which became its own module and is **paused until the chat Max (R1) is built**
  (`docs/plans/meeting/01-overview.md`).
- **The UI is designed** (`docs/plans/13-ui-design.md`, pictures `docs/plans/pictures/ui-*.png`): a simulated Teams
  built with Fluent UI v9 in `teams_sim/web/` (mock data only), Max's own pages, developer tools, all cards (drawn by
  Microsoft's Adaptive Cards renderer) and Max's chat (prompt starters, streaming, answers, feedback, cards).
  Run it: `cd teams_sim/web && npm install && npm run dev` (or `npm run build -- --base ./ && npx vite preview --port 5181`).
- **Next: Step 1** of the build plan (`docs/plans/12-build-plan.md`): any AI provider can be plugged in + all limits
  in one settings file. Write `docs/plans/step-1.md` (1-page plan) first and get Karthi's OK.
- **R1 size:** one laptop, about 4 simulated users in 1-2 teams, Karthi plays all of them (`03-requirements.md` §1).
- In examples and the simulated team use the names **Karthi, Prince, Rachitaa, Praga**.

## 2. Read in this order

| File | What |
|---|---|
| `CLAUDE.md` | Rules: how to work with Karthi, models allowed, git, process |
| `docs/plans/01-open-topics.md` | **The master list of what's left to decide** (start here for the next session) |
| `docs/decisions.md` | Approved tech stack |
| `docs/plans/02-use-cases.md` | 45 use cases, control levels L0-L4, triggers, decisions (agreed) |
| `docs/plans/03-requirements.md` | Requirements, 13 rules, R1 scope, quality targets (approved) |
| `docs/plans/04-agent-design.md` | Agent loop design (approved), loop graph (section 11), 3 modes + skill files (section 12) |
| `docs/plans/pictures/agent-loop.excalidraw` | The loop as a diagram (open at excalidraw.com, or with the VS Code Excalidraw extension); quick picture: `pictures/agent-loop-preview.png` |
| `docs/plans/06-memory.md` | Memory design, all 6 parts agreed (26 Nov). Pictures in `docs/plans/pictures/`: `memory-stories.excalidraw` (simple, 4 stories) and `memory.excalidraw` (full), each with a `-preview.png` |
| `docs/plans/07-rag.md` | RAG (live knowledge) design, all parts + Decisions 1-4 agreed (26 Nov). Pictures in `docs/plans/pictures/` |
| `docs/plans/05-tools.md` | Tool contracts, all agreed (26 Nov) |
| `docs/plans/08-personality.md` | Personality and answer style, agreed (26 Nov) |
| `docs/plans/09-cards.md` | Cards and message formats, agreed (26 Nov); pictures `docs/plans/pictures/cards-*.png` |
| `docs/plans/10-skill-files.md` | Skill files list (agreed) |
| `docs/plans/11-sim-world.md` | Simulated Thirdwave world + test set (agreed; scale test later) |
| `docs/plans/12-build-plan.md` | Build steps in order + "R1 done" checklist (agreed) |
| `docs/plans/13-ui-design.md` | UI design, all agreed; mock-ups in `teams_sim/web/` |
| `docs/plans/meeting/01-overview.md` | Max Meeting module (paused) |
| `docs/plans/step-0.md` | Step 0 plan and results |
| `docs/plans/README.md` | Map of the plans folder: numbered files in reading order + one `pictures/` folder |
| `docs/research/` | All research reports (Teams access, storage, AI stack, app stack, prototype review, knowledge/RAG, tools, competitors, memory) |

## 3. Key decisions so far (short)

| Area | Decision |
|---|---|
| Teams | **Simulated** for now (fake Microsoft cloud with real contracts). Real tenant later. IT admin only installs once. |
| Models | **Gemini only** for now: main `gemini-3.1-flash-lite`, backup `gemini-3.5-flash-lite` (2.5-flash-lite is blocked for new users). `gemini-embedding-2` allowed if tests show it helps. Qwen later. |
| Agent | **Pydantic AI**, only in `max/agent/runner.py` (swappable to LangGraph). 3 modes: workflow / simple loop / plan-then-act. Skill files per task type (written later). |
| Safety | Levels L0-L4, approvals by the right person (configurable), Stop button, budgets per task type + Continue card, loop guard, privacy filter, hidden-instruction guard |
| Memory | Compaction 40k/120k/200k + notepad; thread summaries; people facts with date + source (newer wins); run cards 60 days; lessons only from people (team lead accepts); work-only memory; forgetting rules |
| Knowledge (RAG) | Agreed (`07-rag.md`): structure-based pieces, keyword + meaning search, AI re-rank to best 8, answer checks, ~250-question test set |
| Plans | Living plan card + Plans tab; Max's DB is the source of truth; no Microsoft Planner (Karthi, 26 Nov); Jira/Notion later |
| Time | Team time zone Asia/Tokyo, working hours 9:00-18:00 |

## 4. Setup on another machine (e.g. home laptop)

1. Install **Python 3.12+** (developed on 3.13) and Git. Node is only needed later (frontend build).
2. Clone and switch to the work branch:
   ```
   git clone https://github.com/karthi-ai-engineer/rmeet-ai.git
   cd rmeet-ai
   git checkout max-final
   cd max-final
   ```
3. Copy `.env.example` to `.env` and paste your **AI key** (`LLM_API_KEY`; the old `GEMINI_API_KEY` also works). Never commit `.env`.
4. `python run.py setup` (creates `.venv`, installs exact library versions).
5. `python run.py test` → should show **103 passed** (offline, free).
6. `python run.py check` → live check with the key (main, backup, fallback drill).
7. `python run.py settings` → provider, models and every limit. Optional: `python run.py dashboard` → AI usage
   dashboard on http://localhost:8600. Own limits: copy lines from `limits.toml` into `data/limits.toml`.

Notes:
- `data/` (cost log, logs, database) is per machine and not in git. The daily cost cap ($1) counts per machine.
- Pydantic AI was installed on the office PC for inspection only. It gets pinned in `requirements.txt` when the
  agent is built.
- Claude's own notes ("memory") live per machine. Everything important is in `CLAUDE.md` and this file,
  so a new session on another machine has the same rules.

## 5. Next session: start here (paused 26 Nov 2026)

**Where we stopped:**
- **Step 1 is built, reviewed and fixed** on branch **`step-1`** (pushed): any AI provider via `LLM_*` settings,
  OpenAI-style backend (proven live through Gemini's OpenAI door), `ai_usage/` (was `gemini_cost/`), every limit in
  `limits.toml` + `data/limits.toml`, `python run.py settings`. 125 tests pass; live check passes.
  Results + review fixes: `docs/plans/step-1.md`. **Next: Karthi merges `step-1` into `max-final`.**
- **Avatar design is in progress:** `docs/plans/14-avatar.md` (options A-D, blob style 1-3, and the animated cloud
  engine found in `../max-demo/bot-avatar/`). Three open questions at the end of that file.
- On the home laptop: `git fetch` then `git checkout step-1` to continue (or merge it first).

**Then:**
1. Settle the avatar questions, then Step 2 of `docs/plans/12-build-plan.md` (simulated Teams for real, starting from
   the mock-ups in `teams_sim/web/`). Write `docs/plans/step-2.md` first and get Karthi's OK.
2. Keep the rules in `CLAUDE.md`: one part at a time, limits are settings, model stays swappable, Claude decides UI
   details and shows images.
