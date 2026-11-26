# Max: use cases, tools and control

**Status: AGREED (25 Nov 2026).** Parked topics in section 11 get their own planning later. Nothing here is final. Add, remove, re-rank.

Order of work: use cases → tool table → control levels + triggers → requirements → agent loop design
→ tool interfaces → connect tools to the fake Teams (the agent only sees the interfaces).

## 1. Control levels (Max is semi-autonomous)

| Level | Meaning | Example |
|---|---|---|
| **L0** No tool | Answer from the message itself | Greeting, rewrite pasted text, ask a clarifying question |
| **L1** Read | Read team data. Automatic, logged | Search posts, read a file |
| **L2** Safe write | Write only in Max's own space (a reply in the thread where it was asked, its own task list). Automatic, logged | Reply to an @Max question |
| **L3** Needs approval | Anything that leaves the thread or can't be undone. Approval card first | Send email, book a meeting, upload a file |
| **L4** Never | Max refuses, whoever asks | Delete data, message outside the company, change permissions |

## 2. Triggers (what starts Max)

| Trigger | Example |
|---|---|
| **@mention** | "@Max what did we decide on pricing?" |
| **Meeting event** | Meeting started, ended, transcript ready |
| **In-meeting call** | "Max, what was the Q1 number?" |
| **Schedule** | 15 min before a meeting, 9:00 daily reminders |
| **Card click** | Someone approves or denies an action |
| **Timer set by a person** | "Remind me in 10 minutes to send this", "At 3 AM remind me of X", "Every Monday 9:00 post the status" |
| **Plan / deadline** | A task's due date passes without an update |
| *(more later)* | e.g. a new file uploaded, a keyword in the channel |

## 3. Use cases (draft)

Priority: **M** = must have for R1 (first release) · **S** = should have · **L** = later

