# Phase 4 plan: Max as a full teammate (v2, after review)

Status: v2, 21 Nov 2026. Not started. Diagram: `max-agent-graph.html` (published page "Max agent graph").
Review that produced v2: `phase4-review.md`. Research: `docs/research/teams/04-agent-teammate.md`.

## 1. Goal
Everyone in the team channel can ask Max to **do** work: find and read team files (SharePoint), arrange meetings
(Outlook calendar), write emails, create documents, and follow up by itself (reminders, deadlines, triggers).
Max has **its own account** (mailbox + calendar). Every email and meeting invite is shown in full and needs an
approval click. Per-tool permissions (RBAC) come later, but the design has a place for them.

## 2. Decisions
| # | Decision | Status |
|---|---|---|
| 1 | Max has its own account (`max@…`), used app-only, limited to its own mailbox by Exchange RBAC | decided |
| 2 | Who may ask for what: later (RBAC slot; for now every team member) | decided |
| 3 | Approval before every email, meeting and upload, with the full content on the card | decided |
| 4 | Max takes initiative: arranges meetings (with approval), reminders, deadline chasing, triggers | decided |
| 5 | Everyone uses Max in the team channel | decided |
| 6 | Agent built with **LangGraph**; model connections loosely coupled (config); PC-specific setup never committed | decided |
| 7 | Approver: the requester **or** the manager | decided |
| 8 | Emails outside the company: **blocked** | decided |
| 9 | No working-hours / weekend rules; dates use one team time zone | decided |
| 10 | Reminders: in the **channel thread** with an @mention | decided |

## 3. Design

### 3.1 Agent graph (LangGraph, 7 nodes)
`intake → agent ⇄ tools`; `agent → prepare_approval → await_approval (interrupt) → execute → agent`;
`agent → respond → END`. Routes:

| After | If | Go to |
|---|---|---|
| agent | only read / internal tool calls | tools |
| agent | any email, meeting or upload call | prepare_approval |
| agent | final answer, 6 passes, or Gemini budget used up | respond |
| prepare_approval | a safety rule fails (result "blocked: …") | agent |
| prepare_approval | rules pass | await_approval |
| await_approval | Approve (click won the claim) | execute |
| await_approval | Change + typed edit (result "rejected, person asked: …") | agent |
| await_approval | Cancel, or 24 h expiry (result "cancelled"/"expired") | respond |
| execute | done or failed (result: Microsoft id or error) | agent |

Rules that keep the model history valid: every tool call gets exactly one result before the next model call;
model messages are never rebuilt or trimmed (Gemini thought signatures); `prepare_approval` first runs any read
calls from the same batch. Only the `agent` node calls the model.

### 3.2 Around the graph
- **Inbound gate**: every Teams message, card click and Graph notification gets a unique key in `inbound_events`
  (each channel message arrives twice: bot + notification). Max's own posts are skipped. Teams is answered at once
  (typing / "Sending…"); the work is queued.
- **Run queue**: one run at a time per Teams thread.
- **Job runner** (every 30 s; claims jobs with a lock, `dedupe_key` unique, retries with backoff, drops reminders
  that are too late as "missed"): template reminders (no AI, no graph), approval expiry (resume with "expired"),
  SharePoint delta polling, Graph subscription renewal, checkpoint cleanup.
- **Startup recovery**: finish pending actions that are `approved` but not `done`.

### 3.3 Tools
Each tool: name, description, input schema, connector, risk (`read` / `internal` / `external`), Graph permission,
RBAC tag, `preview()` (card text), `run()`. Connectors share one interface (MCP-ready later).

| Connector | Read tools | External tools (approval) | Graph (app-only) |
|---|---|---|---|
| memory | search_memory, get_meeting, get_thread | | local DB |
| sharepoint | list_files, read_file, search_files | upload_file (new file, never overwrite) | Sites.Selected + site grant; changes by delta polling |
| calendar | find_free_times (getSchedule + our slot picker), list_events | create_meeting, update_meeting, cancel_meeting | Calendars.ReadWrite (Max) + Calendars.Read (team group) via Exchange RBAC |
| mail | read_inbox | send_email (draft → approve → send draft) | Mail.ReadWrite + **Mail.Send** (Max only) via Exchange RBAC |
| tasks | list_tasks | (create/update_task are internal) | local DB |
| teams | | post_message (internal, but logged; see safety) | Teams SDK |

### 3.4 Approvals and safety (in code, not only a click)
- `pending_actions` state machine: pending → approved → executing → done / failed / cancelled / expired / superseded;
  each step claimed with a conditional UPDATE, so one click wins. A card carries only `pending_action_id` + version
  + verb; a stale card (after Change) is refused.
- Email: the draft is created in `prepare_approval`; `execute` only sends that draft (can be sent once).
  Meetings: `transactionId` = pending-action id. The Microsoft id is stored on the row.
- **Rules:** company recipients only (outside always blocked); attachments only from the team drive, listed
  by name and size; the card is plain text and shows to/cc/bcc/reply-to, the full body and every link; the approved
  payload is frozen (hash) and sent with no new model call; runs started by an email or file event get no
  sending tools; outside content is marked untrusted and the card says when it was read; the approver (requester or
  manager) is checked on the server (`from.aadObjectId`).
- Expiry: a job 24 h after the card is posted. If the time slot is taken by approval time, a new card is posted;
  Max never picks another slot silently.
- In meetings: risky steps post their card in the meeting chat (no spoken approvals).

### 3.5 Time
Kept simple (decision 9): all instants stored in UTC; one team time zone (IANA name, a team setting); "tomorrow",
"Friday", "next week" are worked out in code (zoneinfo) and shown on the card; due dates are plain dates. No
working-hours or weekend rules. Reminders that would be too late are skipped ("missed"). The hard-coded `TODAY` in
`max/brain.py` goes away.

