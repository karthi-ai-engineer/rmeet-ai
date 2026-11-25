# Competitors: meeting AI and the Microsoft ecosystem

**Date:** 25 Nov 2026. Input to `docs/plans/use-cases.md` (U1-U27). Goes deeper than `use-cases-market.md`.
Sources are mostly vendor pages and trade press, so features are "what they say", not tested. **(?)** = I could not confirm it.

## 1. Microsoft (Teams)

Price: Microsoft 365 Copilot about $30/user/month (enterprise); Copilot Business $21 ($18 promo to Dec 2026). Teams Premium about $10 (?). Most agents only work for **licensed** users.

| Area | What Microsoft has |
|---|---|
| Before | **Facilitator** reads the agenda from the invite or Loop notes and posts it in the meeting chat; asks for goals if there is no agenda. **Channel Agent** can schedule channel meetings. |
| During | **Facilitator**: live co-edited notes, decisions and open questions, agenda tracker with timers, over-time warning plus follow-up booking, @mentions absent people who were talked about, chat Q&A over meeting/chat/files/web, phishing alerts (preview), phone notes for in-person meetings. **Interpreter**: live speech translation in 9 languages (incl. Japanese), can copy your voice, 20 h/month included. |
| After | **Intelligent Recap** (Premium): AI notes, tasks, chapters, speaker and "your name was said" markers. Recap app (Jun 2026), audio recap in many languages, video highlight recap (Copilot, English only), recap without saving a transcript (rolled out Oct 2026), recap translated to your language (Sep 2026), email the summary. Facilitator writes a Word doc from the meeting; PowerPoint in preview. |
| Chat & Q&A | Copilot summarises a thread (30 days, ≥1000 chars). **Channel Agent** (preview): answers from channel posts, channel files, meetings, web; checks file permissions per asker; if others in the chat can't see a source, it asks the asker before sharing. A meeting summary joins its knowledge only after a **24-hour approve/reject window**. |
| Tasks | Facilitator captures tasks → user accepts → Planner; @mention task edits (preview). **Planner agent** (was Project Manager agent; renamed Mar 2026, GA Jun 2026): tasks from transcripts, **workback plans** from a goal and deadline, tasks can be assigned to the agent. Channel Agent assigns tasks and due dates. |
| Proactive | Channel Agent writes status reports (Loop) and flags deadlines buried in chat. Copilot "Automations" (scheduled or event tasks) and "Autopilot" always-on agent (Frontier, Nov 2026) (?). |
| Integrations | Copilot Studio agents in Teams; proactive messages only via Power Automate and only to 1:1 chat; scheduled prompts can't start a Studio agent. **Copilot Studio agents joining meetings was shelved (Aug 2026)**. Third-party agents in admin center (GA expected Oct 2026) (?). |
| Admin & trust | Purview, sensitivity label on answers, per-meeting on/off, web search off switch. Channel Agent: no private channels or external users. |

Copilot Notebooks/Pages: not researched (?).

## 2. Zoom, Google

| Area | Zoom AI Companion / ZoomMate | Google Gemini in Meet/Chat |
|---|---|---|
| Price | Included in paid Zoom Workplace; standalone $10/month (?); **ZoomMate** add-on (Jun 2026), price not public | Included in Workspace Business Standard and up; Google AI Pro/Ultra for personal |
| Before | Suggested agenda items and tasks (?); "Daily Reflection Report" (vendor post only) | Turn notes on from Calendar; stays on for recurring meetings |
| During | **My Notes** works in Zoom, Teams, Meet and in person; Q&A "what did I miss" (Sep 2026); send a notes bot to meetings you can't attend (Aug 2026) | **Ask Gemini**: private catch-up for late joiners, "summary so far"; consent banner for everyone; host can turn it off |
| After | Post-meeting workflows to Docs/Gmail/CRM; **Auto Writing** templates for recurring meetings (Jul 2026) | Notes doc (summary, next steps, details, screenshots of slides); 8 languages; host picks who gets notes. **Recap card posted to the meeting's Chat space** with owners per action item (Oct 2026), arrives silently |
| Chat & Q&A | Agentic search across Zoom, web and apps, with citations | **Ask Gemini in Chat** (Aug 2026): catch up, search Gmail/Drive/Calendar, schedule, tasks; "Project Summary" skill for a space |
| Tasks | Creates tasks, updates trackers | Owners shown on recap; no status tracking (?) |
| Proactive | Plain-language automations at any point of the meeting lifecycle; Agent Teams (Oct 2026) | None found |
| Integrations | Salesforce, Jira, Slack, ServiceNow, Asana, Box, Teams; MCP "Search/Ask" APIs; custom skills with admin guardrails | Workspace apps |
| Admin & trust | No training on customer content; BAA | Admin can force consent, auto-enable, set note length/sections |

