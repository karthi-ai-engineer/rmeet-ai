# Max: UI design (build plan, design step before step 2)

**Status: ✅ DONE (26 Nov 2026): all screens, cards and the 5 Max-chat elements agreed.** Approach (Karthi, 26 Nov: **no Figma, Claude designs**): screens built with
**Fluent UI v9** + its Teams themes in `teams_sim/web/` (mock data), and **shown to Karthi as images** (Karthi:
"give the images"; pictures in `pictures/ui-*.png`, taken with the PC's Edge browser in headless mode).
**Karthi (26 Nov): "create what you recommend"**: Claude decides the UI details; Karthi reviews the images; cards as
Adaptive Cards checked with Microsoft's renderer. Approved mock-ups become the starting point of the real screens.

| # | Part | Status |
|---|---|---|
| 1 | Theme: modes, colours, font, Max's identity, simulator marking | ✅ Decided (as proposed) |
| 2 | Screens list (every screen + what's on it) | ✅ Decided (as proposed; run viewer in R1) |
| 3 | Screens, one at a time, shown as images | ✅ All 15 screens shown (26 Nov) |
| 4 | Cards with Microsoft's renderer | ✅ Shown 26 Nov |

## Part 1: theme (PROPOSED 26 Nov 2026)
| Item | Proposal | Why |
|---|---|---|
| Modes | **Light, Dark and High contrast**, following the computer's setting, with a switch | Real Teams has these 3; Fluent UI v9 ships ready-made Teams themes for all 3 (`teamsLightTheme`, `teamsDarkTheme`, `teamsHighContrastTheme`), so it costs almost nothing |
| Colours | **Teams' own** (Teams purple for buttons and links, Fluent greys); no custom palette | The simulator must look like real Teams; Max's pages become Teams tabs later |
| Font | **Segoe UI** (Teams' font), Fluent sizes and spacing | Same as Teams |
| Max's identity | The **orange cloud avatar** + one small orange accent (e.g. Max's name, "Max is working"); nothing else orange | Max is recognisable without fighting Teams' look |
| Simulator marking | A **thin bar at the very top** ("Simulated Teams · playing as Prince ▾ · Reset world"), clearly separate from the Teams look | Always obvious what is the simulator and what is Teams |
| Max's own pages (setup, health view, plans tab, cost dashboard) | Same themes, same font and spacing | One consistent product |

## Part 2: screens list (PROPOSED 26 Nov 2026)
**A. Simulated Teams** (looks and works like Teams; only what R1 needs):
| # | Screen | What's on it |
|---|---|---|
| 1 | Simulator bar (top, always) | Playing as Karthi / Prince / Praga / Rachitaa ▾ · theme switch · Reset world |
| 2 | App frame | Left rail: Activity, Chat, Teams, Calendar, Mail, Max; top search box |
| 3 | Teams → channel | Departments and channels list; channel posts with replies (threads); compose box with @mention; Posts / Files / Plans tabs |
| 4 | Chat | Chat list; 1:1 and group chats; quote-reply; the 1:1 chat with Max |
| 5 | Files tab | Files list (type, who, when); a simple preview |
| 6 | Calendar | Week view; meeting details (people, time, agenda, Max's brief) |
| 7 | Mail (simple) | Inbox / Sent for each person: check emails Max sent after approval |
| 8 | Activity | Mentions, replies, Max's private notices |
| 9 | Cards inside messages | All agreed cards, drawn by Microsoft's card renderer (Part 4) |

**B. Max's own pages** (Teams tabs / personal app):
| # | Screen | What's on it |
|---|---|---|
| 10 | Plans tab | All plans, owners, dates, late items (P-3) |
| 11 | Setup (first run + settings) | Departments, history window, approvers, levels, working hours, limits, digest, emoji on/off, follow-up window |
| 12 | Health view | One line per chat: last updated, behind by, problems |
| 13 | Cost dashboard | The existing one, restyled to the same look |

**C. Developer tools (Karthi only):**
| # | Screen | What's on it |
|---|---|---|
| 14 | Search tester | Type a question → see the pieces found, scores, re-rank (step 4-5) |
| 15 | Run viewer | One run step by step: tools called, results, cost, time (the "agent watcher", open question: R1?) |

## Part 3: screens (images)
| # | Screen | Images | Status |
|---|---|---|---|
| 1-3 | Simulator bar + Teams frame + channel view | `pictures/ui-1-channel-light.png`, `-dark.png`, `-rachitaa.png` (Rachitaa doesn't see the private Budget channel; sees Sales) | Shown 26 Nov; Karthi: "good" |
| 4 | Chat: list (Max pinned, recent), 1:1 with Max, group chat, 1:1 chats; own messages right in purple, others left; day dividers; quote-reply; reactions; hover actions (react, reply); Max typing dots; compose box (Enter sends) | `pictures/ui-2-chat-max.png`, `ui-2-chat-group.png`, `ui-2-chat-group-dark.png` | Shown 26 Nov; Karthi: "chat is good" |
| 5 | Files tab: file list (type icon, version badge, modified, by, size) + preview panel (Excel sheets with tabs, slide with chart, document pages, scanned label) | `pictures/ui-3-files.png` | Shown 26 Nov |
| 10 | Plans tab (in the channel), **our own plans, no Microsoft Planner** (Karthi, 26 Nov). 3 layouts: **List** (plans with progress, tasks sorted late → blocked → open → done), **Board** (columns Late / Blocked / Open / Done), **Timeline** (due dates on a time line, today line, plan end line). Filters All / Late or blocked / Mine | `pictures/ui-4-plans.png`, `ui-4-plans-board.png`, `ui-4-plans-timeline.png` | Shown 26 Nov; Karthi: "perfect" |
| 6 | Calendar: work week (JST), today column + red "now" line, meetings Max booked marked orange, "Brief" tag on meetings with a brief; details panel: Join, countdown, Max's brief with sources, agenda, people | `pictures/ui-5-calendar.png` | Shown 26 Nov; Karthi: "good" |
| 7 | Mail (simulated): Inbox and "Sent by Max for me"; emails from Max <max@thirdwave.test> "on behalf of" the person, with sources and an "Approved by … from the approval card" line | `pictures/ui-6-mail.png` | Shown 26 Nov |
| 8 | Activity: All / Unread / Mentions / From Max; Max's private notices (approval waiting, lesson to accept, alert, chase, brief ready), mentions, replies, reactions; detail panel + "Go to" | `pictures/ui-7-activity.png` | Shown 26 Nov; Karthi: "good" |
| 11 | Max app › **Setup** (team lead + admin): 6-step wizard with step list: places + history window + on/off (personal chats off), approvals per action, working hours + nightly check + digest, **limits (all editable, apply at once)**, style, review | `pictures/ui-8-setup-places.png`, `ui-8-setup-limits.png` | Shown 26 Nov |
| 12 | Max app › **Health**: 4 tiles (up to date, catching up, needs attention, last nightly check) + table per place (last update, behind by, read back to, status, Catch up now / Read further back / How to fix) | `pictures/ui-9-health.png` | Shown 26 Nov |
| 13 | Max app › **Costs**: today vs daily budget, this week, per answer, test budget; spend per day (14 days, budget line); today by kind of work; model note | `pictures/ui-10-costs.png`, `-dark.png` | Shown 26 Nov |
| — | Max app › **My settings** (everyone): reminders, briefs, morning summary, digest by private message | (in the page) | Shown 26 Nov |
| 14 | Max app › **Search tester** (Karthi only): question + "as person" (privacy filter), the 6 search stages with counts, time and cost, test-question check, best results with keyword / meaning ranks and re-rank score | `pictures/ui-11-search-tester.png` | Shown 26 Nov |
| 15 | Max app › **Runs** (Karthi only): runs today (who, task, status, time, cost) + one run step by step (INTAKE → THINK → tools → checks → REPLY), time and cost per step, details on click | `pictures/ui-12-run-viewer.png` | Shown 26 Nov |

How to retake the pictures: `cd teams_sim/web && npm run build -- --base ./ && npx vite preview --port 5181`, then
Edge headless `--screenshot` with `?as=<person>&theme=<light|dark|contrast>&channel=<id>`.

## Part 4: cards (drawn by Microsoft's Adaptive Cards renderer)
Card data: `teams_sim/web/src/cards.ts` (Adaptive Cards 1.5, buttons = Universal Actions `Action.Execute`); gallery page
`?view=cards`. Host config is a Teams-like approximation, to be replaced by Microsoft's official Teams host config.
| Cards | Pictures |
|---|---|
| Working + Stop, approval (email, with Edit fields), approval (meeting), Continue | `pictures/ui-13-cards-run.png` |
| Living plan card (owner's view, Done / New date / Blocked with reason), chase, meeting brief with countdown | `pictures/ui-13-cards-plan.png` |
| "What do you know about me?", new lesson, alert, limit reached | `pictures/ui-13-cards-memory.png` |
| Dark theme examples | `pictures/ui-13-cards-dark.png` |
Meeting cards ("taking notes", notes review, owners confirm) come with the Max Meeting module.

## Part 5: where Max chats (Karthi, 26 Nov 2026: "the place that needs the most attention")
**Question (Karthi):** must Max's chat follow Teams' look, or can it be our own UI? **Answer (checked against
Microsoft's docs, 26 Nov):** inside a Teams chat, **Teams draws everything** (bubbles, fonts, colours, layout). A bot
cannot restyle it. What a bot controls is the content and these Teams features:
| Feature | What it does | In R1 |
|---|---|---|
| Text with a small markdown set + emoji | the answer itself | yes |
| **Streaming** | the answer appears while it is written; short status updates ("Searching 3 files…") | yes |
| **Citations** | [1] markers; click opens the source | yes |
| **AI-generated label** | fixed by Teams, can't be changed | yes (automatic) |
| **👍 / 👎 + own feedback form** | form opens on 👎 (reason → lessons) | yes |
| **Prompt starters** | suggestions when the chat with Max opens (GA Apr 2026) | yes |
| **Suggested follow-ups** | tappable chips under an answer | yes |
| Adaptive Cards | approvals, plan card, etc. (Part 4) | yes |
| Typing indicator, message update | "Max is typing", edit own message | yes |
Our own UI is possible only in **tabs next to the chat** (Max's personal app: Setup, Plans, Health… = our pages,
following Fluent / Teams design guidance). So: **the chat follows Teams exactly; our design freedom is in the
content, the cards and the tabs.** The simulator must copy Teams' chat exactly, including streaming, prompt
starters, follow-up chips and the feedback form (to add). To be designed one element at a time with Karthi.

**Emoji (Karthi, 26 Nov 2026):** compared Fluent 3D, Fluent Flat, Noto, Twemoji and Windows (`pictures/ui-14-emoji-sets.png`,
page `?view=emoji`). Apple's iOS emoji are not open source. **Decision: keep what we use now** (the system emoji);
real Teams draws message emoji in its own Fluent style anyway.

### Max chat, element 1: opening the chat (PROPOSED 26 Nov 2026)
Picture: `pictures/ui-15-maxchat-1-open.png` (page `?view=chat&chat=max&fresh=1`).
- A new, empty chat with Max shows what Teams draws from the app manifest: Max's icon, name, "AI teammate · Thirdwave",
  a one-line description ("Ask me about your team's chats, files and plans. I answer with sources, and I always ask
  before I send or change anything.") and **6 prompt starters** as tiles.
- Prompt starters are the **same for everyone** (Teams reads them from the manifest): What did I miss? · What's on
  my plate? · Find a decision · Numbers from a file · Make a plan · Remind me. Clicking one sends it.
- A **"View prompts"** button next to the compose box shows them again at any time.
- Max does not send an unprompted welcome message; the first real message comes from the person.
**Element 1 agreed** (Karthi, 26 Nov).

### Max chat, element 2: asking a question, streaming (PROPOSED 26 Nov 2026)
Pictures: `pictures/ui-15-maxchat-2a-status.png` (status updates), `ui-15-maxchat-2b-streaming.png` (text appearing).
Teams' own streaming (1:1 chat with Max): first short **status updates** with a moving line ("Searching team chats and
files…" → "Reading Parts prices.xlsx › Memory…" → "Calculating…" → "Checking the numbers…"), then the **answer appears
word by word** with a cursor; **Stop** at any time ("Stopped. Nothing was sent or changed."). Sources, the AI label and
👍/👎 appear when the answer is complete (Teams adds them to the final message). Status lines say what Max is really
doing (from the agent's steps), never fake progress. In channels and group chats (if Teams streaming isn't available
there) the agreed "Working on it" card is used instead.
**Stop button (Karthi, 26 Nov):** a small **round button with a square inside** (like ChatGPT), in Teams purple,
**inside Max's message** (bottom right) while Max is answering. **While Max answers, the person can't send a new
message** in the simulator (compose box shows "Max is answering… (stop it to ask something else)").
In real Teams a bot can't lock the compose box; anything sent meanwhile waits in Max's queue (agreed QUEUE step) and
is answered right after. Checked: real Teams has its **own Stop button during streaming
(on by default)**, and streaming works in **1:1 chats only**; the bot is told when the user stops. Our simulator copies
that behaviour; in real Teams the button's exact look is Teams' own. Pictures updated (`ui-15-maxchat-2b-streaming.png`,
`ui-15-maxchat-2c-streaming-dark.png`).

### Max chat, element 3: the finished answer (PROPOSED 26 Nov 2026)
Pictures: `pictures/ui-15-maxchat-3a-answer.png`, `ui-15-maxchat-3b-citation.png` (pages `?view=chat&chat=max&demo=done|cite`).
- The answer with bold key numbers and **[1] source chips**. **Hover / tap a chip** → a small card: source title, where
  exactly (e.g. "rows 2-4, Oct and Nov (sum by code)") and **Open at this spot** (Teams citations).
- **"1 reference ⌄"** under the answer: folded list of all sources (Teams shows references this way).
- "AI generated" label + 👍 / 👎 (Teams adds these to the final message).
- **2-3 follow-up chips** under the **latest** answer only (Teams suggested actions): tapping sends that question.
  They disappear when the next message is sent. Written by Max for that answer (e.g. "Compare with September",
  "Show the GPU prices too", "Who decided the 5% price rise?").
**Element 2 (streaming, Stop inside Max's message) and element 3 (finished answer) agreed** (Karthi, 26 Nov).

### Max chat, element 4: 👍 / 👎 feedback (PROPOSED 26 Nov 2026)
Pictures: `pictures/ui-15-maxchat-4a-feedback.png` (form), `ui-15-maxchat-4b-feedback-sent.png` (after).
- **👍** = one click, no form ("Thanks!").
- **👎** opens **Max's own form** (Teams feedback loop with a custom form): "What went wrong?" with reason chips
  (Wrong facts · Wrong numbers · Missed something · Old information · Wrong source · Not what I asked · Too long),
  "What's right? (optional)", and **"Suggest this as a lesson for the team"** (on by default).
- After sending: the 👎 stays filled and a short line under the answer says what happens: "Sent to Prince (team lead)
  as a lesson to accept", or for the team lead: "Saved as a lesson for the team" (team lead's lessons are active at
  once, agreed in memory Part 4). The lesson card then goes to the team lead (`09-cards.md` Part 5).
**Element 4 agreed** (Karthi, 26 Nov).

### Max chat, element 5: cards inside the chat (PROPOSED 26 Nov 2026)
Pictures: `pictures/ui-15-maxchat-5a-card.png` (approval card in Rachitaa's chat with Max), `ui-15-maxchat-5b-card-done.png`
(after Approve), `ui-15-maxchat-5c-card-dark.png`. Live: type "Email Prince the Q1 pricing summary" in a new Max chat.
- One message = a short line of text + the card (Teams: text + Adaptive Card attachment in the same message).
- The card is drawn by Microsoft's renderer with Teams-like buttons; **Approve and send** is the one filled button.
- After the click the **same message updates in place**: the text becomes "✅ Done. The email went to Prince from
  Max's mailbox." and the card becomes the "Email sent" record. No new message.
**Element 5 agreed** (Karthi, 26 Nov). **The Max chat design is complete (elements 1-5).**