| ID | Use case | Trigger | Example | Tools | Level | Pri |
|---|---|---|---|---|---|---|
| U1 | Answer a question from team knowledge | @mention | "What did we decide about memory prices?" | search_knowledge, read_thread, read_file, get_transcript | L1→L2 | M |
| U2 | Catch me up / summarise a thread | @mention | "What did I miss this week?" | list_recent, read_thread | L1→L2 | M |
| U3 | Answer from a document | @mention | "What's the H1 target in the budget file?" | search_knowledge, read_file | L1→L2 | M |
| U4 | Who knows / who owns what | @mention | "Who's handling the GPU tender?" | list_people, search_knowledge | L1→L2 | S |
| U5 | Meeting notes after a meeting | Meeting ended + transcript | Summary, decisions, action items, risks | get_transcript, post_message, propose_tasks | L2 | M |
| U6 | Recall past meetings | @mention | "What did Prince say about the budget last time?" | search_knowledge, get_transcript | L1→L2 | M |
| U7 | Meeting brief before a meeting (with last meeting's open items) | Schedule (15 min before) | Agenda, open items, related files | get_calendar, search_knowledge, list_tasks, post_message | L2 | M |
| U8 | Answer during a live meeting (text first, voice later) | In-meeting call | "Max, what was Q1 revenue?" | Same as U1 + post_meeting_chat / speak | L2 | S (text) / L (voice) |
| U9 | Turn action items into tasks | After U5 | "Daniel: send forecast by Fri" becomes a task | create_task | L3 (one card for all) | S |
| U10 | Reminders and chasing | Schedule | Due tomorrow, overdue | list_tasks, post_message | L2 (with frequency limits) | S |
| U11 | Send an email | @mention | "Email Sarah the pricing summary" | draft_email, send_email | L3 | S |
| U12 | Book or cancel a meeting | @mention | "Set up 30 min with Jacob next week" | find_free_time, create_meeting, cancel_meeting | L3 | S |
| U13 | Share or upload a file | @mention / after U5 | "Post the notes as a Word file" | upload_file | L3 | L |
| U14 | Explain what Max did | @mention | "Why did you send that email?" | read_audit | L1→L2 | S |
| U16 | Timers and scheduled jobs set by people | @mention | "Remind me at 3 AM to call Tokyo", "In 10 min send this reminder" | schedule_job, list_jobs, cancel_job | L2 (own reminders) / L3 (messages to others) | M |
| U17 | Follow a plan and chase updates | Plan / deadline + schedule | Max tracks a meeting plan, asks owners for updates, flags missed deadlines | list_tasks, post_message, update_task | L2 | S |
| U18 | Create and edit files (PowerPoint, Excel, Word, PDF) in a house style; asks for missing details | @mention | "Make a 5-slide deck on the Q1 results", then "remove slide 3" | make_document (stub now; a separate Document Agent later) | L2 (draft) / L3 (upload to team files) | L (separate project) |
| U19 | Internet research | @mention | "What are DRAM prices doing this month?" | web_search, read_web_page | L1 | S |
| U20 | Work in other apps (Slack, Notion, ...) | @mention | "Add this to the Notion page" | MCP connectors | per tool | L |
| U21 | Talk to other agents (e.g. a future automation agent) | @mention / event | "Ask the automation agent to run the weekly report" | ask_agent (placeholder) | L3 | L |
| U22 | Charts and visuals | @mention | "Show sales by month as a chart" | make_chart | L1→L2 | L |
| U23 | Decisions log: every decision with date, owner, source link | Meeting ended / @mention | "What have we decided about pricing since October?" | search_knowledge, record_decision | L2 | M |
| U24 | Owners confirm their action items (Accept / change date / not mine) | After U5 | Fixes wrong-owner mistakes | post_message (card) | L2 | M |
| U25 | Weekly status digest | Schedule (e.g. Monday 9:00) | Decisions, done, late, coming up | list_tasks, search_knowledge, post_message | L2 | M |
| U26 | Follow-up email draft after a meeting | After U5 | Draft to attendees, sent only after approval | draft_email, send_email | L3 | S |
| U27 | "My day" private message | Schedule | My meetings, my tasks due, mentions | get_calendar, list_tasks | L2 | S |
| U15 | Small talk, clarify, refuse | @mention | "Thanks!", unclear request, forbidden request | none | L0 / L4 | M |

## 4. Tool table (which use cases share which tool)

| Tool | What it does | Level | Used by |
|---|---|---|---|
| search_knowledge | Keyword search over posts, replies, files, meetings | L1 | U1 U3 U4 U6 U7 U8 |
| read_thread | Full thread (post + replies) | L1 | U1 U2 |
| list_recent | Posts and replies since a date | L1 | U2 |
| read_file | Text of one file (or a section) | L1 | U1 U3 |
| get_transcript | A meeting transcript (or a part of it) | L1 | U1 U5 U6 |
| list_people | Team members and roles | L1 | U4 |
| get_calendar / find_free_time | Meetings and free slots | L1 | U7 U12 |
| list_tasks | Tasks with owner and due date | L1 | U7 U10 |
| read_audit | What Max did and why | L1 | U14 |
| post_message | Reply in the current thread / meeting chat | L2 | U5 U7 U10 (U1-U4 answers) |
| propose_tasks / create_task | Tasks from action items | L3 | U9 |
| draft_email / send_email | Email from Max's mailbox | L3 | U11 |
| create_meeting / cancel_meeting | Book or cancel meetings | L3 | U12 |
| upload_file | Put a file in the team's files | L3 | U13 |
| speak | Say an answer in a live meeting | L2 | U8 (voice, later) |
| schedule_job / list_jobs / cancel_job | Timers and repeating jobs | L2/L3 | U10 U16 U17 |
| files.create / files.edit / files.read | Make and change pptx, xlsx, docx, pdf from templates | L2 | U18 |
| web_search / read_web_page | Internet research | L1 | U19 |
| mcp.* | Tools from other apps through MCP | per tool | U20 |
| ask_agent | Send a request to another agent (placeholder for now) | L3 | U21 |
| make_chart | Chart image or chart inside a file | L2 | U22 |

No-tool functions: greetings, thanks, rewriting or summarising text pasted into the message, asking a
clarifying question, refusing L4 requests.

## 5. Karthi's answers (25 Nov 2026)
| Question | Answer |
|---|---|
| Missing use cases | Research what AI teammates offer; added U16-U22 |
| Priorities | OK |
| Control levels | To discuss |
| Who approves L3 | To decide |
| Max starts conversations? | Both: depends on the situation (reminders, plan follow-up yes) |
| Avatar | Orange cloud for now; richer animations later |

## 6. How Max reads a big team (research: `docs/research/knowledge.md`)
> **Replaced by `docs/plans/07-rag.md` (agreed 26 Nov 2026):** keyword + meaning search from R1, re-rank to the best 8,
> answer checks, ~250-question test set. The text below is the earlier first idea, kept for history.

**Search first, then open only what is needed.** Never send everything to the AI.
1. `search_knowledge(query, filters)` → about 8 short snippets with ids and sources (keyword search, SQLite FTS5).
2. The agent opens only what it needs: `read_thread`, `read_file(section)`, `get_transcript(time range)`.
   Files under ~30k tokens go whole (about $0.008); bigger ones section by section.
3. Every answer cites its sources (thread, file section, transcript moment).
4. Search only returns content that **everyone who will see the answer** may see (filter inside the database query).
Meaning search (embeddings) is added only if a 40-question test shows keyword search misses things.
Cost: about $0.005-0.01 per question; first import of a big team (10k posts, 300 files, 50 meetings) under $1.20.

## 7. Decisions (Karthi, 25 Nov 2026)
| Topic | Decision |
|---|---|
| Meaning search | Keyword first. `gemini-embedding-2` is allowed (Karthi, 25 Nov): added if the 40-question test shows it makes answers better |
| Short summary of each file/meeting at import | Yes (about $0.50 for a big team) |
| Internet search | **Tavily** for now |
| Who approves | **Configurable in setup.** Default: requester approves actions for themselves; organizer approves the task batch from a meeting; each owner confirms their own task; admin sets which tools are L3/L4 |
| Meeting notes | Posted automatically, with owner-confirm buttons on action items |
| Chasing | Reminder messages from Max's account (a notification, not a conversation): one the day before the due date, one the morning after; at 2 days late a private note to the plan owner; never in public. Extend later. |
| Message limits | **Configurable in setup** (default: one chase per task per day, max 3 private messages per person per day) |
| Working hours | **9:00-18:00 JST** (team time zone: Asia/Tokyo). No separate "quiet hours". Max's own automatic messages and the meetings it books stay inside working hours. Reminders a person sets ("at 3 AM remind me") fire at the exact time asked. |
| Weekly digest | Monday 9:00 in the team channel |
| Document maker | **A separate Document Agent, built later.** Now: a stub tool `make_document` with a fixed input/output, so the agent loop and approvals can be tested end to end. |
| Timers | Our own SQLite jobs table + one loop; Max repeats the time back with the time zone |
| Charts | Later. matplotlib images in chat; native charts inside pptx/xlsx |
| Other apps / agents | MCP with an allowlist and approval before any write; `ask_agent()` placeholder (A2A later) |

## 8. First-run setup (when Max is installed in a team)
An admin page/card, saved in the database, changeable later:
| Setting | Default |
|---|---|
| Team time zone, working hours | Asia/Tokyo (JST) · 9:00-18:00 |
| Who approves each kind of action | As in section 7 |
| Which tools are L3 (approval) / L4 (never) | As in section 4 |
| Message limits per person per day | 3 |
| Chasing rules | Day before, morning after, plan owner at 2 days late |
| Weekly digest day, time, channel | Monday 9:00, team channel |
| Meeting notes | Auto-post with confirm buttons |

## 9. make_document stub (contract for the future Document Agent)
Input: `kind` (pptx/xlsx/docx/pdf), `request` (what the person asked), `template` (house style name),
`sources` (ids of threads/files/meetings to use), `edit_of` (file id, when changing an existing file).
Output, one of: `{"status": "done", "file_id", "name", "preview"}` · `{"status": "needs_info", "questions": [...]}`
· `{"status": "failed", "reason"}`. The stub returns realistic fake results so the loop can be tested.

## 10. Competitor gaps (research: `docs/research/competitors-meetings.md`, `competitors-workspace.md`)
33 products compared feature by feature. Proposed additions (**waiting for Karthi**):

### Built-in rules for every answer and action (not separate use cases)
| Rule | Who does it | Why |
|---|---|---|
| **Sources panel:** under each answer, a folded "How I got this" with the steps and the sources | Slack, Notion, Gemini | Makes trust visible |
| **Runaway guard:** step limit per run + daily spend cap; clear "stopped" message | Zapier, Notion, Glean, Copilot | A runaway loop wastes money and confuses people |
| **Hidden-instruction guard:** text from web pages, files, MCP results is data, never commands | All serious products | Safety |

### New use cases
| ID | Use case | Who has it | Effort | Proposed |
|---|---|---|---|---|
| U28 | "What did I miss?" during a live meeting (late joiner gets the summary so far) | Gemini, Facilitator, Zoom, Fathom, Fireflies | S | **Must** |
| U29 | Notes reviewed before they become team knowledge, plus "forget this part" | Microsoft channel agent (24 h review), Granola, Read | S | **Must** |
| U30 | A short "Max is taking notes" notice in meetings, plus a "pause notes" command | Gemini, Read, Zoom | S | **Must** (consent is the top legal complaint) |
| U31 | Goal to plan: "budget approved by 15 Jan" becomes steps, owners, dates (U17 then chases it) | Planner agent, Asana, Rovo | M | Should |
| U32 | Spreadsheet numbers calculated by code, never guessed by the AI | Copilot Analyst, ChatGPT | M | **Must** |
| U33 | Answers and notes in the reader's language (other languages besides English) | Teams recap, Gemini, Granola, Fireflies | S | Should (R1 is English) |
| U34 | Note templates per meeting type (forecast review, budget review, ...) | Avoma, Fireflies, Zoom, Gemini, Granola | S | Should |
| U35 | Ask Max privately, then a button to share the answer in the channel | Otter, Gemini in Meet, channel agent | S | Should |
| U36 | Spot deadlines and promises in channel posts, not only meetings | Microsoft channel agent | M | Should |
| U37 | "You were mentioned while away" (part of U27 "My day") | Facilitator | S | Should |
| U38 | Reusable routines: "save this as the monthly variance routine" | Notion, Glean, Dust, ChatGPT | M | Should |
| U39 | Team memory people can see and edit (within what each may see) | ChatGPT, Notion, Copilot | M | Should |
| U40 | Deep research report with sources (extends U19) | Copilot Researcher, ChatGPT, Gemini | M | Should |
| U41 | Plan preview: one approval for a multi-step action | Copilot, Rovo, Lindy | S-M | Should |
| U42 | Undo Max's last action or post | Notion, Zapier | S | Should |
| U43 | Snooze / mute Max per person and per channel | Slack, Read | S | Should |
| U44 | Starter prompts / command menu | Most products | S | Should |
| U45 | Link briefs: a shared link is read and saved as a short brief in the knowledge | Glean, Notion | S-M | Should |
| (U25) | Weekly digest: optional reviewer approves before it posts | Glean, Notion | S | Setting in first-run setup |

### Where Max is ahead
End-to-end polite chasing with buttons; owners confirming their action items; decisions log with sources.
Microsoft's channel agent is still in preview (one channel per agent, no private channels, needs a Copilot
license), and Microsoft dropped its plan to let Copilot Studio agents join meetings (Aug 2026), so Max in
meetings is a real difference.