## 3. Notetakers

**All of them** have: transcript with speakers, summary, action items, search/chat over past meetings, Slack and CRM push, SOC 2. Only what stands out:

| Product (price) | Stand-out features |
|---|---|
| **Otter** (free; Business $19.99) | Pre-call briefing with past items; "channels" grouping meetings by team; AI Chat **private by default**, you choose to share; voice-activated meeting agents; MCP client + server; bot-free desktop. Facing a class action on recording consent. |
| **Fireflies** ($10/$19/$39) | "Hey Fireflies" voice/text commands mid-call in 60+ languages; Live Assist; AskFred with timestamp citations; 200+ "AI Skills" that run automatically; **topic trackers**; Rules Engine routes meetings to Slack channels; tasks to Asana/Jira/Linear; Fred teammate does scheduling and inbox triage (Nov 2026, rolling out). Credits run out; auto-upgrade on by default. |
| **Fathom** (free; Team $15-19) | Live summaries during meetings; Ask Fathom across all team calls (beta); bot-free on Mac (beta); API + MCP. |
| **Read.ai** (free; $15/$22.50/$29.75) | Recap of the last meeting before a recurring one; Search Copilot over meetings, email, Slack, Teams, SharePoint with citations; **Ada**: CC it on email to schedule or draft replies (you approve), out-of-office cover; private speaker coaching; attendees type "opt out" to remove the bot and delete data. |
| **tl;dv** (Pro about $18-20) | **Recurring AI reports** on a topic across many meetings; agents update CRM, create Jira/Linear tasks, draft follow-ups. |
| **Avoma** ($19/$29/$39 + add-ons) | 90+ note templates per meeting type; live bookmarks; follow-up email drafts; Ask Avoma; scheduler with round-robin; deal-risk alerts to Slack/email. |
| **Granola** (free; $14; $35+) | **Briefs** before meetings (May 2026); agentic chat with citations and **Recipes** (saved prompts, "/"); team Spaces; delete parts of a transcript; MCP; daily "agent brief" (Nov 2026); 32 languages. |
| **Krisp** ($8/$15) | Bot-free notes with noise cancelling; English can run on-device. |
| **Supernormal** (free to $40 (?)) | Now "rooms": shared task board where people **and** outside agents (Claude, ChatGPT via MCP) pick up tasks; drafts deliverables you review. |

## 4. Gap table (features in at least one product, not in U1-U27)

Effort: S = days, M = about a week, L = more.

