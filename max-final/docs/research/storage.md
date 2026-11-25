# Research: storage for Max final (25 Nov 2026)

## Headline
- **Raw + working is the right idea.** Make one change: split the data into **three** groups, not two.
  **RAW** = Teams data exactly as Graph sent it (the source of truth). **WORKING** = clean tables + search, which you can
  delete and rebuild. **APP** = Max's own data (tasks, approvals, audit log). APP cannot be rebuilt, so back it up.
- **SQLite now, in one small `store` module, using plain SQL.** Do not use an ORM. The move to the central database will
  most likely be an *export of RAW JSON*, not running Max on their database.
- **Keep both the original file bytes and the extracted text.** Bytes go in a folder, text goes in the database.
- **Max reads data through search tools, not big context dumps.** Start with FTS5 keyword search. Add a small local
  embedding model later, only if tests show keyword search misses things.

## 1. The three layers and a simple schema

Problems with "raw + working" as first proposed, and the fixes:

| Problem | Fix |
|---|---|
| Change notifications often hold only an id, not the full object | Notifications only **wake the sync**. RAW stores only full objects fetched from Graph |
| Append-only RAW keeps deleted text forever, which breaks "deletes honoured" | A purge job removes old versions' content and keeps a tombstone (id + time) |
| Rebuilding file text needs the original file | Keep the file bytes too |
| Max's own data (tasks, approvals) is not Teams data | Put it in a separate APP group that is never rebuilt |

**RAW** (append-only, boring on purpose):

| Table | Key columns |
|---|---|
| `raw_items` | `seq` (auto), `kind` (message / reply / file / meeting / transcript / person / channel), `graph_id`, `parent` (team/channel/drive), `etag`, `content_hash`, `deleted` (0/1), `source` (backfill / delta / notify / poll), `fetched_at`, `json`, `blob_sha` (files and VTT only). **UNIQUE(kind, graph_id, content_hash)**, so storing the same data twice is a no-op |
| `sync_state` | `resource` (e.g. `channel:19:abc`), `delta_link`, `last_ok_at`, `last_error`, `fails` |
| `subscriptions` | `id`, `resource`, `expires_at`, `client_state` |

**WORKING** (derived from the latest RAW version; can be dropped and rebuilt):

| Table | Key columns |
|---|---|
| `people` | `user_id`, `name`, `email` |
| `channels` | `channel_id`, `team_id`, `name`, `membership` (standard / private / shared) |
| `messages` | `(channel_id, message_id)`, `root_id` (null = a top-level post), `author_id`, `created_at`, `edited_at`, `deleted_at`, `text` (HTML turned into plain text) |
| `mentions`, `reactions` | `message_id`, `user_id`, `type` |
| `files` | `item_id`, `drive_id`, `name`, `path`, `modified_at`, `modified_by`, `blob_sha`, `text`, `deleted_at` |
| `meetings` | `meeting_id`, `subject`, `start`, `end`, `organizer_id`, `channel_id` |
| `transcript_lines` | `transcript_id`, `n`, `start_s`, `speaker`, `text` |
| `chunks` (FTS5) | `kind`, `ref`, `channel_id`, `at`, `title`, `body` |
| `projector_state` | `last_raw_seq`: WORKING is updated by processing RAW rows with `seq > last_raw_seq` |

**APP**: `tasks`, `runs`, `audit`, `approvals`, `policies`, `jobs`. The old prototype's tables work well here.

## 2. Database choice

| | SQLite now | PostgreSQL now |
|---|---|---|
| Setup on the office laptop | None, built into Python (FTS5 + JSON checked) | Windows service, may need IT |
| Search | FTS5 built in | Built-in full-text search, also fine |
| Concurrency | One writer at a time (enough for one bot) | Many writers |
| Matches the central DB? | No | Maybe. It could also be SQL Server |

