# Max: agent loop design

**Status: APPROVED by Karthi (25 Nov 2026).** Next: the loop as an exact graph of nodes and edges (section 11).
Implements `03-requirements.md` (rules R-1 … R-13). Framework: Pydantic AI 2.74 (checked: it has step/cost
limits, approve/deny pauses, run cancel). Pydantic AI lives only in `max/agent/runner.py`.

## 1. The big picture

```
 TRIGGER            INTAKE                     RUNNER (agent loop)                   OUTPUT
 @mention    ─┐     who asked, where,          ┌──────────────────────────────┐
 meeting end  ├──►  who will see the answer,──►│ model thinks → picks a tool  │──► reply / card / notes
 timer/job    │     task type + budget,        │   ▲              │           │    + sources panel
 card click  ─┘     settings from setup        │   └── tool result┘           │
                                               │ L1/L2 tools: run at once     │
                                               │ L3 tools: PAUSE → approval   │──► approval card
                                               │ budget hit: PAUSE → Continue?│──► continue card
                                               └──────────────────────────────┘
                     everything is written to the runs + audit tables (R-11)
```

## 2. Task types and budgets (answer to "it depends on the task")

The trigger decides the task type. For an @mention Max starts as **answer**; if the job turns out to be
bigger, the agent calls `ask_for_more_steps(reason)`, which shows a **Continue?** card (the person decides).

| Task type | Examples | Tool steps | Time | Cost per run |
|---|---|---|---|---|
| **quick** | thanks, clarify, refuse | 0 | 15 s | $0.002 |
| **answer** | question, find in a file, decisions, what did I miss | 8 | 60 s | $0.02 |
| **summary** | catch up, meeting brief, weekly digest | 12 | 90 s | $0.03 |
| **meeting_notes** | notes, decisions, action items from a transcript | 10 | 120 s | $0.05 |
| **plan** | tasks from a meeting, goal to plan, multi-step actions | 20 | 3 min | $0.05 |
| **research** (R2) | web research report | 30 | 5 min | $0.10 |

- **Continue?** adds the same budget again. Max first posts what it has done so far.
- **Loop guard:** the same tool with the same input 3 times stops the run with a clear message.
- **Daily cap** ($1, cost meter) applies on top of everything.
- All numbers are settings (first-run setup), not code.

## 3. A run, step by step

| State | Meaning | Shown to the person |
|---|---|---|
| `queued` | Waiting: one run at a time per conversation; new questions queue, **never dropped** | "Got it, after the current one" |
| `running` | Agent loop working | Typing indicator + **Stop** button |
| `waiting_approval` | Paused on an L3 tool | Approval card (exactly what will happen) |
| `waiting_continue` | Budget reached on a big task | Progress so far + Continue / Stop |
| `done` | Answer posted | Answer + folded sources panel |
| `stopped` | Stop pressed | "Stopped. Nothing more was sent." |
| `failed` | Model down, error | Clear message (R-1), never silence |
| `expired` | Approval not given in 24 h | "Not done: no approval" |

**Stop (R-5):** sets the run's stop flag and cancels it (Pydantic AI `RunCancelled`). Pending actions of that
run are cancelled in the database, so a later approval click does nothing. A run is checked for the stop flag
before every tool call, so nothing is sent after Stop.

**Restarts:** runs, pending approvals and timers live in SQLite. After a restart, paused runs can still be
approved; a run that was mid-thinking is marked `failed` with a message ("I was restarted, please ask again").

## 4. Tools: one registry, levels enforced in code

Every tool is a plain Python function plus a small description:

```python
@tool(level="L1", task_types=["answer", "summary", ...])
def search_knowledge(ctx, query: str, after: date | None = None, kind: str | None = None) -> list[Snippet]:
    """Search the team's posts, files and meetings. Returns ~8 short snippets with ids and sources."""
```

| Gate (in code, not in the prompt) | What it does |
|---|---|
| **Level check** | L1/L2 run at once. L3 raises `ApprovalRequired` → run pauses (Pydantic AI deferred tools) → approval card → resumes with approved/denied. L4 tools are never given to the model. |
| **Who approves** | From setup: requester / organizer / owner. Wrong person clicking → "Only X can approve this". |
| **Audience filter (R-8)** | Every read tool gets the audience from the run context (who will see the answer). The model can't change it. |
| **Outside-content rule (R-7)** | A run started by outside content (a file, web page, other app) gets no L3 tools. Tool results are wrapped as data: "content from file X: …". |
| **Stop + budget check** | Before each tool call. |
| **Audit** | Every call: tool, input, result size, time, who, why. |

Tool list for R1: `search_knowledge`, `read_thread`, `list_recent`, `read_file`, `get_transcript`,
`list_people`, `get_calendar`, `list_tasks`, `calc` (numbers from code, R-12), `record_decision`,
`post_message`, `propose_tasks` (L3), `update_task`, `schedule_job`, `list_jobs`, `cancel_job`,
`ask_for_more_steps`. Stubs: `make_document`, `ask_agent`.
**Full, current list with exact inputs/outputs: `05-tools.md`** (26 Nov: adds `query_sheet`, `list_decisions`,
`send_private_message`, `save_meeting_notes`, and email + meetings moved into R1).

