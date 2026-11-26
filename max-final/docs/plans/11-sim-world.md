# Max: the simulated team world + test set (topic 9)

**Status: ✅ AGREED (26 Nov 2026), Parts 1-4; Part 5 later.** The world lives in `world/` (Max never reads it directly; it
reaches Max only through the simulated Teams and its fake Microsoft cloud). R1 size (agreed 25 Nov): about 4 people
Karthi can play, in 1-2 teams. Testing design: `07-rag.md` Decision 4.

| # | Part | Status |
|---|---|---|
| 1 | The company and the people (teams, chats, who can be played) | ✅ Agreed (26 Nov) |
| 2 | The story: 30+ days of work, files, plans, decisions, planted facts | ✅ Agreed (26 Nov) |
| 3 | How the world is made and kept (generated once, reviewed, plain files, repeatable) | ✅ Agreed (26 Nov) |
| 4 | The test set (~250 questions, 11 types, canaries, follow-ups) | ✅ Agreed (26 Nov) |
| 5 | Scale test (a big generated team, for speed and cost) | ⏸️ Later: after the project is finished (Karthi, 26 Nov) |

## Part 1: the company and the people (AGREED 26 Nov 2026, Karthi's company, people and departments)
**Company (Karthi, 26 Nov): Thirdwave**, a PC manufacturer (like HP, Dell). Products, models and figures in the
world are invented (no real product data). **People (Karthi): Karthi, Prince, Praga, Rachitaa** (all four playable).
**Places (Karthi): real working departments**, not invented project teams.

Roles (agreed):
| Person | Department / role | Why this person |
|---|---|---|
| Prince | Product Planning: **department lead** | Approves, reviews, gets lessons and alerts |
| Praga | Procurement: parts buyer (CPU, GPU, memory, SSD) | Owns late tasks: chases, Blocked, supplier prices |
| Rachitaa | Sales: account manager, **also in Product Planning** | In 2 departments: Max picks the right one in 1:1 |
| Karthi | IT / AI: Max's developer and admin, member of Product Planning | Settings, health view, alerts |

Departments (Teams teams) with history (agreed):
| Team (department) | Channels | Members | Tests |
|---|---|---|---|
| **Product Planning** | General, New models, Pricing | Prince, Rachitaa, Karthi + background | Plans, decisions, spec files, launch dates |
| **Procurement** | General, Suppliers | Praga + background | Parts prices in sheets, supplier contracts, numbers by code |
| **Sales** | General, Big accounts | Rachitaa + background | A second team; privacy between departments |
| Private channel Product Planning › **Budget** | — | Prince, Karthi | Private info must never reach Rachitaa |
| Group chat **"New model sync"** | — | Prince, Praga, Rachitaa | Mixed departments: only what everyone there may see |
| 1:1 chats with Max | — | each person | Max Personal, private memory, approvals |
Other departments (Production, Quality, Support, Marketing, Finance) exist as names and background people only.
Background people (history only) get invented names; one outside supplier contact tests "email inside only".

## Part 2: the story (AGREED 26 Nov 2026)
**Time:** history covers the last ~45 days: 30 days inside Max's default window + ~15 older days (tests the
"knowledge horizon"). All products, prices and customers are invented.

**5 storylines** (each crosses departments, so answers need several sources):
| # | Storyline | Where | What it tests |
|---|---|---|---|
| 1 | **New model launch** (an invented gaming desktop): launch date decided, later **moved** | Product Planning, group chat | Old vs new decision, "as of", plan card, late tasks |
| 2 | **Memory price rise**: monthly parts prices in a sheet, supplier quotes → decision to raise PC prices | Procurement, Pricing | Numbers by code (sums, % change), decisions |
| 3 | **GPU supplier choice**: two suppliers compared; budget talk only in the private Budget channel | Procurement, Budget | Privacy: secret code name + budget figure must never leak |
| 4 | **Big customer order** (an invented company, 300 units) depending on the launch date | Sales | Cross-department answers, a second team |
| 5 | **Everyday life**: small talk, lunch plans, a personal message, a blocked task, a new idea | everywhere | Work-only memory, follow-ups, chases |

**Files (~40), mix set by Karthi (26 Nov):** fewer Word, more PowerPoint and Excel, every kind of PDF:
| Kind | Count | Inside |
|---|---|---|
| Excel | ~12 | Price sheets with several sheets, supplier quotes, order lists, budgets |
| PowerPoint | ~12 | Launch and review decks; **several with chart and graph images** (tests AI vision) |
| PDF | 8 = **2 of each kind** | text PDF · scanned PDF (OCR) · PDF with tables · PDF with chart images |
| Word | ~5 | Specs, minutes, a policy; one very long |
| Images | ~3 | Whiteboard photo, chart screenshot, product photo |
**Old and new versions: 3 cases** (e.g. a price sheet, a deck, a spec), each with a changed number or date. **Plans:** a launch plan with ~9 tasks (some done, some late, one blocked). **Calendar:** ~10
meetings (past and coming). **Messages:** ~1,500 (threads, replies, group and 1:1 chats).

