# Max: requirements

**Status: APPROVED by Karthi, 25 Nov 2026.**
Based on `docs/plans/02-use-cases.md` (agreed) and `docs/decisions.md`. Use-case IDs (U..) point there.

## 1. Goal and releases

**Goal:** Max is a semi-autonomous AI teammate in Microsoft Teams that knows everything the team has
posted, shared and said in meetings, answers with sources, writes notes, tracks plans and chases politely.
It only acts on its own inside clear limits, and asks before anything that leaves the conversation.

| Release | What | When |
|---|---|---|
| **R1: first release** | The Must items below, built at product quality, tested in the simulated Teams, English | First |
| **R2** | The Should items | After R1 works |
| **Later** | Parked topics (routines, memory design, Max Personal, integrations, Document Agent, voice) | Own planning |

**R1 size (agreed 25 Nov 2026):** everything runs on **one laptop** (Max, database, simulated Teams, voice).
About **4 simulated users in 1-2 teams**; Karthi plays all 4 himself in the simulated Teams. No other
computers connect in R1. The design stays the same for more people later (one Max program, memory split per
team and per person, short runs only when someone asks).

## 2. People and roles

| Role | Can do |
|---|---|
| **Member** | Ask Max, set own reminders, confirm own tasks, approve actions done for them, press Stop |
| **Meeting organizer** | Approve the task batch from their meeting, review notes before they become team knowledge |
| **Plan owner** | Gets private notes about late tasks in their plan |
| **Team lead** ("Max admin") | The leader of the chat/channel/team: first-run setup (approvers, levels, limits, working hours, digest), accepts lessons. Small, occasional work |
| **IT admin** | Installs Max and grants permissions **once**. Never part of Max's daily flow (no approvals, settings or lessons) |

## 3. Rules for every answer and action (R1)

| ID | Rule | How we check it |
|---|---|---|
| R-1 | **Never silent.** Every request gets an answer, a "working on it" note, or a clear error message | Test: model down → user still gets a message |
| R-2 | **Sources.** Every answer from team knowledge cites its sources; a folded "How I got this" shows steps and sources | Every test answer has ≥1 working source link |
| R-3 | **Control levels.** L0 no tool · L1 read (auto) · L2 write in own space (auto) · L3 approval card first · L4 never | Test per tool: L3 never runs without approval; L4 always refused |
| R-4 | **Approvals.** Who approves follows setup (default: requester for own actions; organizer for meeting task batch; owners confirm own tasks). Card shows exactly what will happen; one click wins; expires after 24 h | Card tests incl. double click, expiry, wrong person clicking |
| R-5 | **Stop button.** Every running task shows Stop. One click: nothing more is sent, pending actions are cancelled | Test: stop mid-run → no further messages, no action executed |
| R-6 | **Runaway guard, per task type.** Each task type has its own budget of tool steps, time and cost (see `04-agent-design.md`). A big task that needs more asks the person: "Done X so far. Continue?" (button), never a silent stop. Same tool with the same input 3 times = loop, stopped. Daily spend cap ($1) on top | Tests: loop stopped; budget reached → Continue card; Continue → resumes |
| R-7 | **Hidden-instruction guard.** Text from files, web pages, other apps is data, never commands. Runs started by outside content get no L3 tools | Test: file saying "email everyone" → no email action offered |
| R-8 | **Privacy filter.** An answer only uses content that **everyone who will see it** may see | Test: private-channel content never appears in a public answer |
| R-9 | **Working hours** 9:00-18:00 JST. Max's own automatic messages and the meetings it books stay inside them. Reminders a person sets fire at the time asked | Clock tests at 8:59, 9:00, 18:01 |
| R-10 | **Message limits** (setting): one chase per task per day, max 3 private messages per person per day; every proactive message says why it was sent | Limit tests |
| R-11 | **Audit.** Every run, tool call, approval and message is logged (who, what, why, sources) | Each test run leaves a complete audit trail |
| R-12 | **Numbers from code.** Totals, differences, percentages from spreadsheets are calculated by code, never guessed by the AI (U32) | Test: sum question matches the spreadsheet exactly |
| R-13 | **Notes consent.** In meetings Max posts a short "taking notes" notice; "pause notes" works (U30) | Paused part never appears in notes or search |

