# Max final: handover

Last updated: 27 Nov 2026. Read with `CLAUDE.md` (rules for Claude).

## 1. Where we are in one minute

- **Max** = a semi-autonomous AI teammate for Microsoft Teams. This is the **real product** (not a demo).
- **Built so far (each step: plan → tests → build → independent review → end-to-end test → docs):**
  Step 0 foundation · Step 1 any AI provider + one limits file (merged into `max-final`) · **Step 2 simulated Teams
  in the browser** (branch `step-2`): people, departments, channels (one private), chats, live updates; Max connects
  through the **real Bot Framework contract** (Teams SDK for Python) and says hello. `docs/plans/step-2.md`.
- **The design phase is DONE (26 Nov 2026).** All topics in `docs/plans/01-open-topics.md` are agreed, except
  **Max Meeting** (topic 7), which became its own module and is **paused until the chat Max (R1) is built**
  (`docs/plans/meeting/01-overview.md`). UI: `docs/plans/13-ui-design.md`; Max's character and chat animations:
  `docs/plans/14-avatar.md` (agreed 27 Nov).
- **Run it:** `python run.py start` → open http://localhost:5100 (switch person in the top bar, write `@Max`).
  Design showcases still work with URL params, e.g. `?view=chat&chat=max&demo=moments`.
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
| `docs/plans/step-1.md`, `step-2.md`, ... | One file per build step: plan, results, review fixes, known gaps |
| `docs/plans/14-avatar.md` | Max's character + the chat animation moments (agreed 27 Nov) |
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

1. Install **Python 3.12+** (developed on 3.13), Git and **Node.js 20+** (builds the Teams screens).
2. Clone and switch to the work branch:
   ```
   git clone https://github.com/karthi-ai-engineer/rmeet-ai.git
   cd rmeet-ai
   git checkout max-final        # or the newest step branch (step-2, step-3, ...)
   cd max-final
   ```
3. Copy `.env.example` to `.env` and paste your **AI key** (`LLM_API_KEY`; the old `GEMINI_API_KEY` also works). Never commit `.env`.
4. `python run.py setup` (creates `.venv`, installs exact library versions).
5. `python run.py test` → all pass (offline, free). `python run.py e2e` → end-to-end + browser tests (needs Node.js
   20+ and Microsoft Edge; builds the screens itself).
6. `python run.py check` → live check with the key (main, backup, fallback drill).
7. `python run.py start` → simulated Teams + Max on http://localhost:5100 (`python run.py stop` to stop).
8. `python run.py settings` → provider, models and every limit. Optional: `python run.py dashboard` → AI usage
   dashboard on http://localhost:8600. Own limits: copy lines from `limits.toml` into `data/limits.toml`.

Notes:
- `data/` (cost log, logs, database) is per machine and not in git. The daily cost cap ($1) counts per machine.
- Pydantic AI was installed on the office PC for inspection only. It gets pinned in `requirements.txt` when the
  agent is built.
- Claude's own notes ("memory") live per machine. Everything important is in `CLAUDE.md` and this file,
  so a new session on another machine has the same rules.

## 5. Next session: start here (27 Nov 2026)

**Where we stopped:**
- **Step 2 is DONE** on branch **`step-2`** (pushed): see `docs/plans/step-2.md` (results, bugs found, known gaps).
  Karthi merges `step-2` into `max-final` when happy.
- **Git identity:** commit only as `karthi-ai-engineer` (repo-local `git config user.email` =
  `296384397+karthi-ai-engineer@users.noreply.github.com`). The PC's global email belongs to a company GitHub
  account; check `git config user.email` before committing on a new clone.
- **Step 3 (Thirdwave's world)** continues on branch **`step-3`**: `docs/plans/step-3.md`. Per the agreed process
  (`11-sim-world.md` Part 3) **Karthi reviews the fact sheet + samples before the full world is generated**.

**Keep the rules in `CLAUDE.md`:** one part at a time, limits are settings, model stays swappable, Claude decides UI
details and shows images, test end to end before saying something works.
