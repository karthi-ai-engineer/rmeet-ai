# Phase 4 plan review (4 independent reviewers, evaluated 21 Nov 2026)

Reviewed: `phase4-max-teammate.md` + `max-agent-graph.html`. Reviewers: LangGraph tech, Microsoft 365 feasibility,
architecture & security, testing & evaluation. Two claims checked by hand: 22 Nov 2026 is a Sunday (the example was
wrong); Max holds tenant-wide `Calendars.Read` today (`simulations/teams/register_app.py:36`).

## Verdict: GO WITH CHANGES
| Reviewer | Verdict |
|---|---|
| LangGraph | go with changes (installs cleanly on Py 3.13/Windows: langgraph 1.2.24, checkpoint-sqlite 3.1.3, MIT, no conflicts) |
| Microsoft 365 | everything maps to real Microsoft; 3 design changes before step 4.3 |
| Architecture & security | direction sound; 3 blockers must be in the design from the start |
| Testing | testable, if test plumbing (fake model, clock, snapshot, cassettes) comes first |

## Blockers (fix in the design before any code)
1. **No double sends.** `pending_actions` state machine (pending → approved → executing → done/failed) claimed with a
   conditional UPDATE (one click wins); email = draft created in `prepare_approval`, `execute` only sends that draft;
   meetings carry `transactionId` = pending-action id; store the Graph id; on startup finish `approved`-but-not-done rows.
2. **Answer Teams at once, work in the background.** Messages and card clicks get an immediate reply ("Sending…");
   runs go to a per-thread queue. `inbound_events` table dedupes events (every message arrives twice: bot + Graph
   notification). Never trigger on Max's own posts.
3. **Safety floor in code, not only a click.** Company recipients only (outside blocked until decided); attachments
   only from the team drive, listed with name/size; plain-text card that shows to/cc/bcc/reply-to and full links;
   after approval send the frozen payload (hash match, no new model call); runs started by an email or file event get
   no send tools; outside content wrapped as untrusted; server-side approver check; `post_message` is a leak path too.
4. **Thread id.** One LangGraph thread per request; each pending action stores `thread_id` + interrupt id. (The
   "pending-action id = thread id" idea in the draft cannot work.)
5. **Max joining meetings it creates.** Calendar meetings are private meetings, not channel meetings, so the Phase 3
   trigger doesn't fire. New path: install Max into the meeting chat (TeamsAppInstallation.ReadWriteAndConsentSelfForChat.All)
   or join at start time from the scheduler (OnlineMeetings.Read.All + CsApplicationAccessPolicy). Post notes back to
   the channel thread. The simulator must model this difference.

## Important changes
| # | Change | From |
|---|---|---|
| 6 | Permissions: add **Mail.Send**; move Mail/Calendar grants from Entra to **Exchange RBAC** (Max's mailbox; team group for free/busy); SharePoint file triggers by **delta polling** (no drive subscriptions under Sites.Selected); upload v3 as a new file | Microsoft |
| 7 | Time: store UTC; `people` with time zone + working hours; "tomorrow" worked out in code; remove hard-coded `TODAY`; weekends | Architecture, Testing |
| 8 | Every tool call gets a result before the next model call (Change/Cancel add a result); never rebuild AI messages (Gemini thought signatures) | LangGraph |
| 9 | Approval expiry via a `jobs` row (LangGraph waits forever); job runner with locks, dedupe keys, "missed" reminders, backoff | LangGraph, Architecture |
| 10 | SQLite in WAL mode, one writer; checkpoints in their own `checkpoints.db` + cleanup job; `LANGGRAPH_STRICT_MSGPACK=true`; LangSmith tracing never on | LangGraph, Architecture |
| 11 | Gemini meter: check + record in the `agent` node from `usage_metadata`; library retries off, LangGraph `RetryPolicy` on | LangGraph |
| 12 | Tables: add `runs`, `inbound_events`, `email_threads`, `calendar_events`, `file_versions`; people ids instead of names; uninstall deletes everything | Architecture |
| 13 | Search: FTS5 with chunking (posts, ~10-line transcript windows, file sections) + query rewriting; keep "send all memory" until search scores ≥ today's 40/40 | Architecture |
| 14 | Test plumbing first: scripted fake model, cassettes at the model adapter, fake clock, simulator snapshot/clock endpoints, approval-gate check after every test, 23-scenario eval set (~60 Gemini requests per live run) | Testing |

## Where reviewers disagreed, and the call
| Topic | Views | Call |
|---|---|---|
| LangGraph pause/resume | Architecture: drop interrupt + checkpointer, end the run at the card and start an execute job. LangGraph: keep it, with fixes 1, 4, 8, 9 | **Keep LangGraph with interrupt** (Karthi's choice; it gives the visible graph, saved state and an easy Change flow). With the fixes, the risks are covered. On a code update, expire old open cards and re-ask |
| Graph size | 9 nodes is more than needed | **Trim to 7**: merge intake + plan_tools, respond + audit; template reminders leave the graph (the job runner posts them, no AI, no checkpoint) |
| Over-engineering | MCP-ready connectors, rules engine, policies table, Change loop | Keep the connector interface (cheap). Triggers: 3-4 hard-coded with on/off flags first. Policies: a config dict first, table later. Keep Change (cheap with LangGraph) |

## Revised build order (each step ends with passing tests)
| Step | What | Gemini |
|---|---|---|
| 4.0 | Test plumbing + spike: model adapter, scripted model, cassettes, fake clock; LangGraph + Gemini tool calling incl. parallel calls | ~10 |
| 4.1 | Data store: SQLite (WAL), JSON import, people/time zones, inbound_events, runs, audit; Phase 1-3 tests pass on cassettes | ~0 |
| 4.2 | **Tasks + reminders (no AI):** action items → tasks, job runner, meeting/due/overdue reminders. First visible value | ~0 |
| 4.3 | Agent graph + read tools + FTS search; eval scenarios 1-4, 23 | ~20 |
| 4.4 | Approvals + email (company only) + the safety floor; scenarios 6, 8, 9, 11, 12, 17-21 | ~25 |
| 4.5 | Meetings: free/busy, create, Max joins its own meetings; scenarios 5, 7, 10, 13 | ~20 |
| 4.6 | SharePoint write + delta polling + deadline-slip trigger; scenario 16 | ~15 |
| 4.7 | RBAC admin page | ~0 |

## Decisions (Karthi, 21 Nov 2026)
1. **Who approves:** the requester or the manager.
2. **Emails outside the company:** blocked.
3. **Working hours / weekends:** no rules; dates use one team time zone.
4. **Reminders:** in the channel thread with an @mention.