## 5. What the model sees (small, not "everything")

1. **Instructions** (`max/agent/prompts/*.md`, plain text): who Max is, the rules, how to cite.
2. **Situation:** who asked, where, who will see it, the time in JST, working hours, the task type and budget.
3. **The conversation:** the current thread (last ~20 messages), not the whole channel.
4. **Tools** for this task type only (fewer tools = fewer mistakes).
Everything else is fetched with tools when needed (search first, then open only what's needed).

## 6. Models and cost

- The model for Pydantic AI is built by `max/llm/` (one place): main `gemini-3.1-flash-lite`, backup
  `gemini-3.5-flash-lite` (Pydantic AI `FallbackModel`), with our time limits.
- A thin wrapper model (Pydantic AI `WrapperModel`) checks the cost meter before every model request and records
  each one: the daily cap, pause switch and dashboard work for the agent exactly like for `ask()`.
- Per-run budget uses Pydantic AI `UsageLimits` (request, tool-call and cost limits).

## 7. Proactive runs (timers, chasing, digest, briefs)

One loop reads the `jobs` table every 30 s: due jobs start a run with trigger `schedule`. Rules:
working hours for Max's own messages (R-9), message limits (R-10), "why you got this" line, and the job's
owner/audience for the privacy filter. Repeating jobs compute their next time after each run. Survives restarts.

**Missed jobs (PC was off), agreed:** a person's own reminder is sent late with "(late: I was offline at 03:00)";
digest and chasing are sent late only on the same working day, otherwise skipped; a meeting brief is skipped
if the meeting has already started.

## 8. Files (inside `max/agent/`)

| File | What |
|---|---|
| `runner.py` | **The only Pydantic AI file**: builds the agent, runs it, pauses/resumes, cancels |
| `intake.py` | Trigger → run context (who, where, audience, task type, budget) |
| `tools.py` | Tool registry + the R1 tools (thin; real work in `store/`, `graph/`) |
| `policy.py` | Levels, approvers, budgets, working hours, message limits (reads setup settings) |
| `prompts/` | Instructions as text files |
| `jobs.py` | Timer loop for proactive runs |
New tables in `store/`: `runs`, `pending_actions`, `jobs`, `audit`, `settings`.

## 9. How we test it (offline, free)

- Pydantic AI `FunctionModel` plays scripted model turns: tests for every state, Stop, approvals (approve,
  deny, wrong person, expiry, double click), budgets, Continue, loop guard, outside-content rule, privacy filter.
- A 40-question test set over the sample world, run with the real model on demand (accuracy + cost report).
- A test that LangGraph could replace `runner.py`: the same scenario tests call the runner only through
  one small interface (`start`, `resume`, `stop`).

## 10. Open questions
1. Are the **task types and budgets** right? (All are settings; these are the defaults.)
2. ~~Queue rule~~: **one run at a time per thread** (agreed).
3. ~~Mid-thinking restart~~: **mark as failed with "I was restarted, please ask again"** (agreed).
4. Budgets per task type + Continue card: **agreed**.

## 11. The loop as a graph (nodes and edges)

**Status: DRAFT, walked through with Karthi one part at a time.**
The runner implements exactly this graph (Pydantic AI `agent.iter()` lets our code step node by node, so
our gates run between nodes). Each node maps 1:1 to a LangGraph node if we switch later.
Every edge writes one line to the audit table.

### 11.1 Overview

Visual: `docs/plans/pictures/agent-loop.excalidraw` (open at excalidraw.com or with the VS Code Excalidraw extension); quick picture: `pictures/agent-loop-preview.png`.

```
            ┌──────────┐    ┌─────────┐    ┌─────────┐    ┌──────────┐
 trigger ──►│ 1 INTAKE ├───►│ 2 QUEUE ├───►│3 PREPARE├───►│ 4 THINK  │◄─────────────────────────┐
            └────┬─────┘    └─────────┘    └─────────┘    └────┬─────┘                          │
                 │ quick reply (L0)                            │                                │
                 ▼                                   answer ───┤─── tool calls                  │
            ┌──────────┐                                       ▼            ▼                   │
            │ 8 REPLY  │◄──────────────────────────── (answer) │       ┌──────────┐             │
            └────┬─────┘                                       │       │ 5 GATES  │             │
                 ▼                                             │       └──┬─┬─┬─┬─┘             │
              DONE                                             │  run     │ │ │ │  not allowed  │
                                                               │  now ────┘ │ │ └── (tell AI) ──┤
                                                               │     ▼      │ │                 │
                                                               │ ┌────────┐ │ │                 │
                                                               │ │ 6 ACT  ├─┼─┼─ result ────────┤
                                                               │ └────────┘ │ │                 │
                                                               │  needs     │ │ budget used     │
                                                               │  approval ─┘ └──────┐          │
                                                               │     ▼               ▼          │
                                                               │ ┌──────────┐  ┌───────────┐    │
                                                               │ │7a APPROVE│  │7b CONTINUE│    │
                                                               │ └──┬───┬───┘  └──┬─────┬──┘    │
                                                               │ yes│   │no   yes │     │ stop  │
                                                               │    ▼   └─(tell AI)┴─────┼──────┘
                                                               │  6 ACT              ▼
    any node: Stop pressed ──► STOPPED · error/timeout ──► FAILED · 24 h no answer ──► EXPIRED
```

### 11.2 Nodes

| # | Node | Does | Writes / sends |
|---|---|---|---|
| 1 | **INTAKE** | Build the situation: who, where, audience, task type, budget, settings. Pure code, no AI | run row (`queued`) |
| 2 | **QUEUE** | Wait while another run is active in the same thread | "Got it, after the current one" (only if waiting) |
| 3 | **PREPARE** | Instructions + situation + last ~20 thread messages + tools for this task type | run → `running`; typing + Stop button |
| 4 | **THINK** | One model request (cost guard → main/backup model). Output: final answer, or tool calls | cost log |
| 5 | **GATES** | For each tool call, in order: Stop? → budget/loop? → allowed for this run (level, outside-content rule)? → L3? | audit |
| 6 | **ACT** | Run the tool (audience filter inside). Result goes back to THINK as data | audit, tool result |
| 7a | **APPROVE** | Pause: save pending action, post approval card to the right approver | run → `waiting_approval`; card |
| 7b | **CONTINUE** | Pause: post progress so far + Continue / Stop | run → `waiting_continue`; card |
| 8 | **REPLY** | Post the answer + folded sources panel (or the quick L0 reply) | message; run → `done` |
| — | **STOPPED / FAILED / EXPIRED** | End states with a clear message (R-1) | run state + message |

### 11.3 Edges (what comes next, and when)

| From | To | Condition |
|---|---|---|
| 1 INTAKE | 8 REPLY | Task type `quick` and no tool needed (greeting, refusal of an L4 request) |
| 1 INTAKE | 2 QUEUE | Otherwise |
| 2 QUEUE | 3 PREPARE | No other active run in this thread |
| 3 PREPARE | 4 THINK | Always |
| 4 THINK | 8 REPLY | Model returns a final answer |
| 4 THINK | 5 GATES | Model asks for one or more tools |
| 4 THINK | FAILED | Main and backup model both fail, or the run's time limit is hit |
| 5 GATES | STOPPED | Stop flag set |
| 5 GATES | 7b CONTINUE | Step or cost budget used up, or the agent called `ask_for_more_steps` |
| 5 GATES | FAILED | Loop guard: same tool + same input 3rd time ("I'm going in circles, stopping") |
| 5 GATES | 4 THINK | Tool not allowed in this run: the AI is told "not allowed: <reason>" and must answer without it |
| 5 GATES | 7a APPROVE | Tool is L3 |
| 5 GATES | 6 ACT | Tool is L1/L2 and all checks pass |
| 6 ACT | 4 THINK | Always (tool result, or the tool's error as data) |
| 7a APPROVE | 6 ACT | Right person approves (payload unchanged since the card was made) |
| 7a APPROVE | 4 THINK | Denied: the AI is told "denied by <person>" and replies accordingly |
| 7a APPROVE | EXPIRED | No answer in 24 h |
| 7a / 7b | STOPPED | Stop pressed while waiting |
| 7b CONTINUE | 4 THINK | Continue pressed: budget refilled |
| 8 REPLY | DONE | Message posted |
| any | STOPPED | Stop pressed (checked at nodes 3, 5, before 6, and while waiting) |
| any | FAILED | Unexpected error: message "Something went wrong, I stopped" + full error in the log |

## 12. Three modes and skill files (agreed with Karthi, 25 Nov 2026)

Intake (code, not the AI) picks the mode from the task type.

| Mode | How | Task types | Who plans |
|---|---|---|---|
| **1. Workflow** | Fixed steps in code; the AI is only used to write (with the skill file) | meeting notes, meeting brief, weekly digest, chasing, reminders | Code |
| **2. Simple loop** | The loop in the diagram: THINK ⇄ GATES ⇄ ACT | questions, catch-up, decisions, find in files | Skill file + the model's thinking, inside THINK |
| **3. Plan, then act** | PLAN node first: the AI writes the plan as a list; the loop follows it, ticks steps off, and can adjust if a step fails | goal to plan, multi-step actions, research, big comparisons | The written plan (visible, survives pauses) |

- **Plan approval:** only when the plan contains actions (L3). A plan with only reading steps just runs, with progress shown.
- **Skill files** (`max/agent/skills/<task>.md`): a short how-to per task type (steps, output format, examples), loaded
  only for that task. Written later, after all design discussions.
- **No matching skill:** general "answer" mode (general instructions + thinking). If it turns out big, the agent
  switches to mode 3 (the person sees the plan). Unmatched requests are logged, to decide which skills to write next.
- **Thinking level** per task type (a setting): low for questions, higher for notes and mode-3 plans (slower, a bit costlier).
- Diagram: `pictures/agent-loop.excalidraw` (PLAN and WORKFLOW nodes added).
