# Max: memory design

**Status: AGREED (26 Nov 2026), all 6 parts.** Research: `docs/research/memory-*.md`.
**Pictures:** `pictures/memory-stories.excalidraw` (4 simple story pictures for anyone; quick view `pictures/memory-stories-preview.png`)
and `pictures/memory.excalidraw` (the whole design on one page; quick view `pictures/memory-preview.png`).

## Agreed so far

### Thread memory: long threads and chats (thousands of messages)
Max never reads a whole long thread. Three layers:
| Layer | What Max gets | Size |
|---|---|---|
| Recent | Last ~20 messages, word for word | Small |
| Rolling summary | Short summary of everything older, updated every ~50 new messages | ~1 page, whatever the length |
| Search | "Search this thread for X" finds exact old messages when needed | Only what's asked |
Matters most for 1:1 and group chats (one endless thread).

### Facts about people: flexible, evidence-based (not a hierarchy)
| | Permissions (RBAC) | Facts about people (memory) |
|---|---|---|
| What | Who may approve/do what | Who handles what, preferences |
| Changes by | Admin, in setup | Learned from evidence, each fact with a date and a source |
| Strict? | Yes (safety) | No: newer evidence wins, old facts fade; people can see and correct them |
Permissions stay small: a few roles, only for approvals.

### Part 1: working memory and compaction (agreed 25 Nov 2026)
- Clean-up by code when the AI's input passes **40k tokens**: old tool results become one-line stubs with their ids
  (last 3 kept in full). Over **120k**: AI summary of old steps (~$0.01). Over **200k**: Continue card. All settings.
- A **notepad** (plan + findings, one line each with source ids, max ~2k tokens) is added to every call in long tasks; never cut.
- Never dropped: the request, the situation, actions/approvals/denials, every source id seen (`run_sources` table).
- Total memory cost about $0.05-0.10 per day; plain code + SQLite, no memory framework.

### Part 2: thread memory (agreed 25 Nov 2026)
- Summary is **added to / edited, never rewritten** (avoids "summary drift"). Background job every ~50 new messages.
- Fixed sections: Topic · Decisions · Open questions · Action items · Key facts; every line has its source message ids.
- AI only proposes add / update / close; max ~1,000 tokens; **rebuilt fresh every 20 updates** from the raw messages.
- Summaries **only for threads/chats where Max is active** (Max is planned separately per chat); search covers the rest.
- People can **see and correct** "what Max remembers about this thread".

### Part 3: facts about people (agreed 25 Nov 2026) — in R1, not later
- Work facts only (handles/owns, expertise, preferences, decisions, commitments). Never mood, health, private life, performance judgements.
- Learned nightly + after meeting notes are approved. The AI only **proposes**; code adds a fact or **closes** the old one (never overwrites, never AI-deletes).
- Each fact: valid from / valid until, source message ids, confidence (high/medium/low).
- A fact is as private as its most private source; 1:1 facts stay private, with an **"OK to share"** button.
- Ageing: not seen 120 days → shown "as of <date>"; one-off facts deleted after 180 days; person left → removed after 30 days.
- "What do you know about me?" card with Correct / Delete; a deleted fact leaves a marker so it isn't re-learned.
- Who may see/correct which facts: **a setting** (default: own facts + team facts they're part of).
- A small people card (people in this conversation) goes in every request; the rest via a tool. ~$0.01-0.05/day.

### Rule: friendly in chat, but remembers work only (Karthi, 25 Nov 2026)
Max may be in chats that also contain personal talk. Max can be friendly, casual and flexible in conversation,
and does precise work when it's about work. But **only work content goes into memory**: thread summaries,
people facts, lessons and decisions skip anything not related to work (the extraction step judges "work or not";
when unsure, it's skipped). Whether personal messages are kept out of the RAG search index too is decided in the RAG session.

### Part 4: episodic memory (agreed 25 Nov 2026)
- A **run card** per run, made by code (free): who asked, task, tools used, answer + sources, outcome (👍/👎/approved/denied/corrected).
- **Lessons only from people** (👎 with a reason, or a correction), never written by Max about itself (2026 studies: self-written lessons make agents worse).
- A lesson becomes active after the **team lead** clicks Accept; the **team lead's own lessons are accepted automatically**. Max 3 relevant lessons per run.
- Run cards kept **60 days**; active lessons stay until removed.

### Part 5: forgetting (agreed 25 Nov 2026)
| Trigger | What Max does |
|---|---|
| Message deleted in Teams | Removed from search, summaries, facts; an empty marker stays so it isn't re-learned |
| "Forget this part" (meeting) / "forget this" (chat) | Same as a delete, for that part |
| Person deletes a fact | Removed + marker |
| Age | Run cards 60 days; one-off facts 180 days |
| Person leaves the team | Their personal memory (preferences, 1:1 facts) deleted after 30 days; their work (posts, decisions, files) stays with the team |
People can see what Max keeps about them and correct/delete it (in chat; no download feature). Deletions are audited.
Max forgets in its own memory only; Teams messages follow the company's Teams retention.

### Part 6: Max Personal / scope (PROPOSED 25 Nov 2026, waiting for Karthi's answers)
Concern (Karthi): the system can't be designed for one person. Some people are in one team, some in many, people move.
- Confusion only exists in the **1:1 chat**. In a team channel/group chat Max is automatically that team's Max.
- Rejected: separate bots per team (max_planning, max_ads): each needs its own Entra app registration (more IT admin
  work), names to remember, manual add/remove when people move, no cross-team questions.
- Proposed: **one Max**. Team decided by where you talk. In the 1:1 chat ("Max Personal") Max sees only the teams the
  person is in **right now** (membership read live from Teams, so moves need no setup), labels sources by team,
  and can be focused with a word ("planning: ...") and/or a "Working in: Planning ▾" menu.
- Team memory stays with the team; personal memory (preferences, own reminders, own tasks) follows the person.
- Open questions: (1) does this remove the confusion? (2) focus by typed word, menu, or both (proposed: both)?
  (3) group chats with people from different teams / shared channels: proposed = only what everyone there may see
  (already rule R-8).
- **Agreed by Karthi (25 Nov 2026, later session):**
  - (1) Yes: one Max (one bot, one program; memory split per team and per person). Max Personal = the person's
    private 1:1 chat with Max. No "@Max" needed there (every message in the 1:1 chat goes to Max).
  - (2) Focus = **both** typed word and menu, plus **automatic choice**: a general question ("what work is
    pending?") gathers from all the person's teams, labelled by team; a question clearly about one team uses that
    team; the person can switch by just saying so in chat ("only Ads", "all teams"). When Max is unsure it uses
    all teams and labels them (never guesses silently). Every answer shows which team(s) it used.
    No separate router agent: the team is just a filter on the search tools, chosen in the same model call.
  - (3) Mixed-team group chats / shared channels: **agreed (26 Nov 2026)**: Max uses only what **everyone** in that
    chat may see (rule R-8). If that blocks an answer, Max says so and offers to answer in the person's 1:1 chat.

## To discuss (after research)
1. Working memory and compaction inside a run
2. Thread memory details (summary updates, what goes in)
3. Facts about people and the team (how learned, stored, corrected)
4. Episodic memory (what Max did before, used next time)
5. Forgetting and privacy (deletes, "forget this", retention)
6. Max Personal (per person vs per team memory) — Karthi's idea
