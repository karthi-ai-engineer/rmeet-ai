# Max: cards and message formats (topic 6)

**Status: ✅ AGREED (26 Nov 2026), all 5 parts.** Content and behaviour are agreed here; **the visual UI design
of the cards is a separate, deeper pass before implementation** (Karthi, 26 Nov). Tone and wording: `08-personality.md` (agreed).
Which tool or workflow posts each card: `05-tools.md`, `04-agent-design.md`.

| # | Part | Cards | Status |
|---|---|---|---|
| 1 | Rules for every card | look, buttons, who may click, update in place, expiry | ✅ Agreed (26 Nov) |
| 2 | Run cards | working + Stop, approval (incl. email + meeting), Continue | ✅ Agreed (26 Nov) |
| 3 | Meeting cards | "taking notes" notice, brief, notes, review, action items confirm | ✅ Agreed (26 Nov) |
| 4 | Plan cards | living plan card, chase, weekly digest | ✅ Agreed (26 Nov) |
| 5 | Memory + team lead cards | "what Max knows", lesson accept, alerts, limit reached | ✅ Agreed (26 Nov) |

## Part 1: rules for every card (AGREED 26 Nov 2026)
- **Teams' standard cards (Adaptive Cards 1.5)**: work the same in Teams desktop, web and phone.
- **Clicks go to Max, and the card updates in place for everyone** (Universal Actions, `Action.Execute`):
  "✅ Approved by Sarah, 10:42".
- **Only the right person sees the buttons** (user-specific views); anyone else sees the status only. A wrong click
  gets a private "Only Sarah can approve this".
- **Same layout everywhere:** title line with one signpost emoji → one line saying why → the facts → up to 3 buttons
  → small footer (sources, time).
- **Buttons are clear verbs:** "Approve and send", "Deny", "New date"; never just "OK".
- **First click wins** ("done once" key); the card locks at once, so a double click or two approvers can't act twice.
- **Expiry** (setting, default 24 h for approvals): the card turns into "Expired, nothing was done".
- **After the action** the card becomes a short record (who, what, when); no old buttons left to click.
- **Phone-friendly:** short lines, no wide tables. Colour never the only signal (text + emoji too).

## Part 2: run cards (AGREED 26 Nov 2026; approval default agreed)
Picture (mock-up, before → after each click): `pictures/cards-2-run.png` (generator: `cardmock.py` +
`make_cards_run.py` in the session scratchpad; real cards use Teams' own look).
1. **Working on it + Stop:** only for tasks longer than ~5 s (setting). Shows progress ("reading 12 threads…, step 3 of
   about 8"), updated in place; **turns into the answer itself** when done. Stop: the asker or the team lead →
   "Stopped by Prince at 10:42. Nothing was posted or sent."
2. **Approval (L3):** title says exactly what will happen ("Send this email?", "Book this meeting?"); shows the exact
   email / meeting (who, when + time zone, agenda); buttons: do it / Edit (or Other time) / Deny. Edit opens the same
   card with fields. Footer: who can approve, expiry, sources. After: "✅ Email sent · Approved by Prince, 10:42".
   Approver = the setup setting; default: the person who asked, for their own requests.
3. **Continue?:** what is done so far + what is left (steps, time, cost) → Continue / "Stop here, post what you have".
4. **Expired:** "Expired, nothing was sent". **Wrong person:** private "Only Prince can approve this."

## Part 3: meeting cards (AGREED 26 Nov 2026)
Picture: `pictures/cards-3-meeting.png` (generator `make_cards_meeting.py`, scratchpad).
1. **Brief** (15 min before, meeting chat): title + time JST, who; open items from last time; related files; sources;
   Join meeting. **Live countdown (Karthi, 26 Nov):** Max updates the card in place every minute ("Starts in 12 min"
   → … → "Started · Join now"). Works on desktop, web and phone. A second-by-second timer would need a meeting side
   panel (an app page inside the meeting): considered in the card UI design pass.
2. **"Max is taking notes"** at the start: Pause notes / No notes today; **anyone in the meeting can pause**; nothing
   said while paused is kept; Resume notes.
3. **Notes** after the meeting: summary · 📌 decisions · ⏰ action items (owner + due) · ⚠️ risks, each with the
   transcript minute. **DRAFT until the reviewer approves** (reviewer = setting; default the organizer): Approve notes
   / Edit / Forget a part. After approval: searchable, decisions go to the decisions log, action items go to owners.
   Review not done in 3 days (setting) → one reminder to the reviewer; notes stay a draft. Agreed: reviewer default =
   organizer; anyone in the meeting can pause notes.
4. **Each owner confirms** (private): Accept / Change date / Not mine. Accept → into the plan; Change date → date
   picker, plan owner sees it; Not mine → Max asks the organizer who owns it.

## Part 4: plan cards (AGREED 26 Nov 2026; done items folded)
Picture: `pictures/cards-4-plan.png` (generator `make_cards_plan.py`, scratchpad).
1. **Living plan card** (channel), one per plan, edited in place: title + end date, "6 of 9 done · 1 late · owner",
   open and late items first (✅ done, ⚠️ late, • open), done items folded ("+ 4 more done"); **each owner sees
   Done / New date / Blocked only on their own items**; Open plans tab; footer "Updated 10:55 (what changed)".
2. **Blocked** asks for the reason (one field) → shown on the plan card, plan owner told privately.
3. **Chase** (private): agreed in `08-personality.md` Part 4 (Done / New date / Blocked · Stop these).
4. **Weekly digest** (channel, Monday 9:00, setting): 📌 decided · ✅ done · ⚠️ late · 📅 coming up, with sources.
   Late items name the task, never shame a person; optional reviewer before posting; quiet week → one line.

## Part 5: memory and team lead cards (AGREED 26 Nov 2026; one-click "Raise today's limit")
Picture: `pictures/cards-5-memory.png` (generator `make_cards_memory.py`, scratchpad). All private (1:1 chat).
1. **"What do you know about me?"** (anyone): work facts with date + source; Correct / Delete per fact. Delete →
   "won't learn it again"; Correct → old fact closed, new one saved with "from <person>" as source. Tasks are changed
   in the plan, not here. (Same card shape for "what Max remembers about this thread".)
2. **New lesson** (team lead only): the lesson text, where it came from (👎 + date + source) → Accept / Edit / Reject.
   After Accept: "Lesson active", and the person who gave the feedback is told it was used.
3. **Alert** (team lead + developer): what's wrong, what Max is doing, what it means for answers → Open health view;
   a follow-up card when fixed.
4. **A limit was reached** (team lead): which limit, what happens now, today's usage → Raise today's limit / Open
   settings (all limits are settings).