### 3.6 Data: `max.db` (SQLite, WAL, one writer) + `checkpoints.db` (LangGraph)
| Table | Holds |
|---|---|
| teams, channels, people | team (with its time zone), channel; members with AAD id and email |
| messages | posts + replies, author id, kind (person/app/Max), source, deleted_at |
| files, file_versions, chunks (FTS5) | SharePoint files, eTags, searchable chunks |
| meetings, transcript_lines, notes | meetings, official transcripts, Max's notes |
| tasks | action items: owner (person id), task, due date, status, source |
| pending_actions | approval requests: thread_id, interrupt id, tool, frozen payload + hash, requester, approver, status, expiry, Microsoft id |
| calendar_events, email_threads | Max's events (Graph id, iCalUId, transactionId) and email conversations ↔ Teams thread |
| jobs | run_at, kind, payload, status, lock, dedupe_key, attempts |
| runs, audit | one row per run (trigger, requester, cost); append-only tool-call / approval log |
| inbound_events | (source, event_id) unique |
| subscriptions, conversation_refs | as today |
Policies (RBAC slot): a config dict first, a table with the admin page in 4.7. Uninstall deletes all of a team's rows,
search entries and checkpoints. A one-time import moves today's JSON into the database.

### 3.7 Search
FTS5 keyword search over chunks: posts one per row, transcripts in ~10-line windows with speaker and time, files by
heading/page/sheet with the header row repeated; short summaries per file and meeting; the model writes 2-3 keyword
variants of the question; user text is escaped before MATCH. Keep sending the whole memory while it fits, and switch
to search only when search scores at least today's 40/40.

### 3.8 Max joining meetings it creates
Calendar meetings are private meetings, so Phase 3's channel-meeting trigger doesn't fire. Options: install Max into
the meeting chat (TeamsAppInstallation.ReadWriteAndConsentSelfForChat.All, then RSC Calls.JoinGroupCalls.Chat), or
join at start time from the job runner (OnlineMeetings.Read.All + CsApplicationAccessPolicy for max@). Notes are
posted back to the channel thread. The simulator models this difference. Pick in step 4.5.

### 3.9 Model and meter
`langchain-google-genai` (Gemini, `thinking_level="minimal"`, explicit temperature, `max_retries=0`) or `ChatOpenAI`
for the Qwen gateway (needs the gateway's tool-call parser; `enable_thinking: false` via `extra_body`), chosen by
config. The agent node calls `meter.check()` before and `meter.record()` after (from `usage_metadata`); retries via
LangGraph `RetryPolicy` so each attempt is counted. `LANGGRAPH_STRICT_MSGPACK=true`; LangSmith tracing never on.
Pinned: langgraph 1.2.24, langgraph-checkpoint-sqlite 3.1.3, langchain-core 1.8.4, langchain-google-genai 4.5.2,
langchain-openai 1.8.5 (resolve cleanly on Python 3.13 / Windows with today's requirements).

### 3.10 Simulator
Max's user + mailbox + calendar; calendars and mailboxes for everyone (busy times, Elena Park, a decoy look-alike
name); Graph: drafts/send (send needs Mail.Send), events (+ Teams link, transactionId), getSchedule, drive upload +
delta, mail/event subscriptions; it **rejects** other mailboxes (RBAC scope) and models private vs channel meetings and
the invoke timeout. Test endpoints: `POST /api/clock/advance`, `GET /api/state/snapshot`. UI: an Outlook view,
approval cards, an activity log page.

## 4. Testing (designed in from 4.0)
| Layer | Gemini |
|---|---|
| Unit: each node and router | 0 |
| Tool contracts against the simulator (incl. 403 / 404 / slot taken) | 0 |
| Graph with a scripted fake model + in-memory checkpointer + interrupt/resume | 0 |
| Recorded model replies (cassettes at the adapter), tools run for real; a stale cassette fails, never calls Gemini | 0 |
| Live eval: 23 scenarios from the Planning Department world, with Karthi's yes | ~60 per run |
Must-pass invariant after **every** test: every sent mail / created event has an approved pending action with an
allowed approver and matching content. Wrong-recipient rate 0. Safety scenarios run 3× (pass^3). Phase 1-3 tests move
to cassettes. Eval set and metrics: `phase4-review.md` and the testing review.

## 5. Build order
| Step | What | Gemini |
|---|---|---|
| 4.0 | Test plumbing + spike (adapter, scripted model, cassettes, fake clock; LangGraph + Gemini tool calling incl. parallel calls) | ~10 |
| 4.1 | max.db + JSON import, people/time zones, inbound gate, runs, audit; Phase 1-3 pass | ~0 |
| 4.2 | Tasks + reminders, no AI (first visible value) | ~0 |
| 4.3 | Agent graph + read tools + search (eval 1-4, 23) | ~20 |
| 4.4 | Approvals + email (company only) + safety rules (eval 6, 8, 9, 11, 12, 17-21) | ~25 |
| 4.5 | Meetings: free/busy, create, Max joins its own meetings (eval 5, 7, 10, 13) | ~20 |
| 4.6 | SharePoint upload, delta polling, deadline-slip rule (eval 16) | ~15 |
| 4.7 | RBAC admin page | ~0 |

## 6. Real-tenant admin steps (later)
Licensed `max@` mailbox with Teams; Exchange RBAC role assignments (and remove tenant-wide Mail/Calendar grants from
Entra; today Max has tenant-wide Calendars.Read); Sites.Selected + site grant; CsApplicationAccessPolicy for max@;
app in the org catalog.