## 4. Features: R1 (first release)

### 4.1 Knowledge: import, sync, search
| ID | Requirement | Use cases | Acceptance |
|---|---|---|---|
| K-1 | First import: all channel posts, replies, files, meeting transcripts, people; stored raw (exact Graph JSON) | storage | Re-running import adds nothing new |
| K-2 | Keep in sync: notifications trigger a catch-up; catch-up on start + nightly compare (no 15-min polling; see `07-rag.md` Parts 2-3); edits and deletes followed | storage | Edited post shows new text; deleted post never used again |
| K-3 | Extraction: text from docx, xlsx (sheets/tables), pptx (slides), pdf. **OCR is a separate pipeline (later step)**; R1 uses text-based files | U3 | Each file is searchable by its content |
| K-4 | `search_knowledge(query, filters)` returns about 8 short snippets with ids and sources (keyword + meaning search, re-rank; see `07-rag.md`) | U1 U3 U6 | ~250-question test set: right source in top 8 for ≥ 90% |
| K-5 | Open only what is needed: `read_thread`, `read_file(section)`, `get_transcript(time range)`; small files whole | U1 U3 U6 | No answer sends more than needed (logged token counts) |
| K-6 | Short summary of each file and meeting at import | U2 U7 | Summaries exist for all files and meetings |

### 4.2 Answers in the channel
| ID | Requirement | Use cases | Acceptance |
|---|---|---|---|
| A-1 | @Max in a thread → answer in that thread with sources | U1 U3 U6 | Test set answers correct ≥ 85%, all with sources |
| A-2 | "What did I miss?" / summarise a thread or a period | U2 | Summary names the main decisions and open items |
| A-3 | Decisions log: decisions recorded with date, owner, source; "what have we decided about X?" | U23 | All decisions found with the right source |
| A-4 | Small talk, clarifying questions, refusals (L4) | U15 | No tool used for "thanks"; unclear request → one clarifying question |
| A-5 | **Follow-ups without @Max** (Karthi, 26 Nov 2026): a reply to Max's message, or the next message in a conversation with Max, is answered without @Max again. Max never cuts into people talking to each other (rules in `08-personality.md` Part 2) | U1-U4 | Test set of follow-ups vs. people-to-people messages: follow-ups answered; Max stays quiet on ≥ 98% of messages not meant for it |

### 4.3 Meetings
| ID | Requirement | Use cases | Acceptance |
|---|---|---|---|
| M-1 | Brief 15 min before a meeting: agenda, last meeting's open items, related files | U7 | Brief appears on time with correct open items |

**26 Nov 2026 (Karthi):** meetings became a separate module, **Max Meeting** (`meeting/01-overview.md`), paused until the
chat Max is done. Chat R1 keeps only **M-1 (brief, from the calendar)**; M-2…M-6 and R-13 move to Max Meeting.
| M-2 | **→ Max Meeting module (paused, after chat R1).** Notice "Max is taking notes" + "pause notes" | U30 | See R-13 |
| M-3 | **→ Max Meeting module (paused, after chat R1).** Live text mode: "Max, …" questions answered in meeting chat; "what did I miss?" for late joiners | U8 U28 | Answer in meeting chat within 15 s |
| M-4 | **→ Max Meeting module (paused, after chat R1).** After the meeting: notes (summary, decisions, action items, risks) posted automatically | U5 | Notes within 2 min of the transcript arriving |
| M-5 | **→ Max Meeting module (paused, after chat R1).** Owners confirm action items: Accept / Change date / Not mine | U24 | Confirmed tasks appear in the plan |
| M-6 | **→ Max Meeting module (paused, after chat R1).** Review before notes become team knowledge; "forget this part" | U29 | Rejected or forgotten parts never appear in search |

