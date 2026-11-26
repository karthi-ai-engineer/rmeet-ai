# Max: RAG (the live knowledge system)

**Status: ✅ AGREED (26 Nov 2026). All 8 parts + Decisions 1-4 below.**
**Karthi (26 Nov): the RAG must be accurate, not basic** (re-ranking, better query handling, accuracy checks, and
"perfect from chunking onwards", e.g. semantic chunking). Deep research running:
`docs/research/rag-advanced-retrieval.md` (query, chunking, search, re-ranking, embeddings),
`rag-answer-accuracy.md` (checking, citations, spreadsheets, knowledge graphs, summaries, time),
`rag-real-systems-eval.md` (how Glean/Copilot/etc. build it + how we measure accuracy).
Research: `docs/research/rag-history-scale.md`, `rag-live-updates.md`, `knowledge.md`, `storage.md`.

## The 8 parts
| # | Part | Status |
|---|---|---|
| 1 | How much history Max reads when it joins + the "knowledge horizon" | ✅ Agreed (26 Nov) |
| 2 | Staying up to date (new, edited, deleted; speed targets) | ✅ Agreed (26 Nov) |
| 3 | Proving it's correct (nightly check, health view, alerts) | ✅ Agreed (26 Nov) |
| 4 | Getting text out of files (extraction, OCR, link briefs) | ✅ Agreed (26 Nov) |
| 5 | Splitting into pieces (chunking) | ✅ Agreed again after deep research (26 Nov) |
| 6 | Search (keyword + meaning + re-rank; personal chat messages in or out) | ✅ Agreed (26 Nov, Decision 2) |
| 7 | Reading tools + citations | ✅ Agreed (26 Nov, stages B5-B9 + Decision 3) |
| 8 | Privacy filter + testing | ✅ Agreed (26 Nov, Decision 4) |

## Part 1: how much history
Picture: `pictures/rag-1-history.excalidraw` (quick view `pictures/rag-1-history-preview.png`).

**Agreed (Karthi, 26 Nov 2026):**
- Max only reads the teams and chats it's added to, never the whole company.
- **Window per chat, chosen in first-run setup: 15 / 30 / 60 / 90 days. Default 30 days** (covers last month's
  meetings and the last monthly cycle). 1 year was too long.
- Newest first; everything from install day on is read live.
- For a big team (~100k messages a year) the 30-day window is ~8k messages: ready in minutes, a few cents.

**Also agreed:**
- Older than the window: **not read at all**. The status card shows the horizon ("read back to 27 Oct");
  the **team lead** can press [Read further back] or change the setting.
- When a question is about something older than the horizon, Max says so plainly instead of guessing.

## Part 2: staying up to date (AGREED 26 Nov 2026)
Picture: `pictures/rag-2-updates.excalidraw` (quick view `pictures/rag-2-updates-preview.png`). Research: `docs/research/rag-live-updates.md`.
- Pipeline: Teams change → Microsoft's short "something changed" note → **inbox** (saved at once) → **one worker**
  (drops duplicates, fixes order, deletes first) → **fetch** the full latest version → **update in one step**
  (saved copy + pieces + keyword search, only that item) → meaning search a few seconds later.
- R1 uses the simple id-only notes + "what changed since" queries; the encrypted full-content notes only if measured
  speed needs them.
- No 15-minute polling: Microsoft's rules allow polling a resource only once a day. Instead: catch-up on start
  (laptop was off), on any subscription problem, and the nightly check.
- Speed targets: post/reply/edit ≤ 30 s; delete ≤ 30 s (first); member removed ≤ 30 s + live member check before any
  private answer; file ≤ 5 min; transcript ≤ 5 min after Teams publishes it; anything missed → nightly check.
- Honest promise instead of "always perfect": once Max knows about an edit/delete the old text never appears again;
  Max knows how far behind each chat is and says so; a nightly check proves the copy matches Teams.
- **Nightly check time is a setting** the team lead chooses in setup (changeable any time). If the laptop is off at
  that time, the check runs at the next start.