**Pick SQLite.** Keep switching cheap like this:
- Put all SQL in one `store` package (`raw.py`, `working.py`, `search.py`). Nothing else writes SQL.
- Use portable SQL: `TEXT`/`INTEGER`, ISO-8601 UTC times as text, JSON as text. `INSERT … ON CONFLICT DO UPDATE`
  works in SQLite and Postgres. SQL Server needs `MERGE`, which is one function to rewrite.
- Only search is engine-specific, so keep it alone in `search.py`.
- Add an **export command** that writes RAW as JSONL. That is the contract for the central project, whatever database
  they choose.
- Use WAL mode and `busy_timeout`, and keep transactions short. Have one sync worker do all writes, so you never see
  "database is locked".

SQLAlchemy Core still needs per-dialect upsert code, so it is not worth a dependency for ~30 queries.

## 3. Sync: keeping up with Graph

| Data | Backfill | Keep up to date | Deletes |
|---|---|---|---|
| Channel posts and replies | `channels/{id}/messages/delta?$expand=replies` (last ~8 months); older posts via list messages + list replies | Subscription on the channel's messages (wake-up) → run delta for that channel | Message comes back with `deletedDateTime` set |
| Reactions and mentions | Part of the message JSON | Arrive as message updates | – |
| Files (docx/xlsx/pdf) | `drives/{id}/root/delta` | driveItem subscription (root, `updated` only) → delta; download only when `cTag` changes | `deleted` facet |
| Meetings and transcripts | Transcript list/delta per organizer; content as `text/vtt` | callTranscript subscription; it arrives minutes after the meeting | Mark as deleted |
| People | Team members list | conversationMember subscription + daily refresh | Mark as left |

What breaks, and the fix for each:
- **Missed or duplicate notifications** (Graph delivers at least once, sometimes out of order, sometimes not at all).
  Fix: every notification only triggers a delta run, writes are idempotent, and a **safety poll runs delta every
  ~15 min** anyway.
- **A new reply may not change the parent post's `lastModifiedDateTime`** (community report). Fix: fetch the reply from
  its own notification, and re-list replies of threads active in the last 14 days on each poll.
- **Delta link expired** (`410` / `resyncRequired`). Fix: restart a full delta for that resource. Idempotent upserts
  make this safe.
- **Save the delta link only after all pages are stored and committed.** A crash then just repeats work and never
  skips anything.
- **Throttling** (`429`/`503`). Fix: retry with backoff and respect `Retry-After`.
- **Teams subscriptions expire after at most 3 days.** Fix: renew daily. A `lifecycleNotificationUrl` is required when
  a subscription lasts over 1 hour. Handle `missed` with a delta run and `reauthorizationRequired` by reauthorizing.
- **The webhook must answer fast.** Fix: check `clientState`, queue it, return `202`.
- Metered billing for Teams export APIs ended 25 Aug 2025, so there is no cost blocker.

**The simulator must be just as unkind**: duplicates, wrong order, a dropped notification, a `429`, an expired delta
link. Otherwise the demo works and real Graph breaks.

## 4. Files

**Store both.** Bytes go to `data/blobs/ab/abcdef…` (named by SHA-256, so the same file is stored once). Text goes into
`files.text` and `chunks`. Why: you can re-extract later with a better tool, the central project may want the
originals, and you keep a full rebuild from RAW. Keep bytes out of the database so it stays small and backups stay
easy. Store transcript VTT as a blob too.

| Format | Library | Note |
|---|---|---|
| docx / xlsx / pdf / pptx | **MarkItDown** (Microsoft, MIT, v0.1.9). Install only the `[docx,xlsx,pdf]` extras | Outputs Markdown, which works well for LLMs. Give it local files only |
| Fallbacks | `python-docx`, `openpyxl`, `pypdf` (BSD) | Small and stable |
| Avoid | PyMuPDF | AGPL licence, risky in a company |
| VTT | Own ~20-line parser (`<v Speaker>` tags) | – |