## 11. Decisions round 2 (Karthi, 25 Nov 2026)
| Topic | Decision |
|---|---|
| Where people see plans | **Max's own views first**: a living plan card in the channel (Max edits it in place, with Done / New date / Blocked buttons) and a **Plans tab** in Teams. Max's database is the one source of truth. No Microsoft Planner (Karthi, 26 Nov: our own plans only). Jira / Notion export maybe later. |
| 3 rules + U28-U30 | Agreed |
| **Stop button (new rule)** | Every running Max task shows a **Stop** button. If Max was called by mistake, one click stops it: nothing more is sent, nothing half-done is left (pending actions cancelled). |
| Language (R1) | English |
| U32 spreadsheet math | Must |
| **Extractor pipeline (new)** | A separate, high-quality extraction pipeline for files: text, tables, slides, and **OCR** for scanned PDFs and images in slides/docs. Its own design step later. |
| **Links (new, U45)** | When someone shares a link, Max reads the page and stores a **short brief** (title, what it's about, key points) in the knowledge, so it can be found later. |
| U35 ask privately | Yes; extended later |
| Everything else | Good |

### Parked: planned separately later (don't design around them yet, but don't block them)
| Topic | Note |
|---|---|
| U38 reusable routines | Probably "saved steps + a trigger"; needs its own careful plan |
| Memory and how the agent uses it | Own design session |
| **Max per channel vs. a person in many teams; "Max Personal"** | Karthi has an idea. Same Max workflow, different connections. |
| Third-party integrations (MCP, Jira, Notion; no Microsoft Planner: Karthi 26 Nov, own plans only) | Own design session |
| Document Agent (U18), charts (U22), agent-to-agent (U21) | Stubs or later |
