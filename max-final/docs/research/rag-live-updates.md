# Research: keeping Max's search index live and correct (26 Nov 2026)

## Headline
- **"Always perfect" can't be guaranteed on top of Graph.** Graph can drop notifications for good (a slow endpoint, or
  being offline for more than 4 h). Its stated maximum delays are 1 min for messages, 60 min for members and 6 h for files.
  What we **can** promise:
  1. Once Max knows about an edit or a delete, the old text never appears again.
  2. Max always knows how far behind each source is, and says so.
  3. A daily check proves the index matches Teams and repairs any difference, with an alert.
- **Change to `storage.md`:** Microsoft's Teams rules allow polling a resource **once per day**
  ([polling requirements](https://learn.microsoft.com/en-us/graph/api/resources/teams-api-overview#polling-requirements)),
  and the OneDrive guide says the same for a safety delta. So **drop the 15-min safety poll**. Run delta only when
  something triggers it, plus the nightly check.

## 1. The pipeline

```
webhook ─► check clientState → insert into inbox table → reply 202 (< 3 s)
                    ▼
one worker: drop duplicates, merge per resource, deletes first
                    ▼
fetch: channel delta (debounced 2 s) | GET the reply | drive delta | member list
                    ▼
ONE transaction per item: RAW (no-op if same hash) → WORKING row → delete the item's old
chunks, FTS rows and vectors → insert new chunks and FTS rows → queue embeddings
→ save the delta link last
                    ▼
embedding worker (batches of up to 100) → chunk_vectors
```

| Trigger | What runs |
|---|---|
| Notification | Delta for that channel or drive. A **reply** notification also GETs that reply directly, because a reply may not show up in delta under its parent |
| Lifecycle event (`missed`, `subscriptionRemoved`, `reauthorizationRequired`) | Fix the subscription, then delta ([lifecycle](https://learn.microsoft.com/en-us/graph/change-notifications-lifecycle-events)) |
| App start / back online | Renew subscriptions **first**, then delta for every resource |
| Nightly | Reconcile (section 3) |
| 410 on delta | Full re-enumeration. Items not seen in it are marked deleted. The old index keeps serving meanwhile |

**Safe with duplicates and wrong order:**
- Apply a version only if its Graph `lastModifiedDateTime` is newer than the stored one.
- A delete is a tombstone. Only a newer version brings the item back.
- RAW stays `UNIQUE(kind, graph_id, content_hash)`.
- Hash only the indexed text. A reaction updates metadata and causes no re-chunk or re-embed.

**Rich (encrypted) notifications** carry the full message, but need a certificate, decryption and token checks
([docs](https://learn.microsoft.com/en-us/graph/change-notifications-with-resource-data)), and files don't support them.
**R1: id-only notifications plus delta** (one simple path). Add rich notifications later only if measured latency needs it.

## 2. Realistic freshness targets

Graph latencies come from the [subscription docs](https://learn.microsoft.com/en-us/graph/api/resources/subscription).

| Change | Target (p95) | Graph latency (average / max) |
|---|---|---|
| New post, reply or edit | **≤ 30 s** (typically 10–15 s) | <10 s / 1 min |
| Delete | ≤ 30 s. Processed first, hidden < 1 s after we know | same |
| Member removed | ≤ 30 s, **plus a live check when answering** | <10 s / **60 min** |
| Channel renamed | ≤ 1 min (names are joined at query time, so nothing is re-chunked) | <10 s / 60 min |
| File new or changed | **≤ 5 min** (60 s quiet period for co-editing, then extract) | <1 min / **6 h** |
| Transcript | ≤ 5 min after Teams publishes it (minutes after the meeting) | <10 s / 240 min |
| Anything missed | Next nightly reconcile | – |

Graph limits that shape this:
- **Webhook:** reply within 3 s. Graph retries for up to 4 h. If more than 10% of replies are slow, notifications are
  delayed by 10 min; above 15%, they are **dropped**
  ([webhooks](https://learn.microsoft.com/en-us/graph/change-notifications-delivery-webhooks)).
- **Subscriptions:** Teams subscriptions last at most 3 days; drive subscriptions about 30 days.
- **Throttling:** GET channel messages is limited to 1 request per second per channel
  ([limits](https://learn.microsoft.com/en-us/graph/throttling-limits)).

**Permissions must not lag.** Before an answer uses private or shared channel content, check that channel's members
live (one GET, cached 60 s). If the check fails, leave the content out.

## 3. Proving the index is correct

| Check | When | How |
|---|---|---|
| Reconcile with Teams | Nightly | Compare `(id, lastModified or cTag, deleted)` per channel, drive and member list. Fix any differences. **Drift** = number of items fixed. Target 0; any drift becomes a test |
| Internal consistency | After catch-up, and nightly | Every live item has chunks. Deleted items have no chunks or vectors. FTS row count = chunk count. Vectors use the current model |
| Canary | Every time Max posts | Max's own post must come back as a notification within 60 s. If not, mark the source "suspect" and run delta |
| Older than 8 months | Monthly | Delta only covers 8 months, so list older messages |

**Health view, one row per source:**
- last notification and last sync
- lag (age of the oldest pending change)
- items pending and embeddings pending
- errors
- subscription expiry
- last drift count
- status: green, yellow or red

**Alerts to the admin:**
- a subscription renewal fails
- lag is over 5 min
- drift is above 0
- a 410 happens
- the embedding backlog is older than 30 min

**Others:**
- Glean mixes webhooks, scheduled crawls and live fetch, and states that its update rate is **not a time-to-search
  guarantee** ([refresh rates](https://docs.glean.com/connectors/crawling-refresh-rates)).
- Copilot connectors use incremental crawls (every 15 min to every few hours) plus a daily full crawl, and the
  incremental crawls **don't update permissions** ([setup](https://learn.microsoft.com/microsoftsearch/configure-connector)).

Max's plan is at least as strict as both.

## 4. Edge cases

| Case | Handling |
|---|---|
| Reply doesn't change its parent | GET the reply directly. The nightly check re-lists replies of threads active in the last 14 days |
| File edited while being indexed | Commit only if the `cTag` from the download is still the newest; otherwise redo |
| Huge file | Cap at 50 MB / 500 pages and mark "partly indexed". Extract in a subprocess with a timeout, outside the transaction |
| Moved or renamed | Track by id. Delta skips children of a renamed folder ([driveItem delta](https://learn.microsoft.com/en-us/graph/api/driveitem-delta)), so build paths from parent ids |
| Private channel files | Each private channel has its own SharePoint drive, so it needs its own subscription |
| Deleted, then restored | Tombstone first. The restore arrives as a newer version, so it is re-indexed. If already purged, fetch it again |
| 404 or 403 on fetch | Hide the item |
| Offline for hours | On start: renew subscriptions, then catch up with delta. Answers say "catching up" |
| Delta token expired (410) | Re-enumerate, then mark and sweep. Keep serving the old index meanwhile |

## 5. Embeddings
- **Re-embed only what changed.** Chunk id = hash(item, text), so unchanged chunks keep their vectors. One edited page
  re-embeds 1–2 chunks.
- **No stale text, ever.** Old vectors are deleted in the same transaction as their chunk. A new chunk is found by
  keyword search at once and by meaning search seconds later.
- **Batching:** up to 100 chunks or every ~2 s through the online API. The batch API is only for backfill.
- **Cost:** about 0.1M tokens/day × $0.20/M ≈ **$0.02/day**, metered through `gemini_cost`.
- **If embeddings lag,** hybrid search still returns keyword hits. Max only adds "as of hh:mm" when the **sync** lag of
  a source it used is over 2 min.

## 6. What the simulator must fake, and the tests
**Faults:**
- duplicate, out-of-order, dropped and delayed notifications
- webhook down for N hours
- slow and drop throttling modes
- `429` with `Retry-After`, `503`, `410`
- the three lifecycle events, and subscriptions expiring

**Data quirks:**
- a reply missing from delta
- a `cTag` that changes mid-download
- a huge file and a scanned PDF
- a folder rename
- member removal and channel rename
- soft delete and undo
- a 404 item
- a late transcript

**Tests (e2e, free):**
1. A new post is found within the target. After an edit, the old words give no hit.
2. A delete is gone from FTS, vectors and the open tools. Undo brings it back.
3. Duplicated and shuffled notifications produce the same index.
4. A dropped notification is repaired, and reconcile reports the drift.
5. A 410 resync leaves no lost or ghost items, and answers keep working during it.
6. Offline for 6 h, then restart: the index catches up and the health view goes red → green.
7. A removed member gets no private content in the next answer.
8. A file edited during extraction ends at the newest version.
9. Only changed chunks are re-embedded. Keyword search works with embeddings off.
10. A 429 storm: `Retry-After` is honoured and the queue drains.
11. **Convergence (the proof):** 10 min of random events with all faults on, then catch-up. The index must equal the
    simulator's ground truth (per-channel counts and hashes).

## Unverified (check on a real tenant)
- Whether a channel soft delete arrives as `updated` or as `deleted`. Subscribe to all three types and treat each one as
  "go fetch".
- Whether reactions always trigger `updated`.
- Which bot events (edit, delete, rename, member removed) arrive without an @mention when RSC is used.
- Whether "poll once per day" applies per resource or per app. The design never polls.