| # | Feature | Who has it | Why users value it | Effort | Priority | Reason |
|---|---|---|---|---|---|---|
| G1 | **"What did I miss?" during a meeting** (summary so far) | Gemini, Facilitator, Zoom, Fathom, Fireflies | Late joiners catch up without interrupting | S | **Must** | Small add to U8; strong live demo moment |
| G2 | **Review before notes become team knowledge**, plus "forget this part" | Channel Agent (24 h approve/reject), Granola (delete transcript parts), Read (opt out) | Confidential numbers; wrong notes don't spread | S | **Must** | Planning talk is sensitive; makes trust visible |
| G3 | **Workback plan from a goal** ("budget approved by 15 Jan" → steps, owners, dates) | Planner agent | Turns a goal into a plan | M | **Should** | Core planning job; feeds U17 chasing |
| G4 | **Spot deadlines and promises in channel posts**, not only meetings | Channel Agent | "I'll send it Friday" in chat gets tracked | M | **Should** | Much commitment happens in threads |
| G5 | **Note templates per meeting type** (forecast review, budget review) | Avoma, Fireflies, Zoom Auto Writing, Gemini sections, Granola Recipes | Same shape every week, easy to compare | S | **Should** | Fixed template also fixes "different every time" |
| G6 | **Notes and answers in the reader's language** (Japanese/English) | Teams multilingual recap, Gemini, Granola, Fireflies | Mixed-language teams | S | **Should** | Team is in Tokyo; Must if demo audience reads Japanese (?) |
| G7 | **Ask privately, then share** (DM Max; "post to channel" button) | Otter AI Chat, Ask Gemini in Meet, Channel Agent | Ask "silly" questions safely | S | **Should** | Cheap, avoids channel noise |
| G8 | **"You were mentioned while absent"** | Facilitator | Nobody misses a request aimed at them | S | **Should** | Fold into U27 "My day" |
| G9 | **Notice that Max is taking notes + "pause notes"** | Gemini banner, Read opt-out, Zoom bot announces itself | Consent; top legal complaint | S | **Should** | One quiet line, not a speech |
| G10 | Live agenda tracker, timers, over-time warning with follow-up booking | Facilitator | Meetings end on time | M | Later | Needs live meeting UI; Teams already has it |
| G11 | Topic watch and recurring topic reports | Fireflies trackers, tl;dv, Read Ada | Nothing important missed | M | Later | Useful after the core works |
| G12 | Saved team prompts / skills ("/forecast-check") | Granola Recipes, Fireflies Skills, Zoom skills | Repeatable asks | M | Later | |
| G13 | MCP server so other AI tools can query Max's memory | Otter, Granola, Fathom, Read, Fireflies, Zoom | Reuse meeting memory elsewhere | M | Later | Fits U20/U21 later |
| G14 | In-person meeting notes from a phone | Facilitator mobile, Gemini, Zoom, Otter, Read | Office meetings | L | Later | Not Teams-channel work |
| G15 | Remembers personal preferences | Zoom/ZoomMate | Answers fit each person | M | Later | |
| G16 | Video/audio recaps, speaker and name markers | Teams Premium/Copilot, Read | Watch 2 min instead of 60 | L | Skip | Teams already does it |
| G17 | Live speech translation | Interpreter | Talk across languages | L | Skip | Teams already does it |
| G18 | Speaker coaching, talk-time, engagement scores | Read, Avoma, Fireflies | Self-improvement | M | Skip | Feels like surveillance |
| G19 | CRM sync, deal risk, forecasting | Avoma, Fireflies, Fathom, Otter, Zoom | Sales teams | M | Skip | Not a sales team |
| G20 | Email-CC assistant, inbox triage | Read Ada, Fireflies Fred | Scheduling by email | M | Skip | U11/U12 cover it |
| G21 | Bot-free capture; works in Zoom/Meet; meeting hygiene tips; phishing alerts | Notetakers, Read, Facilitator | One tool everywhere | L | Skip | We are Teams-native |

## 5. Where Max is ahead

| Max | Market |
|---|---|
| **Chases owners** with Done / New date / Blocked, limits per day, working hours, private escalation (U10, U17) | Nobody found that chases; Channel Agent only flags deadlines; Google shows owners but no tracking |
| **Owner confirms each item** (U24) | Facilitator: one user accepts tasks to Planner; others just list owners |
| **Decision log across meetings and threads** with source links (U23) | Decisions are per meeting only (Facilitator, Gemini) (?) |
| **One agent over posts, files, transcripts, tasks, reminders** in the channel | Notetakers see meetings first; Copilot is split across Facilitator, Channel Agent, Planner agent |
| **People-set timers** ("remind me at 3 AM", "every Monday 9:00") (U16) | Copilot scheduled prompts can't start a Studio agent; proactive messages only in 1:1 chat |
| **Clear control levels** L0-L4, admin-set approvals, "why did you do that?" (U14) | Admin-side audit (Purview) only; no user-facing explanation |
| **Works for everyone in the channel**, no per-user AI licence | Copilot agents need a $21-30 licence per user to interact |

## 6. Five complaints we must avoid

