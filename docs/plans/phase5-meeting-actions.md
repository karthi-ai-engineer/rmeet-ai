# Phase 5.2: Max does things live in a meeting

Karthi (21 Nov 2026): "continue with 2 (do things live) and make it a perfect implementation, with a good UI;
then we continue with the others (1 pre-meeting brief, 3 end-of-meeting check, 4-11)."

## Goal
In a meeting someone says **"Max, book a follow-up on Tuesday with Prince and Daniel"** (or "email Elena the final
numbers", "cancel Friday's sync", "add a task for Jacob …"). Max:
1. understands it during the call (same agent and tools as in the channel, no new powers),
2. posts the **approval card in the meeting chat**, and says one short line: "I've put the meeting in the chat for
   Karthi to approve.",
3. after **Approve**: does it exactly once and confirms ("Booked: Tue 24 Nov 10:30 with Prince and Daniel"),
   spoken if the call is live with voice, written in the chat otherwise,
4. lists what was done in the **meeting notes** ("Done during the meeting").

Nothing new is allowed in a meeting that isn't allowed in the channel: same policies (who may ask / who approves),
same safety rules (company-only email, team files only, no overwrite), same approval card.

## How it flows
```
heard line --"Max …"--> router --question--> classic answer (whole memory, 1 call, fast)   [unchanged]
                               \--action----> agent run (source "meeting", meeting context)
                                               |- read tools, then the external tool -> approval card in meeting chat
                                               |    -> Max: "I've put … in the chat for X to approve."  (no model call)
                                               |    -> click Approve (any time, even after the call) -> execute once
                                               |    -> reply: spoken (live voice call) / meeting chat (text, or call over)
                                               '- no action needed -> reply spoken / in chat
end of meeting -> notes + "Done during the meeting: …" (from the approvals of this meeting's runs)
```
- **Router**: a word check ("book, schedule, set up, email, send, cancel, move, remind, add a task, upload, save …").
  Questions keep today's fast classic answer (Phase 3 quality stays the same). Switch: `MAX_MEETING_BRAIN` =
  `hybrid` (default) | `agent` (everything through the agent) | `classic` (no actions).
- **Who asked**: the speaker from the call roster (name + AAD id) → the approver rules work as in the channel.
- **Meeting context for the agent**: title, people in the call, the last 25 transcript lines, "the meeting chat is
  this thread", spoken style (1-2 sentences, no Markdown).
- **Delivery hook**: the agent's `respond` node hands meeting replies to the live call (speak / chat); if the call is
  over it posts in the thread. Also used when a card is approved later.
- **Meeting chat link**: meetings Max books get a Teams deep link to their channel thread in the invite
  ("Meeting chat and notes: …"), so attendees (and the simulator's meeting view) know where the chat is.
- **Classic answers** must never claim to have done something ("I'll book it" only via the agent).

## UI (simulator, rmeet)
- **Meeting view chat**: Max's messages with formatting, approval cards with working Approve / Change / Cancel
  (clicking as the 'As' person), cards update in place, a "Max is working on it…" line, a badge on the Chat tab and
  the chat opens by itself when a card arrives.
- **Calendar meetings open in the full meeting view** (tiles, live transcript, chat with cards, say box as the 'As'
  person, End meeting), instead of the small box in the calendar list.

## Tests
- Offline (`tests/test_meeting_actions.py`, $0): router, request/meeting context, delivery hook (live voice, live
  text, call over), pause line + approvers, policy still applies, notes section, deep link, classic prompt rule.
- Live (`tests/e2e_phase5_meeting_actions.py`, ~15 requests): Max's own meeting → in the call "Max, book a
  follow-up…" → card in the meeting chat → Approve → event in calendars → Max confirms in the meeting → notes list it.
  Plus "Max, email Elena outside@gmail.com" → blocked, nothing sent. Regression: Phase 3 text + Phase 4 meetings.
- Browser check of the meeting view.

## Status (21 Nov 2026): DONE
Built: `max/meeting_actions.py` (router, run_request, announce_pause, done_section, make_deliver), meeting-aware agent
prompt + delivery hook (`max/agent/graph.py`), `MeetingCall.say` / routing / speaker AAD / Markdown-free speech /
"Done during the meeting" (`max/calling.py`), thread deep link in invites (`max/agent/actions.py`), "updated" line
after Change (`app.resume_approval`), classic meeting rules never claim actions (`max/brain.py`).
Simulator: `/api/calendar/live`, live lines + chat thread for calendar meetings (`server.py`), card + card-update
events in the Budget Review chat (`director.py`); UI: calendar meetings open in the full meeting view (tiles,
transcript, chat with working cards, Speak-as picker, End meeting, reopen after reload), "Live now" banner, chat
badge + auto-open on a card, "Max is working on it…", Max tile only when Max is part of the meeting.

Tests:
- `tests/test_meeting_actions.py` ALL PASS ($0): router (13 actions / 9 questions incl. real meeting lines), pause /
  "updated" lines, call routing + speaker AAD, meeting prompt, delivery (live / after the call), approve once,
  wrong approver refused, Change -> new card, policy in meetings, notes section (replaced versions skipped), deep link.
- Router vs all 23 distinct lines said to Max in the 15 saved Budget Review runs: 0 sent to the agent (all questions).
- Live `tests/e2e_phase5_meeting_actions.py` ALL PASS (11 requests): book follow-up in the call -> card in the meeting
  chat -> Prince refused -> Karthi approves -> in calendars -> Max confirms; outside email refused; question fast;
  notes list the booking.
- Regression: Phase 4 meetings ALL PASS (5 req), Phase 3 meeting ALL PASS, notes 40/40; all offline suites pass.
- Browser: card in meeting chat, Change (fixed a wrong "April" date to "1 May 2027"), Approve -> Done card + Max
  confirmation, notes, Live-now banner, auto-reload + reopen during a meeting.
Found and fixed while testing: wrong variable in run_request (offline test), no line after Change, stale status line,
reload closed the meeting view, Max tile shown in meetings Max isn't in, focus blocked the auto-reload, the router
sent "remind me, what…" and the host's "…I'll send X. Max, please post the summary." to the agent (now: only the
words from "Max" on count; notes are automatic).

# Phase 5.3: End-of-meeting check (built 22 Nov 2026)
Karthi: "continue with 3 perfectly".
- **Trigger**: someone closes the meeting ("OK, let's wrap up", "before we finish", "that's all for today", "any other
  business") -> once per meeting, only after 6+ lines; or someone asks Max ("Max, recap", "Max, what did we decide?",
  "Max, read back the action items") -> any time. "Max, email Elena the recap" stays an action (agent).
  Checked against all lines of the 15 saved Budget Review meetings: 0 false triggers.
- **Max reads back**: one notes call (same prompt as the final notes) -> spoken short recap in a voice call ("Before we
  finish, here's what I have: 2 decisions and 3 action items… Is anything missing or wrong?") + the draft in the
  meeting chat (highlighted). If Max is busy answering, the recap waits and runs right after.
- **Corrections**: people say them ("Max, my date is the 27th"); Max confirms in one sentence; the final notes prompt
  says corrections after the recap win; the notes end with "I read the decisions and action items back…".
- **Fixed with it** (found in the 5.2 demo): notes now use the meeting's real date in the team's time zone (was a fixed
  "Fri 20 Nov" from the Budget Review scenario); Max is never an action-item owner (prompt + filter + save_meeting_tasks
  skips Max/bot accounts), so it no longer chases itself.
Code: `brain.recap_text / is_max / MeetingSession(today=…)`, `meeting_actions.wants_recap`, `MeetingCall._respond /
_recap` (calling.py), `followups.save_meeting_tasks`, UI recap bubble + status (app.js/app.css).
Test robustness: "Reset channel" now ends a calendar meeting left running; e2e tests reset Max's test clock at start.
Results (22 Nov 2026):
- Offline: `tests/test_meeting_recap.py` ALL PASS (22 checks, $0) + all 11 other offline suites pass.
- Live: `tests/e2e_phase5_recap.py` ALL PASS (6 req): wrap-up -> draft read back (2 decisions, 3 actions, dates from the
  meeting's real day) -> Daniel corrects 26th -> 27th -> Max confirms -> final task due 2026-11-27, no task for Max.
- Regression: Phase 4 meetings, Phase 5.2 meeting actions, Phase 3 meeting (notes 40/40), Phase 3 live+edges: ALL PASS.
- Browser: recap bubble (chat opens by itself), status line, "Max, can you recap please?" again, correction, notes.
Found and fixed while testing: the simulator's director (and tests, and the meeting view) took ANY Max message with
"meeting notes" in its first 80 characters as the notes (Max's reply "I'll include them in the meeting notes…" was
graded -> 15/40); now only the real "📝 Meeting notes" heading counts. A run blocked by the old daily cap left a
meeting running and Max's test clock moved -> reset channel ends it, tests reset the clock. Draft didn't open the
chat (only a badge) -> opens now. `_italic_` didn't render in the simulator -> renders like Teams.

# Phase 5.1: Pre-meeting brief (built 22 Nov 2026)
Karthi: "yes go ahead and implement perfectly".
- 15 minutes before a meeting Max knows (Max-booked or synced Teams meetings), the old 15-min reminder became a brief
  in the meeting's thread (`max/briefs.py`, no AI, $0): heading + time + join link; "With:" @mentions of the people
  invited (never Max); Agenda (from the invite); **Last time** = decisions of the meeting this one follows on from
  (same Teams meeting > same thread > same title ignoring "Follow-up:"; never an unrelated meeting) + "Action items
  from then: X of Y done"; **Open action items** of the people invited (overdue first, ⚠️ "was due"), else the team's;
  **New since last time** (files added/updated after that meeting); **Waiting for approval** (cards open in the thread).
- Data: schema v6 `meeting_notes` (title, thread, Teams link, held_at, notes JSON) saved by MeetingCall.finish;
  reminder jobs now carry attendees + agenda (Max-booked meetings).
- UI: the brief has its own blue bubble in the meeting chat.

# Fixes from Karthi's channel test (22 Nov 2026)
"@Max book a meeting tomorrow 11 am" -> Max invited people nobody named and asked "shall I book 12:00?" in chat; then
a NEW post "@Max yes go ahead" -> "I have noted your approval, I will proceed…" (nothing was done). Fixed:
- Rules: never claim something no tool did; unclear on its own -> ask; invite only the people named; busy asked
  time -> the nearest free time goes on the card (the card is the confirmation).
- `create_meeting(asked_start=…)`: the card shows "💡 You asked for 11:00, but Prince Alex is busy 11:00–12:00 (…)" -
  checked in code against the calendars, not written by the model.
- `max/conversation.py`: a short NEW post from someone Max is waiting on in another thread (approval card or
  question, within 15 min) gets that context: "yes go ahead" -> "press Approve on the card" (approving is always a
  click, never a chat message; no second card); an answer to Max's question continues that request.
Tests: `tests/test_conversation.py`, `tests/test_meetings.py` (note), live `tests/e2e_conversation_fixes.py`.
Results (22 Nov 2026): offline `test_meeting_brief` (15 checks), `test_conversation` (10), `test_meetings` (+note),
all 14 offline suites ALL PASS ($0). Live: `e2e_phase5_brief` ALL PASS (6 req; the brief itself 0 req),
`e2e_conversation_fixes` ALL PASS, Phase 5.2 / 5.3 / 4.4 / 4.5 / agent eval ALL PASS, Phase 3 meeting ALL PASS (notes
37-40/40 between runs: the colleagues' lines are generated fresh each run). Test fix: the simulator's notification
log showed only the last 15 entries, so the "transcript published" check could miss it after a busy meeting -> 50/100.
