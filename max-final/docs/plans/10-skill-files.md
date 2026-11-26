# Max: skill files list (topic 8)

**Status: ✅ AGREED (26 Nov 2026): all 11; meeting brief stays in chat R1.** Which task types get a skill file (a short how-to: steps, output format,
examples), loaded only for that task. **Writing them comes later**, during the build. Modes and the rule are in
`04-agent-design.md` §12. Max Meeting has its own skills later (`meeting/`).

**Always loaded, not a skill:** `base.md` = personality and answer style (`08-personality.md`) + the 13 rules.
**No skill needed:** quick replies (thanks, clarify, refuse): `base.md` covers them.

| # | Skill file | Mode | Covers | Requirements |
|---|---|---|---|---|
| 1 | `answer.md` | loop | Questions from team knowledge: chats, files, sheets (numbers by code), conflicts, not found | A-1, U1 U3 |
| 2 | `catch_up.md` | loop | "What did I miss?", summarise a thread or a period | A-2, U2 |
| 3 | `decisions.md` | loop | "What have we decided about X?", recording a decision, replacing an old one | A-3, U23 |
| 4 | `email.md` | loop | Write an email to people inside the company; follow-up after a meeting | E-1, E-2 |
| 5 | `meetings_booking.md` | loop | Find free time, book / move / cancel a meeting | E-3 |
| 6 | `reminders.md` | loop | "Remind me…", repeating jobs: understand the time, repeat it back with the time zone | P-5 |
| 7 | `memory_requests.md` | loop | "What do you know about me?", correct a fact, forget something, a person's correction → lesson | memory Parts 3-5 |
| 8 | `plan.md` | plan, then act | Goal → plan with tasks, owners, dates; multi-step actions | P-1, U31 |
| 9 | `weekly_digest.md` | workflow | Write the Monday digest from code-gathered facts | P-6 |
| 10 | `chase.md` | workflow | Write chases and plan-owner notes (kind, no blame, bundled) | P-4 |
| 11 | `meeting_brief.md` | workflow | Write the brief before a meeting from calendar + open items | M-1 |

Rule (agreed 25 Nov): requests that match no skill use general answer mode and are logged, to decide later skills.
