# Max: tool contracts (topic 4)

**Status: ✅ AGREED (26 Nov 2026), all 4 parts.** Exact inputs and outputs of every R1 tool.
Tool list: `02-use-cases.md` §4. Knowledge design: `07-rag.md`. Levels and gates: `04-agent-design.md`.

| # | Part | Status |
|---|---|---|
| 1 | Rules every tool follows | ✅ Agreed (26 Nov) |
| 2 | Reading tools (search, threads, files, transcripts, sheets, people, tasks, meetings) | ✅ Agreed (26 Nov) |
| 3 | Action tools (post, private message, decisions, tasks, meeting notes, email, meetings, memory) | ✅ Agreed (26 Nov) |
| 4 | Timers and jobs (+ stubs; files, charts and web are R2/later) | ✅ Agreed (26 Nov) |

## Part 1: rules every tool follows (AGREED 26 Nov 2026)
1. **Clear, typed inputs with limits** (Pydantic models).
2. **Same result shape every time:** `ok`, `data`, `sources` (piece/message/file ids), `note`.
3. **Errors in plain words the AI can act on** ("file too big, ask for a section (it has 12)"), never a stack trace.
4. **Each tool has a control level** (L1 read, L2 post, L3 needs approval, L4 never). Gates check it before the call.
5. **Outside content is marked as data, never commands** (messages, files, web pages, transcripts).
6. **Every call is logged** in the run card: input, result size, time, cost.
7. **No double actions:** every action carries a "done once" key, so a retry never posts or creates twice.
8. **Plain Python**, usable by any model and any agent framework.
9. **Limits are settings** (max results, file size, timeouts), editable any time.

## Part 2: reading tools (AGREED 26 Nov 2026)
**Common:** all are L1 (read only). **The audience is set by code from the run** (who will see the answer), never by
the AI, so the privacy filter can't be talked around. Long content comes in pages or sections, never all at once.

| Tool | Inputs | Returns | Notes |
|---|---|---|---|
| `search_knowledge` | `query`, `other_phrasings` (0-3), filters: `chat`, `person`, `from_date`, `to_date`, `kind` (thread / chat / file / meeting / notes), `limit` (default 8) | Best pieces: id, title line, where, who, when, ~300-char snippet, link | Runs the agreed pipeline (keyword + meaning → merge → re-rank). `note` says if dates are older than the knowledge horizon or a chat is behind |
| `read_thread` | `thread_id`, `page` | Post + replies (author, time, text), 50 replies per page | Edited/deleted shown as current state only |
| `list_recent` | `chat`, `since`, `until?`, `page` | Messages and threads in that window, oldest first | For "what did I miss?" and summaries |
| `read_file` | `file_id`, `section?` | Small file: whole text. Big file: table of contents, then the asked section | Includes the quality label (text OK / partly OCR) |
| `get_transcript` | `meeting_id`, `from_min?`, `to_min?` | Lines with speaker + minute; Max's meeting notes if they exist | Short meeting: whole; long: ask for a range |
| `query_sheet` | `file_id`, `sheet`, `columns?`, `filter?`, `group_by?`, `op` (sum / avg / count / min / max / list) | Result table + which rows were used | Numbers by code (Decision 3) |
| `query_sheet_custom` | `file_id`, `query` (written by the AI) | Result table | Only when `query_sheet` can't do it. Read-only, no internet, no files, time limit; the query is shown in the sources |
| `calc` | `expression` | Number | Safe calculator (no code run); for differences, %, totals across tools |
| `list_people` | `team?`, `name?` | Members: name, role, team, work facts (dated, sourced) | |
| `list_decisions` | `topic?`, `from_date?`, `to_date?` | Decisions: what, date, who, source | Decisions log (A-3) |
| `list_tasks` | `plan?`, `owner?`, `status?`, `due_before?` | Tasks: title, owner, due, status, plan | |
| `get_calendar` | `from`, `to`, `person?` | Meetings: title, time, attendees, agenda, link | For meeting briefs (M-1) |

Not in R1: `read_audit` (U14), web tools (R2). (`find_free_time` moved into R1 with meetings, see Part 3.)
Agreed 26 Nov: list complete for R1; audience always set by code. (`get_calendar` keeps the name from `04-agent-design.md`.)

## Part 3: action tools (AGREED 26 Nov 2026)
**Common:** every action carries a "done once" key (no double posts on retry). Cards that code posts by itself
(meeting notes card, living plan card, digest, brief, approval and Continue cards) are **not** AI tools: workflows
post them, and their look is topic 6. The AI only gets the tools below, and only those its task type needs.