Scanned PDFs have no text and there is no OCR. Mark them "no text" and do not crash.

## 5. How Max reads the data

Use **tools, not dumps**. Each answer pulls a few relevant pieces, which keeps Qwen fast and the answers cited.

| Tool | Returns |
|---|---|
| `search(query, kind?, channel?, person?, since?)` | Top 8 snippets with ids and dates |
| `get_thread(message_id)` | The post and its replies |
| `read_file(file_id, part?)` | One section of the file text |
| `get_transcript(meeting_id, from?, to?)` | A window of transcript lines |
| `recent(channel?, since)` | Latest activity |
| `who(name)` | Person details |

**Search:** FTS5 with BM25 (it worked in the prototype). Cheap upgrade: let Qwen rewrite the question into 2–3 keyword
queries. **Local embeddings:** `fastembed` (v0.9.1, ONNX, CPU) with `BAAI/bge-small-en-v1.5` (384 dimensions, about
130 MB). Expect a few ms per query and minutes for a full re-embed at team scale; measure it on this laptop. Store
vectors as BLOBs and compare with numpy. That stays fast below about 100k chunks, so `sqlite-vec` (still 0.1.x) is not
needed. **Recommendation:** ship FTS5 first, build a 30-question test set, and add embeddings (hybrid search) only if
paraphrased questions fail. Per the rules, a local model needs Karthi's OK first.

## 6. Privacy basics
- **Deletes:** WORKING hides the item at once. A purge job clears the content of deleted items in RAW (and their
  blobs) after N days (proposed: 7) and keeps only a tombstone.
- **Retention:** keep the latest version of everything. Purge older edit versions after 90 days. Follow company Teams
  retention when real.
- **Who sees what:** filter search by channel membership. Private and shared channels, and transcripts, are visible
  only to their members or attendees.
- **Secrets:** `.env` only. The DB and blobs live in `data/` (not in git). The laptop disk should be BitLocker
  encrypted. Never log message bodies.

## Top 5 risks

| # | Risk | Could it break the demo? | Mitigation |
|---|---|---|---|
| 1 | Missed updates (lost notifications, replies, 8-month delta window) → stale answers | Yes | Safety poll, reply re-scan, nightly reconcile |
| 2 | Deleted or edited text still answered | Yes, embarrassing | Search only the latest non-deleted rows; purge job; test it |
| 3 | Private channel or meeting content leaks to the wrong people | Later, serious | Membership filter inside `search` |
| 4 | Simulator kinder than real Graph | Not the demo, but the go-live | Fault injection in `teams_sim` |
| 5 | Central DB is unknown (Postgres or SQL Server) and the use case is undecided | No | RAW JSON + JSONL export; WORKING is disposable |

## Sources
- [chatMessage delta (8-month window, $top 50)](https://learn.microsoft.com/en-us/graph/api/chatmessage-delta)
- [List channel messages / replies](https://learn.microsoft.com/en-us/graph/api/channel-list-messages)
- [Replies not bumping parent in delta (community)](https://techcommunity.microsoft.com/t5/microsoft-graph/msteams-chatmessage-delta-doesn-t-pick-up-replies-as-changes/td-p/2755527)
- [Subscription lifetimes, lifecycle URL, latency](https://learn.microsoft.com/en-us/graph/api/resources/subscription)
- [Lifecycle notifications](https://learn.microsoft.com/en-us/graph/change-notifications-lifecycle-events)
- [Teams API billing ended 25 Aug 2025](https://learn.microsoft.com/en-us/graph/teams-licenses)
- [driveItem delta](https://learn.microsoft.com/en-us/graph/api/driveitem-delta)
- [MarkItDown](https://github.com/microsoft/markitdown) · [fastembed](https://github.com/qdrant/fastembed) ·
  [SQLite FTS5](https://www.sqlite.org/fts5.html)
