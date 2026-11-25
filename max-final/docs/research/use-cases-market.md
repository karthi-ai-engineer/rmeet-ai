# What comparable AI teammates offer (market check for Max use cases)

**Date:** 25 Nov 2026. Input to `docs/plans/use-cases.md` (draft 2). Sources are mostly vendor pages, so treat feature claims as "what they say", not tested facts.

## 1. Features our draft is missing

Effort for us: **S** = days, **M** = about a week, **L** = more.

| # | Missing feature | Who has it | Why users value it | Effort | Priority |
|---|---|---|---|---|---|
| F1 | **Decisions log**: one list of "what we decided, when, by whom", each with a link to the source | Gemini notes have a "Decisions" section; Facilitator notes; Read.ai Topics | Managers ask "what did we agree?" more than anything else | S (comes out of U5 notes) | **Must** |
| F2 | **Citations on every answer**, with a jump to the exact transcript moment, file section or post | Glean (citations on each sentence); Copilot | Trust. People check before they repeat a number | S-M | **Must** |
| F3 | **Weekly status digest**: done, due this week, late, blocked, decisions | Teams Channel Agent status report; Slack "Weekly Update"; Asana Smart Status | Saves the manager from chasing people for a status | M | **Must** |
| F4 | **Carry open items into the next meeting** (added to U7) | Fellow; Zoom "prepare me for a meeting"; Slack Meeting Prep | Recurring meetings start where the last one stopped | S | **Must** (move U7 to M) |
| F5 | **Owner confirms each action item** ("Is this yours? Accept / change / not mine") | Linear (a human stays accountable); a common Copilot complaint is wrong owners | Fixes the biggest trust problem in AI notes | S | **Must** |
| F6 | **Follow-up email draft after a meeting** (U11 tied to U5) | Zoom AI Companion "Post Meeting Follow Up"; Copilot | Saves 10 minutes after every external meeting | S | Should |
| F7 | **"My day" message**: my tasks, today's meetings, what needs my reply | Slack "Daily Priorities" | A personal benefit for each person, not only the manager | M | Should |
| F8 | **Workback plan from a goal**: "Launch by 15 Jan" becomes steps with owners and dates | Planner Agent and Channel Agent in Teams | Turns a goal into a plan Max can then chase | M | Should |
| F9 | **Live meeting helper**: agenda timer, "10 min left", capture items in the meeting chat | Teams Facilitator | Meetings stay on time | M-L | Later |
| F10 | **Topic watch**: "tell me when anyone mentions the GPU tender" | Read.ai Topics; Fireflies trackers | Nothing important gets missed | M | Later |
| F11 | **Live translation** | Teams Interpreter | Multi-language teams | L | Later |
| F12 | **Explain what Max did** (U14) | Notion agents log every run; Asana shows what AI Teammates did | Needed as soon as Max acts on its own | S | Raise U14 to Should |

Already in our draft and matching the market: U1/U3/U6 Q&A over meetings and files, U5 notes, U8 "Hey Otter"-style in-meeting questions, U18 decks (Glean, Copilot), timers.

## 2. Five "wow" moments for a 10-minute demo

1. **Meeting ends, and within a minute notes appear in the channel**: summary, decisions, action items with owners, each linked to the transcript moment. One card: "Create these 4 tasks?" One click, the tasks exist. (U5, U9, F1, F2)
2. **"@Max what did we decide on memory prices, and why?"** The answer pulls from a meeting, a file and a thread, with three clickable sources. (U1, F2)
3. **15 minutes before the follow-up meeting**, Max posts a brief: last time's open items, who is late, which file changed. (U7, F4)
4. **Chasing that doesn't nag.** A task is overdue, so Max sends the owner one private message with buttons: *Done / New date / Blocked*. The owner clicks "New date: Fri". The Monday digest updates by itself. (U17, F3)
5. **"Make a 5-slide deck of Q1 results in our style"**, then "remove slide 3". A real PowerPoint appears in the chat. (U18)

