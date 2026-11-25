# Max: use cases, tools and control

**Status: DRAFT 1, for discussion with Karthi.** Nothing here is final. Add, remove, re-rank.

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

## 3. Use cases (draft)

Priority: **M** = must have for the demo · **S** = should have · **L** = later

| ID | Use case | Trigger | Example | Tools | Level | Pri |
|---|---|---|---|---|---|---|
| U1 | Answer a question from team knowledge | @mention | "What did we decide about memory prices?" | search_knowledge, read_thread, read_file, get_transcript | L1→L2 | M |
| U2 | Catch me up / summarise a thread | @mention | "What did I miss this week?" | list_recent, read_thread | L1→L2 | M |
| U3 | Answer from a document | @mention | "What's the H1 target in the budget file?" | search_knowledge, read_file | L1→L2 | M |
| U4 | Who knows / who owns what | @mention | "Who's handling the GPU tender?" | list_people, search_knowledge | L1→L2 | S |
| U5 | Meeting notes after a meeting | Meeting ended + transcript | Summary, decisions, action items, risks | get_transcript, post_message, propose_tasks | L2 | M |
| U6 | Recall past meetings | @mention | "What did Prince say about the budget last time?" | search_knowledge, get_transcript | L1→L2 | M |
| U7 | Meeting brief before a meeting | Schedule (15 min before) | Agenda, open items, related files | get_calendar, search_knowledge, list_tasks, post_message | L2 | S |
| U8 | Answer during a live meeting (text first, voice later) | In-meeting call | "Max, what was Q1 revenue?" | Same as U1 + post_meeting_chat / speak | L2 | S (text) / L (voice) |
| U9 | Turn action items into tasks | After U5 | "Daniel: send forecast by Fri" becomes a task | create_task | L3 (one card for all) | S |
| U10 | Reminders and chasing | Schedule | Due tomorrow, overdue | list_tasks, post_message | L2 (with frequency limits) | S |
| U11 | Send an email | @mention | "Email Sarah the pricing summary" | draft_email, send_email | L3 | S |
| U12 | Book or cancel a meeting | @mention | "Set up 30 min with Jacob next week" | find_free_time, create_meeting, cancel_meeting | L3 | S |
| U13 | Share or upload a file | @mention / after U5 | "Post the notes as a Word file" | upload_file | L3 | L |
| U14 | Explain what Max did | @mention | "Why did you send that email?" | read_audit | L1→L2 | L |
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

No-tool functions: greetings, thanks, rewriting or summarising text pasted into the message, asking a
clarifying question, refusing L4 requests.

## 5. Open questions for Karthi
1. Which use cases are missing? (Think: what would make your managers say "I want this".)
2. Is the priority (M / S / L) right for the first demo?
3. Are the control levels right? E.g. should creating tasks (U9) need approval, or be automatic?
4. Who may approve L3 actions: only the person who asked, or also the team owner?
5. Should Max ever start a conversation on its own (reminders, risk alerts), or only answer?