### 4.4 Plans, tasks, reminders
| ID | Requirement | Use cases | Acceptance |
|---|---|---|---|
| P-1 | Tasks from action items (organizer approves the batch) | U9 | One card creates all approved tasks |
| P-2 | **Living plan card** in the channel, edited in place, with Done / New date / Blocked buttons | U17 | Button click updates the same card for everyone |
| P-3 | **Plans tab**: all plans, owners, dates, late items | U17 | Tab matches the database |
| P-4 | Chasing: day before due, morning after, private note to plan owner at 2 days late; never public | U10 U17 | Clock tests follow the exact schedule and limits |
| P-5 | Timers set by people: "in 10 min", "at 3 AM", "every Monday 9:00"; Max repeats the time back with time zone; survives restarts | U16 | Timer fires within 1 min of target, also after a restart |
| P-6 | Weekly digest Monday 9:00 in the channel (optional reviewer setting) | U25 | Digest lists decisions, done, late, coming up |

### 4.5 Email and meetings (moved from R2 to R1 by Karthi, 26 Nov 2026)
| ID | Requirement | Use cases | Acceptance |
|---|---|---|---|
| E-1 | "Email Sarah the pricing summary": Max writes the email, the approval card shows exactly what will be sent, sent from Max's mailbox only after approval | U11 | Nothing is sent without approval; the sent email matches the card exactly |
| E-2 | Follow-up email to attendees after a meeting, as a draft for approval | U26 | Draft lists decisions + action items with sources; sent only after approval |
| E-3 | Book or cancel a meeting: Max finds free time, proposes slots, books after approval | U12 | Booked meeting has the right people, time (with time zone) and agenda; cancel needs approval |

Needs extra Microsoft permissions in a real tenant (send mail, read/write calendars): asked for **in the one-time
install**, together with everything else. In the simulated Teams they work from day one.

### 4.6 Setup and control
| ID | Requirement | Use cases | Acceptance |
|---|---|---|---|
| S-1 | First-run setup page: time zone (JST), working hours, approvers, levels, limits, digest, notes review | setup | Changing a setting changes behaviour without restart |
| S-2 | Stop button on running tasks | R-5 | See R-5 |

## 5. Features: R2 (after R1)
U4 who-knows · U13 upload files · U14 explain what Max did · U19/U40 web
research (Tavily) · U27/U37 my day · U31 goal to plan · U33 other languages · U34 note templates
· U35 ask privately + share · U36 promises in posts · U39 editable memory · U41 plan preview · U42 undo ·
U43 snooze/mute · U44 command menu · U45 link briefs · `make_document` and `ask_agent` stubs · OCR pipeline.

## 6. Quality targets

| Area | Target |
|---|---|
| Speed (chat) | "Working on it" within 2 s; answer p50 ≤ 8 s, p95 ≤ 20 s; hard limit 60 s then a clear message |
| Speed (meeting) | In-meeting answer ≤ 15 s; notes ≤ 2 min after transcript |
| Accuracy | Test set: right source in top 8 ≥ 90%; answers correct ≥ 85%; numbers exact |
| Cost | ≤ $0.01 per question on average; full end-to-end run ≤ $0.20; daily cap $1 |
| Reliability | Main model fails → backup answers; both fail → clear message; the full end-to-end run passes 3 times in a row without a failure |
| Security | Keys only in `.env`; never in logs; L3/L4 enforced in code, not only in the prompt |
| Tests | Offline tests for every rule (free); end-to-end test in the browser; one command each |

## 7. Not in R1 (parked or later)
Routines (U38), memory design, Max per channel vs. "Max Personal", third-party integrations (MCP, no Microsoft Planner,
Jira, Notion), Document Agent (U18), charts (U22), agent-to-agent (U21), live voice, real Teams tenant, OCR.
R1 must not block them: tools are plain functions behind interfaces; the agent framework stays in one file.

## 8. Answers (25 Nov 2026)
R1 scope OK · quality targets OK · step limits per task type instead of one fixed number.
