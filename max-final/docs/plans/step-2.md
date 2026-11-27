# Step 2 plan: the simulated Teams, for real (+ Max says hello)

**Status: APPROVED (Karthi, 27 Nov 2026): scope as below, Playwright for browser tests.** Branch: `step-2`. Build plan: `12-build-plan.md`.
Design: `13-ui-design.md` (screens, agreed) · stack: `docs/decisions.md` (Teams SDK for Python, FastAPI, React + Fluent UI).

## Goal
The simulated Teams stops being mock-ups: messages are **saved and loaded for real**, several people (Karthi, Prince,
Praga, Rachitaa) can post in departments, channels and chats, and **Max connects through the real bot protocol** and
answers "hello" when @mentioned or messaged. First proof that the whole path works end to end. No AI yet.

## What we build
| # | Piece | Where | What it does |
|---|---|---|---|
| 1 | Simulator server | `teams_sim/server.py` (FastAPI, port 5100) | Serves the Teams screens, a small API for them, and live updates (WebSocket) so every open window sees new messages at once |
| 2 | Simulator data | `teams_sim/cloud/store.py` (SQLite in `data/teams_sim.db`) | People, departments, channels (incl. private), chats, threads, replies, members. Starts with a small Thirdwave set (the full world comes in Step 3). Reset button = back to the start set |
| 3 | **Fake Microsoft bot service** | `teams_sim/cloud/bot_connector.py` | Speaks the **real Bot Framework contract**: when someone writes to Max, it sends Max the same "activity" Teams would (mention, thread, sender, conversation); Max replies, edits or sends typing through the same endpoints Teams offers. So Max can't tell it from real Teams |
| 4 | Max, first version | `max/app.py`, `max/teams/` (Teams SDK for Python `microsoft-teams-apps` 2.2.1, pinned; port 3978) | Receives messages; @mention in a channel or any message in its 1:1 chat → "Hi Prince, I'm Max. I'm connected 👋" in the same thread. No AI, no knowledge yet |
| 5 | Real screens | `teams_sim/web` | The agreed channel view, chat and simulator bar now use the server (post, reply, quote-reply, switch person, private channel rules, live updates). Files, calendar, mail and Max's pages stay mock-ups until their steps |
| 6 | One command | `python run.py start` / `stop` | Starts the simulator and Max together (and builds the screens if needed); prints the address to open |

## How we check it (tests first)
- **Offline tests (free):** store (posts, replies, private channel visibility, reset); the activities we send to Max
  match the Bot Framework schema (fields Teams really sends); replies land in the right thread; Max's hello logic;
  Max still never imports `teams_sim/` (folder rule).
- **End-to-end in the browser:** open the simulator, post as Prince with @Max → Max's reply appears live in the thread;
  second window as Rachitaa sees it too; 1:1 chat with Max; private channel hidden from Rachitaa. Tool: **Playwright**
  using the Edge already on the PC (new test dependency, no browser download), kept in `tests/e2e/`.
- **Review** by a separate reviewer, fixes + tests, then docs; Karthi commits.

## Questions for Karthi
1. OK with this scope (no AI answers yet: those come in Step 5 after the world and the reading)?
2. OK to add **Playwright** for the browser tests (uses the PC's Edge, nothing big to download)?