## Part 3: proving it's correct (AGREED 26 Nov 2026)
- **Nightly compare** (at the team lead's chosen time): Max's list vs Teams' list per chat and file folder
  (id, last changed, deleted). Fixes any difference.
- **Self-check** after catch-ups and nightly: live items have pieces; deleted items have none; search counts match.
- **Echo test:** every Max post must come back as a "something changed" note within 60 s; if not, the chat is
  marked "suspect" and Max catches up.
- **Drift counter:** how many fixes the nightly compare needed. Target 0; anything else becomes a test.
- **Health view** on the team lead's setup page (one line per chat: last updated, behind by, problems).
  Kept separate from the cost dashboard (cost may stop mattering if models move to company servers).
- **Alerts** only when something needs attention, to **both the team lead and the developer** (Karthi), in their
  private chat with Max.

## Part 4: getting text out of files + link briefs (AGREED 26 Nov 2026)
Picture: `pictures/rag-4-extraction.excalidraw` (quick view `pictures/rag-4-extraction-preview.png`). Research: `docs/research/rag-extraction-ocr.md`.
- Background pipeline: file arrives → **does it have real text?** → yes: read text (headings, slides, sheets,
  tables kept as tables) · no/partly: **OCR on the laptop** · OCR unsure / charts / handwriting: **AI vision (switch)**
  → **quality label** (text OK / partly OCR / failed + why) → **sections with locations** (page, slide, sheet) → pieces.
- Tools (free, safe licences): **Docling** (headings + table structure) as main extractor; MarkItDown, python-docx,
  openpyxl, python-pptx as fast path/backup; **RapidOCR** on CPU (3-4 s/page, 100% on our test page); AI vision
  ~$0.001/page, any vision model. Avoid: Marker/Surya (paid above a revenue limit), MinerU (custom licence), PyMuPDF (AGPL).
- Original files are always kept, so everything can be re-read with a better extractor later. Limits for very large files.
- OCR and vision each sit behind one function (model stays swappable). OCR model files ship with Max (downloads stalled in the test).
- **Link briefs:** a shared link is read safely (no logins, size + time limits, page text = data never commands) →
  short brief (title, what it's about, key points, link, date) → searchable.
- Agreed: **Docling now** (best tool; machine size is not a limit). **AI vision switch ON by default.** Test pages:
  generated for now; real samples planned later.

## Part 5: splitting into pieces (AGREED 26 Nov 2026)
Picture: `pictures/rag-5-pieces.excalidraw` (quick view `pictures/rag-5-pieces-preview.png`).
| Content | Pieces |
|---|---|
| Thread | Post + replies = 1 piece; very long thread: replies in groups, post repeated on top |
| Word | One piece per heading section; long sections split, heading kept |
| Excel | Per sheet: a summary piece (columns, row count) + rows in blocks of 50 as a table |
| PowerPoint | One piece per slide (+ speaker notes) |
| PDF | One piece per page (short pages joined); scanned pages = OCR text |
| Transcript | 2-3 minute windows cut at speaker changes; names on every line |
| Max's meeting notes | One piece per meeting |
- Every piece carries a label: title line ("Budget.xlsx > sheet Q1 > rows 1-50"), where (team, chat, file,
  page/slide/sheet/minute), author + last changed, **who may see it**, link back to the exact spot.
- Size about 300-800 tokens. Only changed pieces are redone on edits.

## Part 6: search (AGREED 26 Nov 2026; flow updated by Decision 2 below)
Picture: `pictures/rag-6-search.excalidraw` (quick view `pictures/rag-6-search-preview.png`, redrawn with re-rank).
- Flow: question → Max rephrases 2-3 ways → **privacy filter first** → **keyword search** (exact words, names,
  numbers, file names) + **meaning search** (embeddings) run together → merge (best of both) → top 8 pieces →
  short snippets to the AI (title, where, who, when, ~300 chars, id) → open more only if needed.
- **Both kinds from R1** (changed from "keyword first, embeddings only if tests need it": best tools, environment
  is flexible). Embedding model behind one `embed()` switch (`gemini-embedding-2` now); changing it = re-index once.
- Meaning search lags keyword search by a few seconds; keyword search covers new messages meanwhile.
- Filters: chat, person, date, file, meeting.
- Personal (non-work) messages: Max only reads chats it was added to; small talk rarely matches work questions;
  memory is already work-only; a chat can be set to **"don't index this chat"**.

## The accurate RAG: all stages (PROPOSED 26 Nov 2026, after deep research)
Picture: `pictures/rag-accurate.excalidraw` (quick view `pictures/rag-accurate-preview.png`).
Research: `rag-advanced-retrieval.md` (chunking, query, search, re-rank, embeddings), `rag-answer-accuracy.md`,
`rag-real-systems-eval.md`.

**A. Preparing the knowledge (background):** A1 extract (Part 4) → A2 pieces by structure with a clear label (Part 5;
large studies show semantic/AI/late/contextual chunking tie or lose vs this) → A3 extra pieces: one summary per file and
meeting; plain chats split into conversations by quiet gaps → A4 keyword index + meaning index (strong, swappable
embedding model; open fallback Qwen3-Embedding-0.6B, Apache 2.0) → A5 spreadsheets stored as tables (header row repeated
in row blocks) → A6 every piece labelled with who may see it.

**B. Answering:** B1 the AI writes the search + 2-3 other phrasings (no separate rephrase step); code turns "last week"
into dates → B2 privacy filter → B3 keyword top 50 + meaning top 50, weighted merge → top 40 → B4 **re-rank**: the AI
ranks the 40 (provider-neutral, ~1-2 s, ~$0.0015) → best 8 (a local re-rank model only on a GPU machine: Qwen3-Reranker
took 58 s on the office laptop) → B5 read + dig deeper, search again if weak (max 3 searches; stop after 2 with nothing
new) → B6 numbers by code (`query_sheet` with simple fields + `calc`) → B7 answer with a status (answered / partial /
not found / conflict; newest source wins, "as of") → B8 checks before posting (every source id real, every number
matches the tools; extra AI fact-check for numbers and decisions) → B9 post with exact-spot sources. If a check fails:
fix once; still failing → say what is known + "not sure".

**C. Proving accuracy (Part 8):** planted facts in the simulated team; ~250 test questions in 11 types reviewed by
Karthi; free search tests on every `run.py test`; nightly answer tests with an AI judge checked against Karthi's marks;
canary words for leak tests; same questions to compare models.

**Left out (no proven gain for us):** semantic/AI chunking as default (A/B test only in long chats and transcripts),
old-style cross-encoder re-rankers, knowledge graphs (GraphRAG, LightRAG, HippoRAG, Graphiti), Self-RAG, long context.

Estimated: typical answer 6-8 s, $0.006-0.009; hard question 12-18 s, ~$0.012-0.016.

### Decision 1, chunking (AGREED 26 Nov 2026, after deep research)
Structure-based pieces ~300-800 tokens, little/no overlap, clear label on top (best in Chroma 2024, Vectara 2025,
Caspari 2026). Improvements: (1) plain chats split into conversations (45+ min quiet = new one); (2) Excel header row
repeated in every block, blocks sized by length; (3) one summary piece per file and per meeting; (4) semantic splitting
only inside long chats/transcripts, and contextual pieces on files later: both **tested during implementation and kept
only if the test set shows they're better**. Picture updated: `pictures/rag-5-pieces-preview.png`.

### Decision 2, search + re-rank (AGREED 26 Nov 2026)
Picture: `pictures/rag-6-search-preview.png`. Flow: understand (search + 2-3 phrasings in the same AI call; code turns dates
into filters) → privacy filter → keyword top 50 + meaning top 50 → weighted merge → top 40 → **AI re-rank → best 8**
→ read (open whole thread / section only if needed) → search again if weak.
1. **Re-rank ON from day one** (any model; ~1-2 s, ~$0.0015). The test set must show it helps, otherwise it is turned
   off. A local re-rank model may replace it on a GPU machine or server.
2. **Max 3 searches** per question; stop after 2 that find nothing new.
3. **Qwen3-Embedding-0.6B** is the open backup embedding model, **used only if the test set shows it is as good as
   the current one** (Karthi: "yes if it is perfect").

### Decision 3, answer checks (AGREED 26 Nov 2026)
1. **Numbers by code.** Defined tools (`query_sheet` with simple fields + `calc`) cover most cases. **When they aren't
   enough, the agent may write its own query** (Karthi: "let the agent create its own tools if required and if it's
   best"). Proposed safe form: a read-only query on the sheet's table, on a read-only connection, with a time limit,
   no network, no file access; the query and its result are kept in the run card (sources panel). To confirm.
2. **Answer status** (answered / partial / not found / conflict): agreed. **Conflicting sources: the model decides**
   which is right, using dates as a strong hint (newer usually wins); when it can't tell, it shows both with dates.
3. **Code checks before posting** (every source id real, every number matches the tools): agreed.
4. **AI fact-check** for answers with numbers or decisions: agreed, to be built.
5. Hard questions may cost up to **~$0.015** (normal answers under $0.01).
6. **Agent-written query** (when defined tools aren't enough): read-only, can't change data, no internet, no files,
   time limit; the query + result shown in the sources. Proposed 26 Nov; Karthi said "progress" (taken as OK).

### Decision 4, testing accuracy (AGREED 26 Nov 2026)
- Simulated team with **planted facts**, so the right answer is always known.
- **~250 test questions in 11 types**, generated by Claude (40 can't prove 90%). Review changed 26 Nov: Karthi
  spot-checks ~25 + flagged ones; code + a second AI reviewer check the rest (`11-sim-world.md` Part 4).
- **Search tests** on every `run.py test` (free: is the right piece in the top 8?).
- **Answer tests** nightly with an AI judge, first checked against **~80 answers Karthi marks**.
- **Leak tests** with canary words; **model tests** (same questions on any model).
- **Test budget separate from the daily cap**, starting at ~$5/week.
- **Rule (Karthi): every price, budget and limit is a setting the user can change any time, never fixed in code.**
  An editable dashboard for them comes later (not R1 now); until then they live in the settings file.

**RAG (topic 3) agreed in full on 26 Nov 2026.** Parts 7 (reading tools + citations) and 8 (privacy filter +
testing) are covered by stages B5-B9, Decision 3 and Decision 4.
