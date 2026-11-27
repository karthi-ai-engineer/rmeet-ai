# Step 3 plan: Thirdwave's world (history, files, reset)

**Status: IN PROGRESS (27 Nov 2026).** Started on Karthi's go-ahead ("go to the next step in a new branch and keep
progressing"); design already agreed in `11-sim-world.md` (Parts 1-4). Branch: `step-3`. Build plan: `12-build-plan.md`.
**Review gate (agreed process, `11-sim-world.md` Part 3): Karthi reviews the fact sheet + samples before the full
world (~1,500 messages, AI-written, about $1-3) is generated.** Everything up to that gate is built and tested now.

## Goal
The simulated Teams opens on **Thirdwave's real-looking history**: 45 days of posts, replies and chats across the
departments, ~40 real files (Excel, PowerPoint, PDF, Word, images) in the channels' Files tabs, the planted facts
and traps the test set needs, and **dates that slide** so the history always ends "today". Reset = back to this world.

## What we build
| # | Piece | Where | What it does |
|---|---|---|---|
| 1 | **Fact sheet** | `world/facts.yaml` | Company, people (4 playable + background), places, 5 storylines, dated events, decisions (incl. changed ones), parts prices, the launch plan, meetings, **every planted fact + trap** with its exact answer and place, canary words. **Karthi reviews this** |
| 2 | **Samples** | `world/messages/samples.yaml` + sample files | ~50 messages across all places and 1-2 files of every kind, so Karthi sees the style before the full world is made |
| 3 | **File makers (numbers by code)** | `world/make/` | Excel (openpyxl), PowerPoint with chart images (python-pptx + matplotlib), Word (python-docx), PDF: text, tables, chart images, "scanned" (page image with noise) (reportlab + Pillow), images (chart screenshot, whiteboard photo). Every figure comes from the fact sheet. Fixed seed: same files every time |
| 4 | **Checks by code** | `world/check.py` | Every planted fact is findable exactly where the fact sheet says; canary words only in the private channel; old/new versions differ only where planned; no real company data |
| 5 | **Loader with sliding dates** | `teams_sim/cloud/world.py` | Loads messages and files into the simulated Teams through its store; day offsets + Tokyo times become real dates ending today. Reset loads the world |
| 6 | **Files for real** | `teams_sim/cloud/store.py` (files table), screens' Files tab | Files per channel with versions, who/when/size; list + download in the Files tab; background people shown by name |
| 7 | **Full world** (after the gate) | `world/make/messages.py` | AI writes the human text around the facts (cheapest model, cost visible in the usage meter, budget is a setting); checks run again |

## How we check it (tests first)
- **Offline tests:** fact sheet loads and is consistent (dates, people, places exist); each file maker writes a file
  that opens and contains its facts at the labelled place; checker catches a moved fact and a leaked canary; loader
  slides dates (history ends today, order kept, Tokyo times right); reset gives the same world twice; Files API
  respects private channels; Max still never reads `world/` (folder rule).
- **End to end:** start, open channels as each person: history and files visible, private files hidden from Rachitaa,
  reset works; Max still says hello. Browser tests (Playwright).
- **Review** by a separate reviewer, fixes + tests, docs.

## Open for Karthi (at the review gate)
1. Fact sheet: storylines, names, numbers, traps OK?
2. Samples: message style and file look OK?
3. Then: generate the full world (~$1-3 one time, cheapest Gemini model)?

## Progress (27 Nov 2026): everything up to the review gate is built and tested
| Piece | State |
|---|---|
| Fact sheet `world/facts.yaml` | ✅ Draft for review: 10 people (4 playable + 6 background) + 1 outside contact, 3 departments + private Budget, 4 chats, 5 storylines, 38 dated events, **77 planted facts** in all 11 types (more come with the full world, target ~120), 9 traps, canaries, 40 files (9 fully specified samples incl. all 3 old/new version cases) |
| Samples `world/messages/samples.yaml` | ✅ 55 messages (every event + everyday chatter), all 5 storylines, every place |
| File makers | ✅ Excel, PowerPoint with chart pictures, Word, PDF (text, table, chart, scanned), whiteboard photo. Same day = same bytes |
| Checks `python run.py world` | ✅ 77 facts proven at their labelled place, 0 pending, 0 problems; canary sweep over every message and file |
| Loader + reset | ✅ The simulated Teams starts from the world; dates slide (working days, Tokyo); history ends this morning; nothing from the future; edited / deleted history |
| Files for real | ✅ Files tab with versions, preview (images, PDF), download; private files closed to non-members; full names for everyone |
| Full world (AI-written, ~1,500 messages + the other 31 files) | ⏸️ **Waiting for Karthi's review** |

**Design decisions made while building (for Karthi to confirm at the review):**
1. **Files and dates are made at load time, not frozen in git.** git keeps the fact sheet and the message text with date
   placeholders; the loader makes the files and messages for today. Frozen files would contradict sliding dates
   (a file saying "due Mon 24 Nov" while the messages slide). Same day = exactly the same world.
2. **Dates count working days**, so the history never happens on a weekend.
3. **The reading window, checked by code:** facts Max must answer are at most 19 working days old (inside 30 calendar
   days on any weekday); "older than the window" facts are at least 24 working days old. Building this caught facts
   that would have been invisible to Max (e.g. the Northwind order at 25 working days ≈ 35 days).
4. **Praga is not in Product Planning** (as agreed), so Praga's pricing-channel items are posted by Prince
   ("Praga's new quotes…"); background people Aiko (Quality) and Lena (Finance) were added to Product Planning.

**Review pack for Karthi:** `world/facts.yaml` (start with `names`, `people`, `data`, `storylines`, `traps`),
`world/messages/samples.yaml`, pictures `docs/plans/pictures/world-sample-*.png` and `ui-18-step3-*.png`.