Managers react most to #1 and #4 because they save *their* time. Show the approval card in #1 and #4 so trust is visible.

## 3. Control and trust patterns

**What others do**

| Topic | Market pattern |
|---|---|
| Who approves | The **requester** approves the agent's actions (Lindy "Ask for confirmation"; Dust tool approval). The **admin** decides which tools need approval: Dust lets admins mark tools "high stake = always ask" or "low stake = user can stop being asked". Asana AI Teammates ask before acting. Linear: the person who started the agent stays responsible. |
| Drafts | Prefer making a draft over sending (Lindy Gmail drafts; Asana drafts the status update and a human posts it). |
| Proactive messages | Microsoft's bot guidance: use proactive messages sparingly, always say why, no bursts, respect the user's time zone. Geekbot: snooze, the person's local time, pause while out of office. Notetakers are disliked when they join or speak unasked ([Bloomberg](https://www.bloomberg.com/news/articles/2025-02-14/ai-notetakers-in-meetings-are-making-me-queasy), [ClickUp complaint](https://feedback.clickup.com/ai-notetaker/p/prevent-ai-notetaker-from-introducing-itself-in-meeting-chat)). |
| Audit | Notion logs every agent run. Asana shows admins what the AI did. Glean shows the sources used in a side panel. |
| Disclosure | Gemini shows all participants that notes are being taken. Linear: agents must be clearly marked as agents. |

**Recommended defaults for Max**

| Level | Default |
|---|---|
| L0, L1 | Automatic. L1 is logged. Answers only use data the asker can already see. |
| L2 | Automatic and logged. Max can **delete its own post** if someone asks ("undo"). |
| L3 | Approval card that shows exactly what will be sent, with **Edit / Approve / Cancel**. The card expires after 24 h. |
| L4 | Refuse, explain why in one line, log it. |

**Who approves L3** (simple rule):
- **Acts for me** (my email, my meeting, my file): the **requester** approves.
- **Gives work to someone else** (tasks from meeting notes): the **meeting organizer** approves the batch, and each **owner** then gets "Accept / change date / not mine" (F5).
- **Which tools are L3 or L4**: set by the **admin** (Karthi), not by users.
- Later: a "don't ask again for this kind of action" option for low-risk actions, as Dust does.

**Proactive rules**
- Max only speaks up unasked for agreed triggers: meeting ended, brief, reminder, chase, digest.
- Every proactive message says why it was sent ("because you own task X, due today").
- At most 1 chase per task per day and 3 proactive private messages per person per day. Several items go into one message.
- Quiet hours: outside the person's working hours and on weekends, Max waits. A reminder a person sets for themselves (the 3 AM case) is allowed.
- Snooze or mute per person and per channel. Max never joins a meeting it wasn't invited to.

**Citations**: every fact links to its source. If Max finds nothing, it says "I couldn't find this" instead of guessing.

## 4. Plan follow-up and chasing (simple design)

Market check: Asana only reminds people and drafts status updates; it doesn't send them on its own. Geekbot reminds people, lets them snooze, and lists who hasn't replied. It does **not** report to managers. Planner and Channel Agents create plans and status reports.

**Design for Max**
1. **Plan** = tasks with owner, due date and a source link (usually from meeting notes).
2. **On creation**: the owner confirms (Accept / change date / not mine).
3. **1 working day before the due date**: one private nudge with buttons **Done / New date / Blocked (why?)**.
4. **Morning after the due date**: one more nudge. Then Max stops nudging.
5. **2 working days overdue**: Max tells the **plan owner** (the person who asked for the plan or ran the meeting) privately. It never names late people in the public channel, and it doesn't report to managers by default.
6. **Monday 9:00 digest** in the channel: done, due this week, late or blocked (counts and items, neutral tone), plus decisions from the week (F3, F1).
7. Out of office or snoozed: pause. Each reply updates the plan right away. No free-text form to fill in.

