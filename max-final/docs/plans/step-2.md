# Step 2 plan: the simulated Teams, for real (+ Max says hello)

**Status: ✅ DONE (27 Nov 2026), see Results. Plan approved by Karthi 27 Nov (scope as below, Playwright for browser tests).** Branch: `step-2`. Build plan: `12-build-plan.md`.
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

## Results (27 Nov 2026)
**Status: DONE**: built, reviewed by an independent reviewer (two rounds: findings, then a check of the fixes),
fixes tested. Pictures:
`pictures/ui-17-step2-channel-prince.png`, `ui-17-step2-channel-rachitaa-live.png` (Max's reply arrives live in
another window), `ui-17-step2-chat-praga.png`.

| Piece | Where | Notes |
|---|---|---|
| Simulator server (port 5100) | `teams_sim/server.py` | API for the screens, one WebSocket per tab, JSON-only changes. All handlers async (one SQLite connection, never two threads) |
| Simulator data | `teams_sim/cloud/store.py`, `seed.py` | SQLite `data/teams_sim.db`; start set = people, 3 departments, private Budget channel, chats, a few messages |
| Fake Microsoft bot service | `teams_sim/cloud/bot_connector.py` | Real Bot Framework contract: activities checked against the SDK's own model; send / reply / update / delete / typing / streaming (1:1 only); AI label and 👍/👎 only when Max marks a message; Teams-like ids |
| Max, first version | `max/app.py`, `max/teams/hello.py` | Teams SDK for Python 2.2.1. Hello in its 1:1 chat always, in channels / group chats when @mentioned |
| Screens on the real server | `teams_sim/web/src/api.ts`, `App.tsx`, `ChatScreen.tsx` | Channels, threads, chats, quote-reply, person switch, Reset, live updates, typing / streaming preview. Showcase URLs (`demo=`, `fresh=`, `step=`) still show the agreed design demos on mock data |
| One command | `run.py start / stop / e2e` | `stop` only stops Python programs listening on 5100 / 3978 |

**Settings:** `TEAMS_MODE=sim` (default) or `teams`; `BOT_PORT`. In sim mode Max accepts unsigned messages, so it
answers only this PC (127.0.0.1, no proxies or tunnels) and ignores any real credentials; real mode always checks
Microsoft's signature (`.env.example`). Never forward Max's port in sim mode with a plain port forward (`netsh portproxy`,
`ssh -L/-R`): those add no "forwarded" header, so Max can't tell. For real Teams use `TEAMS_MODE=teams`.

**Tests:** unit (store, server, bot service, Max app, hello, settings) all pass; end to end: both programs on free ports
+ browser tests with Playwright on the PC's Edge (channel @Max live in a second window, 1:1 chat, group chat,
private channel hidden, saved after reload, reset, no AI label on the plain hello), 10 tests, repeated runs clean.

**Bugs found by the tests and the review (each now has a test):** shared database connection across threads (hang);
messages missed between page load and live connection; live messages lost while a list was loading; an unread
output pipe froze the test programs; Max could edit its message through another conversation (and the edit went to
the wrong people); real credentials in `.env` would have been used in sim mode; streamed answers had a different id
than the SDK expects; mention list taken on trust; stuck tabs never told to reconnect; `run.py stop` could hit an
unrelated program after a reboot; deleted messages could be quoted / replied to / edited; the SDK's stream-timeout
fallback (final text sent as an edit) left the answer hidden.

**Known gaps (on purpose, later steps):** the newer `channelData.replyChain` + `/replyChains/` route of the SDK is not
simulated (Max uses the classic `;messageid=` thread path, which real Teams supports); card buttons (`Action.Execute`)
don't reach Max yet (Step 6); Files, Calendar, Mail and Max's pages are still mock-ups (their steps); new chats don't
appear without a reload; Max streams nothing yet (no AI until Step 5).