| Complaint | Evidence | How Max avoids it |
|---|---|---|
| Wrong owner or overstated promise becomes "official truth" | [Venture-Lab 2026](https://venture-lab.org/2026/copilot-meeting-notes-wrong/), [MS Tech Community Jul 2026](https://techcommunity.microsoft.com/discussions/microsoftteams/who-verifies-teams-meeting-summary-accurately-reflects-what-was-actually-agreed-/4542338) | Owner confirm (U24), link to transcript moment, G2 review |
| Bots that join or record without everyone's consent | [Otter class action](https://www.npr.org/2025/08/15/g-s1-83087/otter-ai-transcription-class-action-lawsuit), Fireflies BIPA suit, [PYMNTS 2026](https://www.pymnts.com/artificial-intelligence-2/2026/the-meeting-bot-nobody-invited-is-now-exhibit-a/) | Join only when invited; G9 notice and pause |
| Unreliable capture (joins late, drops, misses) | Avoma reviews: 48% late, 31% drop ([ZoomInfo](https://pipeline.zoominfo.com/sales/avoma-review)); Krisp freezing (G2) | Say clearly when a transcript is missing; never guess |
| Surprise costs and licence walls | Fireflies credits with auto-upgrade; Avoma add-ons; Copilot agents licensed-only | No per-user gating in the demo; show cost per question |
| Meeting records become legal risk | [Bloomberg Law](https://news.bloomberglaw.com/ip-law/ai-notetaking-poses-wiretapping-discovery-and-ethical-pitfalls), [Nat Law Review](https://natlawreview.com/article/when-ai-notetakers-take-stand-legal-risks-lurking-your-virtual-meetings) | Retention setting in first-run setup; "forget this part" (G2) |

## Sources
Microsoft: [Facilitator](https://support.microsoft.com/en-US/teams/copilot/facilitator-in-microsoft-teams-meetings) · [Channel Agent](https://learn.microsoft.com/microsoftteams/set-up-channel-agent-teams) · [Interpreter](https://learn.microsoft.com/en-us/microsoftteams/interpreter-agent-teams) · [Recap](https://support.microsoft.com/en-US/teams/meetings/recap-in-microsoft-teams) · [Recap app (UC Today)](https://uctoday.com/microsoft-teams-is-getting-a-dedicated-meeting-recap-app-this-month-heres-what-it-teams-need-to-do-before-it-arrives) · [Recap without transcript](https://learn.microsoft.com/microsoftteams/intelligent-recap-without-saving-transcripts) · [Planner agent GA](https://techcommunity.microsoft.com/blog/plannerblog/planner-agent-in-microsoft-365-copilot-is-now-generally-available/4527629) · [Rename (office365itpros)](https://office365itpros.com/2026/03/19/planner-agent/) · [Copilot Oct 2026](https://techcommunity.microsoft.com/blog/microsoft-copilot-blog/what's-new-in-microsoft-copilot--october-2026/4568528) · [Teams Sep 2026 (UC Today)](https://uctoday.com/microsoft-teams-copilot-whats-new-in-september-2026) · [Studio proactive messages](https://learn.microsoft.com/en-us/microsoft-copilot-studio/advanced-proactive-message) · [Copilot pricing](https://techcommunity.microsoft.com/t5/microsoft-365-copilot-blog/act-now-lock-in-current-pricing-on-microsoft-365-copilot/ba-p/4502628)
Zoom: [ZoomMate](https://www.zoom.com/en/blog/zoom-ai-companion-zoommate/) · [What's new](https://www.zoom.com/en/products/whats-new/) · [Mar 2026 news](https://news.zoom.com/ec26-zoom-ai/) · [AIC 3.0 community](https://community.zoom.com/customer-success-forum-23/from-conversation-to-completion-zoom-ai-companion-3-0-73615)
Google: [Take notes for me](https://support.google.com/meet/answer/14754931) · [Ask Gemini in Meet](https://support.google.com/meet/answer/16024610) · [Recaps in Chat](https://workspaceupdates.googleblog.com/2026/10/follow-through-on-your-meeting-tasks-with-meeting-recaps-in-Google-Chat.html) · [Ask Gemini in Chat](https://workspaceupdates.googleblog.com/2026/08/ask-gemini-in-chat.html) · [In-person notes](https://workspaceupdates.googleblog.com/2026/08/take-notes-with-me-for-in-person-meetings-is-now-available.html)
Notetakers: [Otter Apr 2026](https://otter.ai/blog/otter-ai-evolves-from-ai-notetaker-to-create-100b-enterprise-conversational-knowledge-engine-market) · [Otter agent](https://otter.ai/meeting-agent) · [Fireflies (ZoomInfo)](https://pipeline.zoominfo.com/sales/fireflies-ai-features) · [Fathom 3.0](https://techcrunch.com/2026/04/15/fathom-adds-a-bot-less-meeting-mode-in-a-bid-to-take-on-granola/) · [Fathom pricing](https://fathom.ai/pricing) · [Read.ai (ZoomInfo)](https://pipeline.zoominfo.com/sales/read-ai-features) · [tl;dv agents](https://tldv.io/ai-agents-for-meetings/) · [Granola updates](https://granola.ai/updates) · [Krisp (Capterra)](https://www.capterra.co.uk/software/1016635/krisp) · [Supernormal](https://www.supernormal.com/)
Note: the ZoomInfo pages are written by a competitor of those tools.