## 5. Pitfalls that make AI teammates annoying or untrustworthy

| Pitfall | Seen where | How Max avoids it |
|---|---|---|
| Wrong owner or invented action item treated as fact | [Copilot recap threads](https://techcommunity.microsoft.com/discussions/microsoftteams/who-verifies-teams-meeting-summary-accurately-reflects-what-was-actually-agreed-/4542338), [Venture-Lab](https://venture-lab.org/2026/copilot-meeting-notes-wrong/) | Owner confirms; link each item to the transcript moment |
| Missed implicit commitments, generic summaries | Otter reviews | Short notes; "possible action items" listed separately |
| Uninvited bots, noisy self-introductions | Bloomberg, Product Hunt, ClickUp | Join only when invited; one quiet line, not a speech |
| Too many pings, no reason given | Microsoft bot guidance | Limits, bundling, quiet hours, "why you got this" |
| Acting without asking | [PCWorld](https://www.pcworld.com/article/3276905/my-ai-agents-sent-emails-without-my-ok-this-simple-prompt-stops-it.html) | L3 cards; drafts by default |
| Approval fatigue (too many cards, people approve blindly) | General pattern | One card per batch; only for leaving the thread |
| Showing data the person can't see | Glean and Slack stress permission checks | Check what the asker can see on every read |
| Polished but wrong output ("workslop": 4.5 h a week fixing AI work) | [Zapier survey](https://zapier.com/blog/ai-workslop/) | Citations, "I couldn't find this", short answers |
| Different results each time | [Copilot forum](https://techcommunity.microsoft.com/discussions/microsoft365copilot/inconsistent-meeting-recap-results/3993623) | Fixed note template; test on demo data |
| Public shaming for late tasks | Chasing tools | Escalate privately to the plan owner only |

## Sources
- Teams: [Facilitator](https://support.microsoft.com/en-us/office/facilitator-in-microsoft-teams-meetings-37657f91-39b5-40eb-9421-45141e3ce9f6), [Channel Agent](https://learn.microsoft.com/microsoftteams/set-up-channel-agent-teams), [Planner Agent GA](https://techcommunity.microsoft.com/blog/plannerblog/planner-agent-in-microsoft-365-copilot-is-now-generally-available/4527629), [Interpreter](https://learn.microsoft.com/en-us/microsoftteams/interpreter-agent-teams), [proactive bot guidance](https://learn.microsoft.com/en-us/azure/bot-service/bot-builder-howto-proactive-message)
- [Slack feature drop Apr 2026](https://slack.com/blog/news/slack-feature-drop-april2026) · [Gemini take notes](https://support.google.com/meet/answer/14754931) · [Zoom AI Companion 3.0](https://news.zoom.com/ai-companion-3-0-and-zoom-workplace/) · [Otter Meeting Agent](https://www.engadget.com/ai/otterais-meeting-agent-can-schedule-calls-and-write-emails-for-you-130048189.html)
- [Glean Assistant](https://glean.com/ai-assistant) · [Notion releases](https://www.notion.com/releases/2026-07-31) · [Asana Smart Status](https://help.asana.com/s/article/smart-status) · [Asana AI Teammates approval](https://forum.asana.com/t/exciting-new-approval-process-for-ai-teammates/1125568) · [Linear agents](https://linear.app/docs/agents-in-linear) · [Dust tool approval](https://docs.dust.tt/changelog/️-customizable-tool-approval-settings-for-mcp-tools) · [Lindy human-in-the-loop](https://docs.lindy.ai/testing/human-in-the-loop) · [Geekbot](https://help.geekbot.com/en/articles/14007711-geekbot-features) · [Fellow carry-over](https://fellow.ai/blog/ai-agent-meeting-notes-to-tasks/) · [Notetaker comparison 2026](https://www.techrepublic.com/article/news-best-ai-meeting-note-takers-2026/)
