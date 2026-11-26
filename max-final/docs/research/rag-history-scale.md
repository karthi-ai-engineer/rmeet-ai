# Research: how much history Max reads, and how it scales (26 Nov 2026)

Unverified items are marked **(?)**. Numbers marked "est." are our own estimates; measure them on the laptop.

## Headline
- **Do not index everything at install, and do not start from zero either.** Use **tiers**: read the last
  **12 months** fully (default, a setting), keep **all older messages keyword-searchable**, list **all files by name**,
  and open old files or meetings **only when someone asks**.
- **Messages are cheap; files and embeddings are expensive.** 100k messages is only ~6M tokens and ~35 min of
  Graph calls. Most of the time, disk and money go into files and embeddings.
- **Read newest first.** Max is useful within minutes, and what it has read is always one unbroken range,
  "today back to date X". That date is Max's **knowledge horizon**, and Max shows it, like an LLM's knowledge cutoff.
- **The Microsoft Search API is not a shortcut for Max.** Searching Teams messages works only for a signed-in user
  (delegated). App-only search covers files only and needs tenant-wide `.All` permissions, which we decided not to ask for.

## What comparable products do

| Product | History and speed | What we take |
|---|---|---|
| M365 Copilot | Microsoft owns the index: all history, permission-filtered. New files up to ~48 h (community **(?)**) | Only the host indexes everything for free |
| Teams Channel Agent (preview) | Channel messages + files. Recurring meetings: **1 earlier transcript + 28 days of chat**. Removed = zero state | Even Microsoft limits history |
| Notion AI connectors | Slack: **1 year back**; first sync **up to 36 h**; new messages **up to 3 h** | 1-year window is normal |
| Glean | All, with optional **max age** and team/channel allowlists. Admin sees crawl rate + "estimated 2 days" | Progress + ETA |
| Atlassian Rovo (Teams) | "**Limit by date**" at setup, **can't change later**. Files: metadata only | Window yes, but extendable |
| Dust (Slack) | Only from when the bot joined (Slack limit) | "Live only" is a limitation |
| Slack AI / Slack API | Slack AI uses Slack's own full search. Since May 2025 outside apps get 1 call/min on history and a **Real-time Search API** | Trend: search old content live, don't copy it all |

## 1. Options compared
Example team: 100k messages, 2,000 files, 200 one-hour transcripts, ~4 years old. Sizes (est.): messages ~6M tokens,
files ~10M, transcripts ~2.4M, so **~18M tokens, ~50k chunks**. File bytes ~2–4 GB. A 12-month window ≈ 25% of this.

| Option | Time until done (laptop, est.) | Gemini cost | Disk | Accuracy | Verdict |
|---|---|---|---|---|---|
| A. Everything at install | 3–6 h; Max not ready until the end | ~$3.70 embeddings (~$1.85 batch), +~$3 if summaries | 3–5 GB | Best recall, but lots of stale old content competing with current content | No |
| B. Newest-first, everything | Same total, but **useful after ~5–10 min** | Same as A | 3–5 GB | Same as A | Good order, too much volume |
| C. 12-month window + older on demand | ~1 h | ~$1 | ~1 GB | Great for recent. Old content is invisible until someone asks | Close |
| D. Live only, from install day | 0 | $0 | ~0 | Day 1: knows nothing. "What did we decide in March?" fails | No |
| **E. Tiered** (hot / warm / cold) | ~1–1.5 h in the background, useful in minutes | **~$1** | **~1.3 GB** | Near A for most questions. Old files take 5–30 s the first time | **Recommended** |

Tiers in E:

| Tier | What | Stored |
|---|---|---|
| **Hot** (last 12 months) | Messages, file text, transcripts | Full chunks + keyword index + embeddings; file bytes kept |
| **Warm** (older) | All older messages; a list of all files and meetings | Messages: keyword index only (no embeddings). Files and meetings: name, path, author, date, size |
| **Cold** (fetched when asked) | Text of old files, old transcripts | Downloaded and read on request, then kept as hot |

Graph check: list channel messages = **1 call/s per channel, 20/s per app per tenant**, 50 posts per page with
replies, **newest activity first** (suits backfill). 100k messages ≈ 2,000+ calls ≈ **~35 min** in one channel.
Delta covers only **8 months**, so older posts come from list messages anyway.

## 2. Recommended default and settings
**Default:** tier E, newest first, 12-month hot window.

First-run setup (team lead, one screen):

| Setting | Choices | Default |
|---|---|---|
| How far back should Max read fully? | 3 months / **12 months** / everything | 12 months |
| Channels | Pick channels. Private channels only if Max is added there | All standard channels |
| Files | **Recent + linked + asked for** / all files | Recent + linked |
| Older messages | Keyword-searchable / skip | Keyword-searchable |

Setup shows an estimate before it starts: "About 1 h, ~$1, 1.3 GB." The window **can be extended later**, which Rovo
does not allow.

**Many teams:** one backfill queue, **round-robin across teams, newest first**, so a new team gets its last week read
within minutes. 10 such teams (est.): E ≈ 13 GB, ~10–15 h background, ~$10; A ≈ 30–50 GB, 30–60 h. Vectors are
searched per team; `sqlite-vec` past ~100k chunks; past a few big teams, move to the central server.

## 3. The "knowledge horizon" UX
Store one row per channel and kind: `coverage(channel, kind, read_back_to, state, updated_at)`. Graph gives no message
counts, so progress is **by time**: (today − read_back_to) ÷ (today − channel created date).

