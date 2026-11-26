# Max: build plan (topic 10)

**Status: ✅ AGREED (26 Nov 2026).** How we build is agreed in `CLAUDE.md` ("How we build"):
each step = one complete, visible feature; plan → tests first → build → review → end-to-end test → docs → Karthi
commits; one branch per step; never start the next step while one is half done. Each step gets its own
`step-N.md` (1-page plan) when we reach it.

| # | Part | Status |
|---|---|---|
| 1 | The order of the steps (big picture) + UI design step | ✅ Agreed (26 Nov) |
| 2 | What "done" means for R1 (release checklist) | ✅ Agreed (26 Nov) |

## Part 1: the order of the steps (AGREED 26 Nov 2026)
Design passes that were parked (card visuals, simulated Teams screens) happen **just before the step that needs
them**, not all up front.

| Step | What you can see at the end | Main pieces |
|---|---|---|
| 0 ✅ | `run.py test` passes; Gemini answers | Settings, logs, model client, database, cost meter (done 25 Nov) |
| 1 | Same as now, but **any model provider** can be plugged in; **all limits in one settings file** | Provider-neutral settings (`LLM_*`), OpenAI-compatible backend for company-server models, neutral usage meter, limits as settings |
| 2 | **Simulated Teams in the browser**: switch between Karthi / Prince / Praga / Rachitaa, departments, channels, chats; Max replies "hello" | Design pass for the simulated Teams screens first; fake Microsoft cloud with the real contracts (bot messages, channels, chats, files) |
| 3 | **Thirdwave's world** loaded: 45 days of history, ~40 files; reset button | Fact sheet + samples (Karthi reviews) → full world → loader with sliding dates |
| 4 | **Max reads everything** and keeps up to date; a search page shows what it finds | Knowledge import, extraction (Docling, OCR, AI vision), pieces, keyword + meaning search, live updates, nightly compare, health view |
| 5 | **"@Max what did we decide…?" → correct answer with sources** | Agent loop, reading tools, re-rank, answer checks, citations, 👍/👎; first ~120 test questions |
| 6 | **Cards work**: Stop, approvals, Continue, cards updating in place; follow-ups without @Max | Card visual design pass first; card engine; follow-up detection |
| 7 | **Max remembers**: thread summaries, "what do you know about me?", lessons | Memory (all 6 agreed parts) |
| 8 | **Plans and reminders**: decisions log, tasks, living plan card, chases, weekly digest, timers | Plans, jobs, workflows |
| 9 | **Email and meetings**: send email, book / cancel meetings, meeting brief with countdown | Simulated mailbox + calendar, approval cards |
| 10 | **Setup page** for the team lead: departments, approvers, working hours, limits | First-run setup (S-1), settings editable without restart |
| 11 | **R1 ready**: full ~250 questions + ~60 behaviour scenarios pass; 3 full end-to-end runs in a row | Hardening, fixes, docs |

After R1: **Max Meeting** module (paused design), scale test, the editable limits dashboard, R2 items.

**Karthi (26 Nov 2026): the complete UI must be designed clearly as part of the build plan.**
**Decided (26 Nov 2026): no Figma** (Karthi's Figma plan allows only ~6 design actions a month). Claude designs the UI
directly as **clickable mock-ups built with Fluent UI v9** (Microsoft's own component library used for Teams) with its
ready-made Teams themes. Karthi reviews in the browser and comments in chat. Approved mock-ups become the starting
point of the real screens (nothing redrawn). Details: `13-ui-design.md`.
- **One full UI design step before step 2** (all screens at once, so every later step builds to a finished design).
- **Cards** are Adaptive Cards (JSON) checked with Microsoft's own card renderer in the Teams look.

## Part 2: what "R1 done" means (AGREED 26 Nov 2026)
R1 is done only when **all** of these are true (numbers are starting values from `03-requirements.md`):
| Area | Check |
|---|---|
| Features | Every R1 requirement works end to end in the simulated Teams, played as the 4 people |
| Knowledge | ~250 test questions: right source in top 8 ≥ 90% · answers correct ≥ 85% · numbers 100% exact · honest "I don't know" ≥ 90% · wrong refusals ≤ 5% |
| Privacy | **0 leaks** (canary sweep over every question × every person) · stale / deleted text never shown |
| Behaviour | ~60 scripted scenarios pass (approvals, reminders, follow-ups, Stop / Continue, memory, chases) · Max quiet on ≥ 98% of messages not for it |
| Speed | First status / stream within 2 s · answer p50 ≤ 8 s, p95 ≤ 20 s |
| Cost | ≤ $0.01 per question on average · daily budget and test budget work |
| Reliability | Backup model takes over; clear message if both fail · the full end-to-end run passes **3 times in a row** |
| Security | Keys only in `.env` · L3 / L4 enforced in code · emails only inside the company |
| UI | All screens and cards match the agreed design in light, dark and high contrast |
| Docs | README (how to run) · HANDOVER · decisions and plans up to date |
| Karthi's check | Karthi plays one **scripted working day** at Thirdwave (morning brief → questions → email → plan → chase → digest) and signs off |
