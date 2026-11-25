# Research: how Max finds answers in a big team (25 Nov 2026)

## Headline
- **Search first, then open only what is needed.** The agent reads short snippets, then opens one thread, file section or transcript time range if it needs more.
- **Your idea is good: it is the "open" step of this design.** One change: the **agent decides** when to open a file (a tool), never automatic. Small files go whole, big files one section at a time.
- **Step 1:** keyword search (FTS5). **Step 2:** add embeddings, but only if the test set shows that keyword search misses things.
- **Cost:** about **$0.005–0.01 per question**. The first backfill costs **under $1**.

## 1. Options compared

| Option | Cost per question | Speed | Accuracy | Complexity | Verdict |
|---|---|---|---|---|---|
| Keyword search (FTS5 / BM25) | Free | ~10 ms | Good for names, numbers, file names. Misses synonyms ("price" vs "cost") | Built into SQLite | **Start here** |
| Vector search (embeddings) | ~Free | 10–300 ms | Good for paraphrased questions, weak on exact ids | Medium: needs a model and re-embedding when content changes | Add if tests need it |
| Hybrid (both, merged with Reciprocal Rank Fusion) | ~Free | Sum of both | Best of both. Usually the most reliable | Medium: about 20 lines on top of both | **Step 2** |
| Rerank (LLM call, or local cross-encoder ms-marco-MiniLM, 80 MB) | +1 call, or free | +0.5–2 s | Small gain: the agent already picks from the snippets | Low | Skip unless tests need it |
| Long context ("send everything") | $0.25+ per question | 20–60 s | Worse on big inputs. A real team (~3M tokens) does not fit in 1M | Very low | **No** |
| Gemini context caching | Storage $1 per 1M tokens per hour (~$24/day). Any edit breaks the cache | Faster | Same as long context | Medium | **No**. Implicit caching of our fixed system prompt is free and automatic |
| Gemini File Search (Google-hosted RAG) | $0.15/M to index | Fast | Good, but ranking is hidden | Hard to test. Deletes and permissions must be mirrored in Google | No |
| **Agentic retrieval** (search tools, then open full items) | ~$0.005–0.01 | 3–8 s | High, and every answer has citations | Medium: just plain Python tools | **The design** |

Embedding models we may use:

| Model | Price | Notes |
|---|---|---|
| `gemini-embedding-2` | $0.20/M ($0.10 batch). Free tier exists | 8k-token input, 128–3072 dims (use 768), multilingual |
| `gemini-embedding-001` | $0.15/M | Text only, 2k input. Vectors not compatible with v2 |
| Local `bge-small-en-v1.5` (fastembed 0.9.1) | Free | 67 MB, 384 dims, English only, fast on CPU |
| Local `paraphrase-multilingual-MiniLM-L12-v2` | Free | 220 MB, multilingual, weaker. (`bge-m3` is not in fastembed: skip) |

**Pick:** `gemini-embedding-2` if you allow it (better, multilingual, ~$0.60 for the whole team). If not, bge-small. Either one sits behind one `embed()` function, so a swap is just a re-embed.

## 2. Recommended design

**Chunking.** 300–800 tokens each, starting with a heading such as "Budget.xlsx › Sheet H1" so it makes sense alone.

| Content | Chunk | Kept for |
|---|---|---|
| Thread | Post plus replies as one chunk. Long threads are split into windows of replies, and the post is repeated at the top of each | `thread_id`, channel, authors, first and last date |
| docx | One chunk per heading section | file, heading path |
| pdf | One chunk per page (or several pages together if they are short). Scanned pages are marked "no text" | file, page |
| pptx | One chunk per slide, including speaker notes | file, slide number |
| xlsx | Per sheet: a summary chunk (columns, row count) plus blocks of 50 rows as Markdown tables | file, sheet, rows |
| Transcript | 2–3 minute windows that cut only at speaker changes, with 30 s overlap. Each line is "Name: text" | meeting, start and end time, speakers |
| Max's meeting notes | One chunk per meeting | They are searchable too, which makes past meetings easy to find |

**Metadata on every chunk:** `ref` (short id), kind, title, author(s), date, last changed, channel, file or meeting id, `acl` (who may see it) and a link.

**Tools.** Each tool returns short output with ids. Each has a token cap, and when the output is cut it adds a hint such as "truncated, ask for section 3".

| Tool | Returns |
|---|---|
| `search_knowledge(query, kind?, channel?, person?, since?, until?, file_id?, meeting_id?)` | The top 8: `ref`, title, where, author, date, a snippet of about 300 characters |
| `read_thread(thread_id)` | The post and its replies, with names and dates (up to ~50 replies) |
| `find_files(name?, author?, since?)` / `list_meetings(subject?, attendee?, since?)` | Metadata only, for questions like "the budget file" |
| `read_file(file_id, section?)` | No section: the outline (sections with sizes), plus the **full text if it is under ~30k tokens**. With a section: that section's text, or a sheet as a table |
| `get_transcript(meeting_id, start?, end?)` | Transcript lines with speaker and time. The whole transcript if it is under ~20k tokens (about 1.5 h) |
| `list_recent(channel?, since)` | New posts and replies (for "catch me up") |

