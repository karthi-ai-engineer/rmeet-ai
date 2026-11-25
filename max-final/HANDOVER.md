# Max final: handover

Last updated: 25 Nov 2026. Read with `CLAUDE.md` (rules for Claude).

## 1. Where we are in one minute

- **Max** = a semi-autonomous AI teammate for Microsoft Teams. This is the **real product** (not a demo).
- **Step 0 (foundation) is built, tested and committed**: settings, Gemini client with time limits + backup
  model, SQLite store (raw layer), Gemini cost meter + dashboard, `run.py`, 59 offline tests.
- **Now we are DESIGNING, not coding.** Rule: every topic in `docs/plans/open-topics.md` is discussed and agreed
  with Karthi, **one part at a time**, before any more code.
- **We stopped at:** memory Part 6, "Max Personal" (one Max; the team is chosen by where you talk; in the 1:1 chat a
  focus word and/or a team menu). Two questions are waiting for Karthi (see `docs/plans/memory.md`, Part 6).

## 2. Read in this order

| File | What |
|---|---|
| `CLAUDE.md` | Rules: how to work with Karthi, models allowed, git, process |
| `docs/plans/open-topics.md` | **The master list of what's left to decide** (start here for the next session) |
| `docs/decisions.md` | Approved tech stack |
| `docs/plans/use-cases.md` | 45 use cases, control levels L0-L4, triggers, decisions (agreed) |
| `docs/plans/requirements.md` | Requirements, 13 rules, R1 scope, quality targets (approved) |
| `docs/plans/agent-design.md` | Agent loop design (approved), loop graph (section 11), 3 modes + skill files (section 12) |
| `docs/plans/agent-loop.excalidraw` | The loop as a diagram (open at excalidraw.com, or with the VS Code Excalidraw extension); quick picture: `agent-loop-preview.png` |
| `docs/plans/memory.md` | Memory design: Parts 1-5 agreed, Part 6 proposed |
| `docs/plans/step-0.md` | Step 0 plan and results |
| `docs/research/` | All research reports (Teams access, storage, AI stack, app stack, prototype review, knowledge/RAG, tools, competitors, memory) |

## 3. Key decisions so far (short)

| Area | Decision |
|---|---|
| Teams | **Simulated** for now (fake Microsoft cloud with real contracts). Real tenant later. IT admin only installs once. |
| Models | **Gemini only** for now: main `gemini-3.1-flash-lite`, backup `gemini-3.5-flash-lite` (2.5-flash-lite is blocked for new users). `gemini-embedding-2` allowed if tests show it helps. Qwen later. |
| Agent | **Pydantic AI**, only in `max/agent/runner.py` (swappable to LangGraph). 3 modes: workflow / simple loop / plan-then-act. Skill files per task type (written later). |
| Safety | Levels L0-L4, approvals by the right person (configurable), Stop button, budgets per task type + Continue card, loop guard, privacy filter, hidden-instruction guard |
| Memory | Compaction 40k/120k/200k + notepad; thread summaries; people facts with date + source (newer wins); run cards 60 days; lessons only from people (team lead accepts); work-only memory; forgetting rules |
| Knowledge (RAG) | Search first, open only what's needed. **Own big design session still to come** (topic 3, incl. OCR extractor and live updates) |
| Plans | Living plan card + Plans tab; Max's DB is the source of truth; Planner/Jira/Notion later |
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
3. Copy `.env.example` to `.env` and paste your **Gemini key** (never commit `.env`).
4. `python run.py setup` (creates `.venv`, installs exact library versions).
5. `python run.py test` → should show **59 passed** (offline, free).
6. `python run.py check` → live check with the key (main, backup, fallback drill).
7. Optional: `python run.py dashboard` → Gemini cost dashboard on http://localhost:8600.

Notes:
- `data/` (cost log, logs, database) is per machine and not in git. The daily cost cap ($1) counts per machine.
- Pydantic AI was installed on the office PC for inspection only. It gets pinned in `requirements.txt` when the
  agent is built.
- Claude's own notes ("memory") live per machine. Everything important is in `CLAUDE.md` and this file,
  so a new session on another machine has the same rules.

## 5. Next session: start here

1. Ask Karthi the two open questions of **memory Part 6** (`docs/plans/memory.md`).
2. Then continue `docs/plans/open-topics.md` in order: **RAG design (topic 3)** → tool contracts → personality
   and answer style → message/card formats → meetings (text mode) → skill files list → simulated team world +
   test set → build plan.
3. Walk through each topic **one part at a time**; record agreements in the docs; tick in `open-topics.md`.