| Tool | Inputs | Returns | Level + guard |
|---|---|---|---|
| `post_message` | `text`, `sources`, `reply_to` (default: the current thread) | message id + link | **L2** in the current conversation; posting in a different channel or chat = **L3** |
| `send_private_message` | `person`, `text`, `why` | message id | **L2** with limits (settings): max 3 per person per day, 1 chase per task per day, working hours only, always says why |
| `record_decision` | `what`, `decided_by`, `date`, `source` | decision id | **L2**; Max says "Recorded as a decision" so people can correct it |
| `propose_tasks` | items: `title`, `owner`, `due`, `source` | approval card → created tasks | **L3**: the organizer approves the batch; then each owner gets Accept / Change date / Not mine |
| `update_task` | `task`, `status` / `due` / `owner` / `note`, `why` | updated task; the plan card refreshes itself | **L2** when the task's owner or plan owner asked; otherwise **L3** |
| `save_meeting_notes` | `meeting`, `summary`, `decisions`, `actions`, `risks` | draft notes | **L2**; posted, but becomes searchable knowledge only after review (M-6) |
| `ask_for_more_steps` | `reason`, `done_so_far` | Continue card | The person decides (R-6) |

Stubs (return "not available yet"): `make_document`, `ask_agent`. Not in R1 (R2): uploading files, web research.

**Email and meetings (moved into R1 by Karthi, 26 Nov 2026; web search stays R2):**

| Tool | Inputs | Returns | Level + guard |
|---|---|---|---|
| `find_free_time` | `people`, `duration`, `from`, `to` | 3 best slots (working hours, time zone shown) | **L1** (reading tool) |
| `send_email` | `to`, `cc?`, `subject`, `body`, `sources` | sent email id | **L3**: the approval card shows the exact email; sent from Max's mailbox |
| `create_meeting` | `title`, `attendees`, `start`, `end`, `agenda`, `online` (yes) | meeting id + link | **L3**: the card shows people, time + time zone, agenda |
| `cancel_meeting` | `meeting`, `reason` | done | **L3**; attendees get the reason |

Guards (agreed 26 Nov): **email only to people inside the company in R1** (outside addresses blocked); max emails
per day = a setting. Moving a meeting = cancel + create (one approval card for both).

**Agreed 26 Nov 2026**, with Claude's review additions (Karthi: "you have all the rights to add them to make it
work"). Checked against every R1 requirement and the agreed memory design; these gaps were found and added:
| Addition | Why |
|---|---|
| `propose_tasks` gets `plan` (existing plan, or a new one: title + owner) | Living plan card (P-2) needs to know which plan |
| `record_decision` gets `replaces?` | A new decision closes the old one (newest wins); both stay in history |
| `edit_own_message` (`message`, `new_text`, `why`): L2, Max's own messages only, shows "edited" + why | Fix a wrong answer in place after a check or a correction |
| `show_memory` (`about`: me / this thread): L1 | "What do you know about me?" card (memory Part 3) |
| `correct_fact` (`fact`, `new_value`): L2 for own facts; others per the memory setting | Code closes the old fact, adds the new one (memory Part 3) |
| `forget` (`what`: message / meeting part / fact): L2 for own content; team content = L3 (team lead) | "Forget this" in chat (memory Part 5) |
| `propose_lesson` (`lesson`, `from_person`): L2; active only after the team lead accepts | Lessons only from people (memory Part 4) |

## Part 4: timers and jobs (AGREED 26 Nov 2026; Parts 4 + 5 merged)
Files (`make_document`), charts and web research are stubs or R2, so only timers need contracts in R1.

| Tool | Inputs | Returns | Level + guard |
|---|---|---|---|
| `schedule_job` | `what` (a reminder text, or a task for Max to run), `when` (once: date + time; or repeat: "every Monday 9:00"), `for` (me / this chat / a person) | job id + Max repeats it back with the time zone: "Reminder set: Mon 1 Dec, 09:00 JST" | **L2** for yourself or this chat; for another person it goes as a private message (message limits apply); repeating tasks that post in a channel = **L3** |
| `list_jobs` | `for` (me / this chat) | Active jobs: what, next time, who made it | **L1** |
| `cancel_job` | `job` | done | **L2** for your own jobs; someone else's = their OK or the team lead |

**Rules (all limits are settings):**
- Jobs are saved in the database, so they **survive restarts**. Missed while the computer was off → run at the next
  start if less than ~2 hours late; otherwise skipped with a short "missed" note to the owner.
- A time the person chose explicitly is kept, even outside working hours ("at 3 AM"). Reminders Max starts on its own
  (chases, briefs) stay within working hours.
- A job that runs a task (e.g. "every Friday summarise this channel") runs **as the person who made it**, with that
  task type's budget, and can be stopped like any run.
- Guards: max ~40 active jobs per person (Karthi, 26 Nov); repeats no more often than every 15 minutes; a job that fails 3 times
  pauses itself and tells its owner.
