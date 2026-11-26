# Competitors: workspace AI teammates and knowledge agents

**Date:** 25 Nov 2026. Input to `docs/plans/02-use-cases.md` (U1-U27). Goes deeper than `use-cases-market.md`.
Sources are mostly vendor pages, so treat them as claims. **(unverified)** = not confirmed from a 2026 primary source.
Tags: **Search**, **Chat**, **Tasks**, **Proactive**, **Docs**, **Actions**, **Multi** (agents/automation), **Memory**, **Trust** (admin, approvals, audit, citations).

## 1. Products, feature by feature

| Product | Main features | Price |
|---|---|---|
| **Microsoft Teams agents + Copilot** (our home turf) ([Channel Agent](https://learn.microsoft.com/microsoftteams/set-up-channel-agent-teams), [June 2026](https://techcommunity.microsoft.com/blog/microsoft365copilotblog/what’s-new-in-microsoft-365-copilot--june-2026/4529572), [Cowork GA](https://microsoft.com/en-us/microsoft-365/blog/2026/06/16/copilot-cowork-is-now-generally-available)) | **Search/Chat:** Channel Agent answers from channel posts, files, meetings, web. **Tasks:** assigns tasks, flags buried deadlines; Planner Agent builds plans. **Proactive:** status reports, reviewer can approve first. **Docs:** Researcher reports, Analyst charts, Notebooks. **Actions/Multi:** Cowork long tasks, browser automation, plugins, skills. **Trust:** meeting summary waits 24 h for approve/reject before becoming knowledge; asks before sharing a privately-sourced answer; Purview audit; credit caps. **Limits:** Channel Agent in preview, one channel, no private channels, US English first. | Copilot licence (about $30/user/mo, unverified 2026) + Copilot Credits for Cowork |
| **Slack (Slackbot, Agentforce)** ([Apr 2026 drop](https://slack.com/blog/news/slack-feature-drop-april2026), [TNW](https://thenextweb.com/news/slack-slackbot-30-ai-features-agentic)) | **Search/Chat:** messages, files, decisions; PDF Q&A (incl. Japanese). **Proactive:** morning priorities, weekly report, meeting prep, daily recaps, **scheduled tasks** tab. **Docs:** project kickoff (channel + canvas + milestones). **Actions:** DM, channels, workflows, email, meetings, MCP. **Multi:** routes to the right Agentforce agent; **Skills** = saved shareable workflows. **Meetings:** decisions + action items. **Trust:** visible reasoning timeline. **Memory:** roadmap. | In Business+ / Enterprise+; limited on Free/Pro; Agentforce uses credits; 15 Slackbot msgs/week on Business+ (third-party, unverified) |
| **Glean** ([release notes](https://docs.glean.com/release-notes/), [May 2026](https://www.glean.com/blog/may-2026-launch), [SiliconANGLE](https://siliconangle.com/2026/02/17/glean-adds-bit-sheen-enterprise-ai-assistant/)) | **Search:** permission-aware, personal graph. **Chat:** voice; resume old chats. **Tasks:** activity cards with first drafts. **Proactive:** scheduled agents (about one run per day), daily action items, email triage. **Docs:** on-brand slides, Canvas, Library of outputs. **Actions:** 100+ actions chained in one run, MCP. **Multi:** **sandboxes** (code interpreter). **Memory:** persistent (billed). **Trust:** preview of changes before every write; citations; auto-pause at limit. | No public price (unverified); credits for memory, voice |
| **Atlassian Rovo** ([Team '26](https://www.atlassian.com/blog/company-news/rovo-team-26)) | **Search:** Teamwork Graph + connectors. **Chat:** **Max mode** shows the plan and asks approval before running. **Docs:** docs, decks. **Actions:** Jira items, notify, meetings. **Multi:** Studio no-code agents, event triggers, graph via MCP. **Trust:** approvals, versioning, agent inventory, audit logs. | Credits per plan (complaints below); exact price unverified |
| **Notion AI** ([Agents](https://www.notion.com/product/agents), [pricing](https://www.notion.com/help/custom-agent-pricing)) | **Search:** enterprise search (beta), Meeting Notes. **Proactive:** agents on schedule or triggers (Slack emoji, new email, calendar change); Q&A, triage, status templates. **Actions:** Slack, Mail, Calendar, MCP. **Memory:** user style. **Trust:** every run logged with reasoning; **undo via version history**; per-agent permissions; prompt-injection flagging; per-agent budgets. | Business/Enterprise; agents $10 per 1,000 credits since 4 May 2026, pause when empty |
| **Asana AI Studio / AI Teammates** ([help](https://help.asana.com/s/article/ai-teammates), [memory](https://venturebeat.com/orchestration/asanas-ai-agents-share-memory-across-your-company-but-not-your-secrets)) | **Tasks:** subtasks with **checkpoints** to redirect; Smart Status drafts. **Multi:** no-code teammates, AI Studio rules. **Memory:** you can **see, edit, delete** it; visible only to those who can see the source. **Trust:** approval for deletes and privacy-sensitive actions. | AI Studio tiers; Teammates GA unverified |
| **ClickUp Brain / Super Agents** ([launch](https://clickup.com/blog/super-agents-launch/)) | **Triggers:** schedule, task created, form, @mention, assignment. **Tasks:** agents own recurring work, flag risks. **Memory:** preferences + long-term memory in editable Docs. **Multi:** 500+ skills. **Trust:** audit log, approval before high-impact actions. | Brain add-on / "Everything AI" tier (prices unverified) |
| **monday.com** ([Mar 2026](https://ir.monday.com/news-and-events/news-releases/news-details/2026/monday-com-Welcomes-AI-Agents-to-Its-Platform-Marking-a-Shift-in-How-Work-Gets-Done/)) | Sidekick agent; built-in agents for all customers; Agent Factory (standalone builder); **outside agents can sign up and work on boards** via MCP/API under the same permissions; webhooks trigger agents. | Agents use normal plan pricing |
| **Dust** ([changelog](https://docs.dust.tt/changelog), [Pods](https://docs.dust.tt/docs/pods-overview)) | Agents in Slack/Teams/email; triggers created **by chatting**; **Pods** (shared space for people + agents); **Frames** (interactive reports); per-tool approval (read free, delete asks). | Per seat (unverified) |
| **Lindy** ([site](https://www.lindy.ai/)) | Inbox, calendar, meeting follow-ups; routines (7:00 brief); memory; computer use; 3,000+ apps; asks first, runs alone once trusted. | Team $29.99/user/mo, 3,000 credits |
| **ChatGPT Enterprise** ([release notes](https://help.openai.com/en/articles/10128477-chatgpt-enterprise-edu-release-notes)) | Workspace agents; **ChatGPT Work** scheduled tasks (recurring, triggered, **monitor for changes**), team tasks; @ChatGPT in Teams/Slack; memory with **source attribution**; shared Projects; Record & Replay makes skills; "ask before consequential actions"; audit logs. | Seat + token credits for Work/agents |
| **Claude for work** ([release notes](https://support.claude.com/en/articles/12138966-release-notes)) | Projects; M365 connector (Teams read-only); editable memory; Cowork scheduled tasks; skills/plugins; Slides/Docs; Excel/PowerPoint add-ins; Claude Meetings (beta); connector permissions per role. | Team / Enterprise (self-serve) |
| **Gemini Enterprise** (ex-Agentspace) ([Apr 2026](https://cloud.google.com/blog/products/ai-machine-learning/whats-new-in-gemini-enterprise), [Computerworld](https://www.computerworld.com/article/4161990/gemini-enterprise-update-brings-ai-agents-into-collaborative-workflows.html)) | Long-running agents; **Inbox** ("Needs your input / Errors / Completed"); human checkpoints; shared Projects; Canvas; Deep Research, Data Insights; skills; charts and forms in chat; BYO-MCP; agent registry. | $30/user/mo (large), $21 (small) |
| **Moveworks** (ServiceNow) ([docs](https://www.servicenow.com/docs/r/SogDT~k7ktsbe1ZYegnaLg/qYkqTXYYC1B9v8jiByyRdQ)) | Search + action in one box; web search; 100+ languages, user picks answer language; personal Slack/Outlook content; Agent Studio. | Enterprise, custom |
| **Sana (Workday)** ([Mar 2026](https://newsroom.workday.com/2026-03-17-Introducing-Sana-from-Workday-Superintelligence-for-Work-That-Finds-Answers,-Takes-Action,-and-Automates-Workflows)) | Answers + HR/finance actions; connectors; reachable from Teams, Slack, Copilot, Claude, Gemini; admins switch skills on/off. | Workday Flex Credits |
| **Zapier Agents** ("AI by Zapier") ([blog](https://zapier.com/blog/zapier-agents-is-now-ai-by-zapier/)) | 8,000 apps; "require approval before running" per tool; guest approvers via link; **run pauses after 75 steps** (runaway guard). | Pro about $50/mo (third-party) |
| **Viktor** ("AI employee") ([Teams launch](https://www.producthunt.com/products/viktor/launches/viktor-for-microsoft-teams)) | In Teams since Jun 2026: memory over weeks, flags issues, suggests automations, 3,200 tools, reports, builds apps. | Not published |

## 2. Gap table: in at least one product, not in U1-U27

Effort: S = days, M = about a week, L = more.

| # | Feature | Who has it | Why users value it | Effort | Priority | Reason |
|---|---|---|---|---|---|---|
| G1 | **Runaway guard**: max steps per run + daily spend cap, clear "stopped" message | Zapier (75 steps), Notion/Glean/Copilot budgets | Stops loops and bill shocks | S | **Must for demo** | A loop on stage breaks the demo; cheap |
| G2 | **"How I got this" panel** under each answer: steps + sources, collapsed | Slack reasoning timeline, Notion run log, Gemini step view | Trust without asking U14 | S | **Must for demo** | Makes trust visible; we already log it |
| G3 | **Reusable skills**: "save this as the monthly variance routine" | Slack, ClickUp, Gemini, Cowork, Glean, Claude, ChatGPT | Same report done the same way every month | M | Should | Planning work repeats monthly |
| G4 | **Team memory you can see and edit** ("FY starts April", "Prince owns pricing"), scoped by permission | Asana, ClickUp, ChatGPT, Claude, Glean, Viktor | Max stops asking the same things | M | Should | Strong "teammate" signal |
| G5 | **Numbers from spreadsheets computed, not guessed** (sandbox) | Copilot Analyst, Glean sandbox, Gemini Data Insights | Correct totals, variances | M | Should | Planning team lives in Excel; LLM maths is risky |
| G6 | **Deep research report** (multi-step, web + internal, cited) | Copilot Researcher, Gemini, ChatGPT, Glean | Market/competitor briefs | M | Should | Extends U19 |
| G7 | **Goal to plan**: "launch by 15 Jan" becomes steps, owners, dates (then U17 chases) | Planner Agent, Slack kickoff, Rovo | Plans that get followed | M | Should | Core for planners |
| G8 | **Plan preview** before a multi-step action, one approval | Rovo Max mode, Gemini checkpoints, Glean preview | No surprise chains | S-M | Should | Fits L3 cards |
| G9 | **Reviewer approves digest/status** before it posts | Teams Channel Agent | Manager controls tone | S | Should | U25 posts unseen today |
| G10 | **Undo** Max's last action/post | Notion version history | Safe to let it act | S | Should | Lowers fear of L2/L3 |
| G11 | **Prompt-injection guard** for web pages, files, MCP | Notion, Gemini Agent Gateway | Stops hidden instructions | S-M | Should | U19/U20 open this risk |
| G12 | **Snooze / mute** per person and channel | Geekbot; general pattern | Control over pings | S | Should | In market scan, never made a U |
| G13 | **Answer in the asker's language (JA/EN)** | Moveworks (100+ languages) | Tokyo team | S | Should (Must if demo data is Japanese) | Channel Agent is weak here |
| G14 | **Starter prompts / command menu** | Copilot org prompts, Slack skill library | People find what Max can do | S | Should | Helps first-time demo viewers |
| G15 | Agent inbox (pending approvals, jobs, errors) | Gemini Inbox, Slack tasks tab | One place to manage | M | Later | Cards in chat enough now |
| G16 | Long-running background tasks with progress | Gemini, Cowork, ChatGPT Work | Big jobs | L | Later | |
| G17 | More triggers: new file, email, keyword, "monitor for changes" | Notion, ClickUp, ChatGPT, Dust, Rovo | Nothing missed | M | Later | Same as F10 |
| G18 | Daily channel recap (opt-in) | Slack recaps | Light catch-up | S | Later | U2 + U25 cover it |
| G19 | Meeting summary approve/reject window before it becomes knowledge | Teams Channel Agent | Confidential meetings | S | Later | U24 covers owners |
| G20 | Interactive dashboards / forms in chat | Dust Frames, Gemini A2UI, Glean | Live numbers | M-L | Later | After U22 |
| G21 | Canvas co-editing with Max | Glean, Gemini, ChatGPT | Draft together | L | Later | Document Agent project |
| G22 | Max reachable from Copilot/Claude via MCP | Rovo MCP server, Sana, monday | Use Max anywhere | M | Later | |
| G23 | Usage dashboard, agent inventory | Rovo, Notion, Copilot, Claude | Admin oversight | M | Later | One agent only |
| G24 | Suggests automations it noticed | Viktor, Claude smart reports | Discovery | M | Later | |
| G25 | Email triage, browser computer use, no-code agent builder, CRM, model picker | Glean, Lindy, Cowork, all builders, Slack | Breadth | L | Skip | Off-mission or against model rule |

## 3. Where Max is ahead

- **Closed-loop chasing** with private escalation, limits, working hours. Others only draft or report.
- **Owner confirms each action item** (U24); others just assign.
- **Decisions log with source links** (U23).
- **L0-L4 levels with a never-list**, set per tool. Most offer only per-tool approval.
- **Audience-safe answers**: search filters to what everyone seeing the answer may see.
- **One Teams teammate** for channel, meetings, tasks, any channel. Channel Agent is preview, one channel, no private channels, needs a Copilot licence.
- **Predictable cost** (about $0.01 per question) vs credit meters that pause agents.

## 4. Five complaints to avoid

1. **Meters that silently stop the agent.** Notion agents pause when credits run out; Rovo users blocked "at credit limit" with little use ([community](https://community.atlassian.com/forums/Rovo-questions/I-AM-DISAPPOINTED-You-ve-reached-your-Rovo-Dev-credit-limit/qaq-p/3201903)); 15 Slackbot messages a week reported on Business+ ([TechConcepts](https://techconcepts.org/blog/is-slack-ai-worth-it), unverified). Max: say clearly when a limit is hit (G1).
2. **Assumptions stated as facts, half-finished work.** Copilot "creating more work than it saves" ([forum, Aug 2026](https://techcommunity.microsoft.com/discussions/microsoft365copilot/after-a-week-of-heavy-use-microsoft-365-copilot-is-creating-more-work-than-it-sa/4551358)). Max: citations, "I couldn't find this", say what is missing.
3. **Wrong meeting summaries.** Microsoft confirmed some users saw incorrect Teams custom summaries (Apr 2026, [notice](https://mc.merill.net/message/MC1275312/compare/2026-06-10T16-14-11-797Z/2026-04-29T16-42-51-32Z), unverified detail). Max: transcript links + owner confirm.
4. **Creepy or pushy agents.** Slack's screen-watching desktop agent raised privacy worries ([TNW](https://thenextweb.com/news/slack-slackbot-30-ai-features-agentic)); agents that DM everyone or leak exec-channel context get security pushback ([talk](https://www.ai.engineer/talks/viktor-ai-coworker-that-lives-in-slack)). Max: agreed triggers only, channel-scoped knowledge.
5. **Inconsistent or irrelevant results.** Glean reviewers report inconsistent or irrelevant results ([Gartner](https://www.gartner.com/reviews/market/enterprise-search-engines/vendor/glean), [G2](https://g2.com/products/glean-technologies-glean/reviews)). Max: fixed note templates, the 40-question test before demo.