| Where | What Max says |
|---|---|
| Welcome after install | "Hi Planning! I'm reading your history, newest first: back to **18 Nov 2026** so far, 12 months in about an hour. Older messages I can keyword-search; older files I open when asked." |
| "What have you read?" (card) | Messages: fully read back to **1 Dec 2025** ✓ (older: keyword only). Files: 412 read, 1,588 listed. Meetings: 48 transcripts since Dec 2025. Up to date: 1 min ago. **[Read further back]** |
| In an answer (only when needed) | "Note: I've only fully read Planning back to **1 Dec 2025**. **[Search older]**" |
| While reading | "Still reading Planning (40%, back to 3 Jun 2026)." |

Rules (in code): show the horizon line only when (a) the question names a time before the horizon, (b) search found
little while reading still runs, or (c) the best source is warm or cold. Never on every answer. "Read further back"
(team lead) becomes a job with a time and cost estimate, through the normal approvals. "Search older" (anyone) is a
one-off live fetch. Products show progress **to admins only** (Glean, Rovo, Notion). Showing it to users in answers
would be new **(?)**.

## 4. Files
- **Read text of:** files changed in the last 12 months; files **linked or attached** in any read message (any age);
  files someone asks about. **List all files** (cheap metadata via drive delta).
- **Types first:** docx, pptx, xlsx, text PDFs; then txt, md, csv. Skip video, audio, zip, exe, images, scanned PDFs
  ("no text").
- **Limits (proposed):** skip over **50 MB**; read at most **~200k tokens**, then outline + "partly read"; xlsx: sheet
  summary + first 5,000 rows. Current version only; same hash = read once.
- **File bytes only for hot files** (cold ones are re-downloaded). Saves gigabytes; slightly changes `storage.md`.

## 5. Microsoft Search API as a way to reach old content
| Entity | App-only (bot) | Delegated (signed-in user) |
|---|---|---|
| chatMessage (Teams messages) | **Not supported** (only delegated scopes listed) | Yes, filtered to that user's access |
| driveItem / listItem / site (files) | Yes, but needs `Files.Read.All` / `Sites.Read.All` (**tenant-wide**). `region` is required; OneDrive content is left out by default; paging stops around 1,000 | Yes |

So for R1: **no**. Maybe later, in the 1:1 chat, with the user's own sign-in (SSO + on-behalf-of), needing admin
consent **(?)**. The cold path = **direct Graph reads under team consent (RSC)**. Old meetings: transcript permission is
meeting-scoped, so **transcripts from before Max joined may be unreachable** **(?)**. Check on the real tenant.

## 6. Top risks
| # | Risk | Fix |
|---|---|---|
| 1 | Outdated content outranks current | Recency boost, dates on snippets, newest wins |
| 2 | False "I don't know" (content older than horizon) | Warm keyword index of all messages, horizon line, [Search older] |
| 3 | Laptop overloaded | Low-priority jobs, pause while answering, resumable, disk estimate first |
| 4 | Throttling, 8-month delta window | `Retry-After`, 1 call/s per channel, list messages for older, save cursor after commit |
| 5 | Cost and disk grow with teams | Embeddings and file bytes only for hot; budget in `gemini_cost` |
| 6 | Old deleted content comes back | Same delete/forget pipeline for every tier |
| 7 | Simulator too small to show speed issues | One synthetic 100k-message team for a performance test |

## Sources
- [Graph throttling limits (Teams section)](https://learn.microsoft.com/en-us/graph/throttling-limits) ·
  [List channel messages](https://learn.microsoft.com/en-us/graph/api/channel-list-messages) ·
  [chatMessage delta (8 months, $top 50)](https://learn.microsoft.com/en-us/graph/api/chatmessage-delta)
- [Search API overview (entity types, paging)](https://learn.microsoft.com/en-us/graph/api/resources/search-api-overview) ·
  [search/query permissions](https://learn.microsoft.com/en-us/graph/api/search-query) ·
  [App-only search needs region](https://learn.microsoft.com/en-us/graph/search-concept-searchall)
- [Teams Channel Agent setup (knowledge, 28 days, zero state)](https://learn.microsoft.com/microsoftteams/set-up-channel-agent-teams)
- [Semantic index for Copilot](https://learn.microsoft.com/en-us/microsoftsearch/semantic-index-for-copilot) ·
  [Index timing (community)](https://techcommunity.microsoft.com/discussions/microsoft365copilot/copilot-semantic-index-data-refresh/3967419)
- [Notion AI connectors](https://www.notion.com/help/notion-ai-connectors) ·
  [Notion Slack connector](https://www.notion.com/help/notion-ai-connectors-for-slack)
- [Glean crawling FAQ](https://docs.glean.com/connectors/crawling-faq) ·
  [Glean Teams restrictions](https://docs.glean.com/connectors/native/teams/restrictions) ·
  [Glean sync monitoring](https://docs.glean.com/connectors/connectors-monitoring)
- [Rovo: connect Microsoft Teams](https://support.atlassian.com/organization-administration/docs/connect-microsoft-teams-to-teamwork-graph/)
- [Dust Slack connection](https://docs.dust.tt/docs/slack-connection)
- [Slack May 2025 rate limit and terms change](https://api.slack.com/changelog/2025-05-terms-rate-limit-update-and-faq) ·
  [Slack Real-time Search API](https://api.slack.com/changelog/2026-02-real-time-search-api) ·
  [Security for AI features in Slack](https://slack.com/help/articles/28310650165907)
- Our own: `docs/research/knowledge.md`, `storage.md`, `teams-access.md`, `docs/plans/06-memory.md`