**Planted facts:** ~120 facts with the exact answer and where it lives (e.g. a part price in a given sheet, row and
month). Plus **traps**: a decision changed later, two similar files, an outdated version, a number that exists only as
a sum of rows, facts older than the window, a personal message Max must not remember, and **canary words** that may
appear only in the private channel. Each fact and trap feeds the test set (Part 4).

## Part 3: how the world is made and kept (AGREED 26 Nov 2026)
**Review (Karthi):** the fact sheet **plus sample messages and files** (about 50 messages across all places and
1-2 files of every kind), before the full world is generated.
1. **Facts first:** a fact sheet (plain YAML) with the storylines, people, dates, decisions and every planted fact +
   trap. Karthi reviews **this** (short), not 1,500 messages.
2. **Numbers by code:** all figures (prices, sums, quantities) come from the fact sheet and are written by code, so
   they are exact. The AI only writes the human text (messages, document prose) around the facts.
3. **Real files:** Excel (openpyxl), PowerPoint (python-pptx, charts drawn as images), Word (python-docx), PDF (text,
   tables, chart images; "scanned" = page turned into an image with slight noise), images (charts, a whiteboard photo).
4. **Checked by code:** every planted fact must be findable in exactly the place the fact sheet says; canary words
   only in the private channel; no real company data.
5. **Plain files in `world/`, in git** (small), made once with a fixed seed: the same world every time.
   Regenerated only on purpose. One-time AI cost: about $1-3.
6. **Loaded into the simulated Teams** through the fake Microsoft cloud. **Dates slide**: the history always ends
   "today", so the 30-day window and "last week" questions keep working on any day.
7. **Reset button** in the simulated Teams: back to the clean world (whatever Karthi typed while playing is dropped).

## Part 4: the test set (AGREED 26 Nov 2026)
Built from the planted facts (we know every right answer and where it lives). The AI drafts 2-3 wordings per fact.
**Review (Karthi, 26 Nov: not every question):** the right answers are already checked through the fact sheet; code
checks each answer really is at its labelled place; a second AI reviewer checks each question is clear and has one
right answer; **Karthi spot-checks ~25 questions plus any the AI reviewer flags**. Sources are labelled by item (thread, file + sheet/page/slide), so changing how
pieces are cut doesn't break tests. Start with ~120, grow to ~250 before R1; every bug found becomes a new question.

**A. Knowledge questions (~250, 11 types).** Meeting-transcript questions moved to Max Meeting; replaced by files:
| Type | Example | Count |
|---|---|---|
| Exact fact | "What's the order number for the big customer?" | 30 |
| Same meaning, other words | "What did we settle on for the cost cut?" (post says "price reduction") | 30 |
| Number from Excel (incl. sums, % change) | "Total memory cost in October?" | 25 |
| From slides, chart images, scanned PDFs | "What does the launch deck chart show for week 3?" | 25 |
| Two sources (chat + file) | "Does the price sheet match what we decided on Tuesday?" | 25 |
| Latest / changed over time | "What's the **current** launch date?" | 20 |
| Edited content | Must use the new text, never the old | 15 |
| Deleted content | Must not appear at all | 15 |
| Private, asker not allowed | Must not leak (plus the automatic canary sweep) | 30 |
| Not in the data / older than the window | Must say so, not guess | 20 |
| Follow-up | "And who owns that?" | 15 |

**B. Behaviour scenarios (~60 scripted conversations)** for the non-knowledge features: approvals (email, meeting,
tasks), reminders and jobs, follow-ups without @Max (answered vs. must stay quiet), memory requests, refusals, Stop
and Continue, chases and "Stop these", cards updating in place.

**Targets** (from `07-rag.md` / requirements): right source in top 8 ≥ 90% · answers correct ≥ 85% · numbers 100%
exact · leaks **0** · correct "I don't know" ≥ 90% · wrong refusals ≤ 5% · Max quiet on ≥ 98% of messages not for it.

## Part 5: scale test (LATER: after the project is finished, Karthi 26 Nov 2026; design kept here)
A separate, **big** team made by code from templates (no AI, free, not reviewed): ~100,000 messages over a year,
~2,000 files, ~20 channels and chats. Not for accuracy, only to measure speed and cost at company size.
| Measure | Target (starting values, settings) |
|---|---|
| First read of a 30-day window (~8,000 messages + files) | minutes, not hours; under ~$1 |
| Search speed on 100k messages | under ~0.3 s for the search step |
| Live update (new post searchable) | within 30 s (RAG Part 2) |
| Nightly compare | well under 10 minutes |
| Database size and memory use | recorded, so we know what a server needs |
Run on demand (not on every `run.py test`), on the stronger machine or a server.