**When to send the full document:** the question names one file or meeting ("summarise the Q1 deck"), or the snippets are not enough, and it is small (30k tokens ≈ $0.008). Otherwise outline first, then the right section. Limits: **6 tool calls, ~60k input tokens** per question. Live meetings: fast path, one search then answer.

**Citations.** The model writes ids like `[T12]`, `[F3 p.4]`, `[M5 12:30]`. Our code turns them into Teams links. **Ids the tools did not return in this answer are removed**, which stops made-up sources.

**Permissions.** Filter **inside the SQL, before ranking**, by the audience of the place where the answer is posted (the channel's members, or the meeting's attendees), not only the asker: a reply in a standard channel is seen by everyone there. Private content only comes back if the whole audience may see it. The open tools check again.

**Freshness.** When an item changes (new `content_hash`), rebuild only its chunks and vectors, in one transaction. A delete removes its chunks at once, and the open tools re-check `deleted_at`. Snippets show "last changed", so Max can say "as of 3 Oct".

## 3. Where to store vectors
**In the same SQLite file**: a `chunk_vectors(ref, model, vec BLOB)` table, compared with numpy. 10k chunks × 768 dims ≈ 30 MB, under 10 ms per search, nothing new to install. `sqlite-vec` (0.1.9, Windows wheel, pre-1.0) only above ~100k chunks. No separate vector database.

## 4. Initial backfill (10k messages, 300 files, 50 one-hour transcripts)
Size: messages ~0.6M tokens, files ~1.5M, transcripts ~0.6M. Total **~3M tokens, ~8k chunks**.

| Step | Time (estimate, measure on the laptop) | Cost |
|---|---|---|
| Download from Graph (throttling sets the speed) | 10–30 min (seconds in the simulator) | Free |
| Extract text with MarkItDown, 4 processes | 3–10 min (big PDFs are the slow part) | Free |
| Chunk + FTS5 index | < 1 min | Free |
| Embeddings, local bge-small | ~5–15 min | Free |
| Embeddings, `gemini-embedding-2` | ~5 min (100 chunks per call) | ~$0.60 (or $0.30 batch) |
| Optional: a one-paragraph summary per file and meeting, made by Gemini | ~10 min | ~$0.50 |
| **Total** | **~30–60 min** | **< $1.20** |

## 5. Evaluation and risks
**Test set:** ~40 questions written **together with the demo world**, each with its correct `ref`s: exact words, paraphrases, a spreadsheet number, "what did Prince say last meeting", an edited fact (newest wins), deleted content (not found), private content (no leak), two-step questions.
- **Retrieval test** (pytest, free, offline): **recall@5 / recall@10** of `search_knowledge`. Target ≥ 90% at 10. If paraphrase questions fail, add embeddings (Step 2) and measure again.
- **Answer test** (nightly, real Gemini): is the answer right, is the citation right, latency, tokens. Target ≥ 85% correct, **0 leaks**, p95 under 10 s.

| # | Risk | Could it break the demo? | Mitigation |
|---|---|---|---|
| 1 | Private or meeting content leaks into a channel answer | Yes, badly | Audience filter in SQL, applied again on open. Leak tests |
| 2 | Deleted or old text is used in an answer | Yes | Delete and re-chunk in one transaction. Tests |
| 3 | Search misses paraphrases, so Max wrongly says "I don't know" | Yes | The agent tries 2–3 phrasings. Add hybrid if recall is low |
| 4 | Spreadsheet maths or scanned PDFs give wrong numbers | Yes | Give the model tables, not prose. Add a small calculate tool. Mark files with no text |
| 5 | The agent loops (slow, costly), or cites made-up sources | Yes, in meetings | Cap of 6 calls, token budget, time limit, meeting fast path, check every cited id |

Also: Gemini's **free tier may use our data to improve Google's products**. Use a paid key for company data.

## Sources
- [Gemini API pricing (models, embeddings, caching)](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini embeddings (dims, limits, v1 and v2 not compatible)](https://ai.google.dev/gemini-api/docs/embeddings)
- [Gemini context caching](https://ai.google.dev/gemini-api/docs/caching) · [Gemini File Search](https://ai.google.dev/gemini-api/docs/file-search)
- [fastembed supported models](https://qdrant.github.io/fastembed/examples/Supported_Models/) · [fastembed on PyPI (0.9.1)](https://pypi.org/project/fastembed/)
- [sqlite-vec on PyPI](https://pypi.org/project/sqlite-vec/) · [SQLite FTS5](https://www.sqlite.org/fts5.html)
- [Reciprocal Rank Fusion (Cormack et al.)](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)
- Our own: `docs/research/storage.md`, `docs/decisions.md`
