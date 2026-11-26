# Research: answer accuracy and reasoning over retrieved data (26 Nov 2026)

How Max turns found pieces into a correct, cited answer. Builds on `plans/07-rag.md` (parts 1-6),
`plans/04-agent-design.md` (sections 2, 11, 12), `plans/06-memory.md`, rules R-2 and R-12.
Claims we could not check fully are marked **(?)**. Numbers marked "est." are our estimates; measure them.

## Headline
- **The biggest accuracy wins for Max are cheap code-level rules, not fancy retrieval.** Do numbers in code over
  sheets stored as tables, check citations and numbers in code before posting, resolve dates in code, and let Max
  say "not found" in a fixed format.
- **Keep the agentic loop we designed** (search → open → search again → answer). Add **code stop rules** and a
  **structured answer** (claims + source ids + status), because smaller models are weak at deciding when to stop and
  at tool use.
- **Skip knowledge graphs for R1** (GraphRAG, LightRAG, HippoRAG, Graphiti). The benchmark gains are real but narrow,
  costs are high, and our people facts, decisions log and summaries already cover the "who decided what" and "summarise X" cases.
- **Reuse summaries we already make** (thread summaries, meeting notes, weekly digests) as searchable pieces. That is
  "RAPTOR-lite" for broad questions at almost no extra cost.

## 1. Ranked table

Cost uses Gemini 3.1 Flash-Lite at **$0.25 / 1M input, $1.50 / 1M output** ([Google](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-1-flash-lite/)).

| # | Technique | Accuracy gain (evidence) | Latency | Cost / question | Complexity | For Max |
|---|---|---|---|---|---|---|
| 1 | **Numbers by code**: sheets saved as SQL tables + a query tool + `calc` | Code instead of model maths: 59.7% → 67.3% on finance QA ([Financial-PoT](https://arxiv.org/pdf/2601.21157)); TAT-QA exact match <30% → ~80% with a code agent ([2512.13323](https://arxiv.org/html/2512.13323v1)); models fail to add 14 decimals in text ([ASTRA](https://arxiv.org/pdf/2604.08999)). SQL + pandas with self-correction: 86-88% on DataBench ([SemEval-2025](https://arxiv.org/html/2506.09657v2)) | +1 tool step (~1-2 s) | ~$0.001 | Medium | **R1** (rule R-12) |
| 2 | **Code check before posting**: every cited id was returned in this run; every number in the answer appears in a cited piece or a `calc` result; else retry once | Up to 57% of RAG citations are "after the fact", not real support ([2604.03173](https://arxiv.org/pdf/2604.03173)); a verify step is what lifts citation quality ([VeriCite](https://arxiv.org/abs/2510.11394)) | 0 (+~2 s on a retry) | ~$0 (+$0.002 on retry) | Low | **R1** |
| 3 | **Dates in code**: "last meeting", "this month", "before/after" resolved to filters; every snippet shows its date; `newest first` option | Rerankers prefer old, wordy pages even when outdated ([FRESCO](https://arxiv.org/abs/2604.14227)); rewriting the query with dates *hurt* (BM25 nDCG 0.149 vs 0.209) ([TimelyRAG](https://arxiv.org/pdf/2609.11572)); a mild recency prior worked for "latest" questions ([2509.19376](https://arxiv.org/html/2509.19376v1)), a strong one hurt relevance ([2604.14169](https://arxiv.org/pdf/2604.14169)) | 0 | 0 | Low | **R1** |
| 4 | **"Not found" as a real answer** (status `answered / partial / not_found / conflict`) | With context that is not enough, wrong answers went 10.2% → 66.1% (Gemma): more context makes models *more* confident; abstaining when unsure added up to 10% accuracy on answered questions ([Google, sufficient context](https://research.google/blog/deeper-insights-into-retrieval-augmented-generation-the-role-of-sufficient-context/)) | 0 | 0 | Low | **R1** |
| 5 | **Conflict rule**: newest dated source wins, say "as of", mention the older value | Models handle conflicting sources poorly; asking them to reason about the conflict explicitly helps ([CONFLICTS](https://arxiv.org/pdf/2506.08500)); filtering outdated versions helps ([Re³, ACL 2026](https://aclanthology.org/2026.acl-long.1180/)) | 0 | 0 | Low | **R1** |
| 6 | **Agentic multi-hop loop with code stop rules** | Agentic retrieval gains grow with the number of hops ([SAG2](https://arxiv.org/pdf/2610.22588)); small models call tools too little and guess ([Search, don't guess](https://arxiv.org/html/2604.04651)); tools help small models more than "thinking", full thinking can break tool use ([2601.11327](https://arxiv.org/html/2601.11327v1)) | 2-4 model turns (est. 5-9 s) | ~$0.006-0.009 | Medium (already designed) | **R1** |
| 7 | **LLM claim check**: one extra cheap call, "is each claim supported by its cited pieces?" | Prompted Gemini judged "enough context" at ≥93% accuracy (same Google paper); a 770M checker matches GPT-4 at 400× lower cost ([MiniCheck](https://arxiv.org/abs/2404.10774)); Google sells this as a <500 ms API ([Check grounding](https://docs.cloud.google.com/generative-ai-app-builder/docs/check-grounding)) | +~1 s (est.) | ~$0.001 | Low | **R1, only for answers with numbers or decisions**; drop if tests show no gain |
| 8 | **Summary pieces** (thread summaries, meeting notes, weekly digests, 1 paragraph per file) searchable, linked to sources | RAPTOR: +20% on QuALITY with GPT-4 ([RAPTOR](https://arxiv.org/abs/2401.18059)); summarisation questions gain most from structure (+7 to +13 points) ([GraphRAG-Bench](https://arxiv.org/html/2506.05690)) | 0 at question time | Files ~$0.50 once; digests already made | Low (reuse) | **R1** (reuse); monthly roll-ups later |
| 9 | **Light entity layer**: people roster + decisions log + people facts (all already designed) as tool filters | No benchmark; middle ground between plain search and a graph | 0 | 0 | Low | **R1** (people, decisions). Project/product alias list **later** |
| 10 | Separate relevance grader per piece (Corrective RAG) | Original needs a fine-tuned grader; the grader mostly matches names, and transfer to new domains is weak ([CRAG reproduction](https://arxiv.org/abs/2603.16169)) | +1 call | +$0.001-0.002 | Medium | **Skip** (the model grades while reading; a local reranker later if tests need it) |
| 11 | Self-RAG | Needs a specially fine-tuned model; doesn't fit a swappable API model | n/a | n/a | High | **Skip** |
| 12 | GraphRAG / LightRAG / HippoRAG 2 | Complex reasoning +6 to +10.5, summaries up to +13; but **fact lookups lose** (MS-GraphRAG −11.6, and −26 on medical). Tokens per query: plain RAG 879, HippoRAG 2 1,008, LightRAG ~100k, GraphRAG global ~331k ([GraphRAG-Bench](https://arxiv.org/html/2506.05690)). Indexing ~10-40k LLM tokens per document ([RAGU](https://arxiv.org/pdf/2607.11683)) **(?)** | High (global modes) | High to index | High | **Skip R1**; HippoRAG 2 style only if multi-hop tests fail |
| 13 | Graphiti / Zep temporal graph | LongMemEval 71.2% vs 60.2% full context (vendor numbers, [Zep](https://arxiv.org/abs/2501.13956)); an independent test could not finish indexing in 2 days ([2604.01707](https://arxiv.org/pdf/2604.01707)) | Low at query | LLM calls per message | High (graph database) | **Skip**; our facts already have valid from / until |

## 2. What each topic means for Max

**Corrective / adaptive retrieval.** Max already decides "search or not" inside THINK, and intake already sends
greetings to `quick`. The missing parts are code rules: (a) a statement about team facts must carry a citation
(enforced by the check in row 2), (b) the search tool tells the model when matches are weak ("weak matches: try other
words, a person, or a date filter"), (c) code tells the model when a new search returned **no new ids**
("nothing new found: answer with what you have or say not found"). A separate grader call per piece costs time and
isn't proven for API models.

**Grounding and citations.** Make the final answer a **typed object**, not free text:
`status`, `claims[]` (text + source ids), `numbers[]` (value + source id or calc id), `as_of` date. Pydantic AI
supports this (output type + output validator that can ask the model to retry). Our code renders it into a Teams
message and the "How I got this" panel. Deterministic checks first (free, every answer); the LLM claim check only
where a wrong answer hurts most (numbers, decisions).

**Spreadsheets.** Text pieces alone can't add up a column. Evidence favours **running code on real tables**, with
self-correction on errors. Plain SQL breaks on messy sheets (merged headers, unit rows) ([RePairTQA](https://arxiv.org/html/2509.22983)), so:
- At extraction (part 4) each sheet also becomes an **SQLite table** (header row detected, merged headers joined,
  units kept as a column note, original cell address per row). The sheet's summary piece lists columns and examples.
- Tool `query_sheet(sheet_id, columns, filters, group_by, op)` with **simple fields, not free SQL**: code builds a
  read-only SQL query. Smaller models fill fields more reliably than they write SQL (?). Results carry cell ranges
  ("Budget.xlsx > Q1!C5:C17") for citations.
- `calc` for anything that mixes values from different places. A failed query returns the error so the model can fix it once.
- Free SQL (read-only, row limit) can be added later for strong models.

**Graphs vs a light entity layer.** Graph methods win on "connect many pieces" and "summarise everything" benchmarks,
but lose on plain fact lookups, which are most of Max's questions ("what's the Q3 ads budget?"). They also add an LLM
extraction step per document, a second store to keep in sync with edits and deletes (part 2), and more for small
models to get wrong. Our design already has the useful parts: people roster (from Teams, free), people facts with
dates, and the decisions log (who decided what, when, source). These become **filters** on search
(`person=`, `kind=decision`). Revisit graphs only if the test set shows multi-hop failures we can't fix otherwise.

**Hierarchical summaries.** For "what happened in Planning this month?", searching 8 pieces is not enough. Store
summaries as pieces with `kind=summary` and links to their sources: thread summaries (already planned), Max's meeting
notes (already planned), the weekly digest (already a workflow), and one paragraph per file (~$0.50 once,
`knowledge.md`). A month question reads 4 weekly digests + that month's meeting notes, then opens sources only for
details. Summaries never count as the final source for a number: numbers are always cited from the original.

**Temporal reasoning.** The situation already includes today's date and time. Code (not the model) turns phrases
into dates; tools take `after`, `before`, `sort=newest`. "Last meeting" is a **lookup** (`list_recent(kind=meeting, n=1)`),
not a search. Ranking: meaning + keyword first, recency only as a tie-breaker or mild boost when the question asks
for the current state. Every snippet shows its date, so "as of 12 Nov" is easy. Questions older than the knowledge
horizon get the horizon message (part 1).

## 3. Recommended answer pipeline (mode 2, simple loop)

```
INTAKE (code)   task type answer · dates resolved · audience · team filter · horizon
PREPARE         instructions + skill file "answer" + situation + last ~20 messages + 8 tools
THINK 1         plan in one line → search_knowledge (2-3 phrasings, filters, dates)
ACT             snippets: title · where · who · date · ~300 chars · id · match strength
THINK 2         open 1-3 items (read_file section, read_thread, get_transcript window)
                or query_sheet / calc for numbers   ← corrective re-search if weak / nothing new
THINK 3 (opt.)  one more hop if a piece points elsewhere ("see the v3 file")
ANSWER          typed object: status · claims + ids · numbers + ids · as_of
CHECK (code)    ids seen in run? numbers found in cited text or calc? dates OK? → else retry once
CHECK (LLM)     only if numbers/decisions: claims vs cited pieces (~4k tokens) → drop or fix unsupported claims
REPLY           answer + "How I got this"; not_found → "I couldn't find this in what I can see (back to 27 Oct)"
```

**Code stop rules** (on top of the 8-step budget): stop searching after 2 searches with no new ids; at most
3 search calls per question unless the model calls `ask_for_more_steps`; loop guard as designed.

**Other modes.** Mode 1 (workflows) *produces* the summary pieces (weekly digest, meeting notes). Mode 3 (plan, then act)
is for big comparisons ("Q1 plan vs actual across three files, by product"): the plan lists one `query_sheet` per file, then `calc`.

**Numbers per question (est., measure on the laptop):**

| | Typical | Hard (multi-hop, sheet) |
|---|---|---|
| Model calls | 3 + optional check | 5-6 + check |
| Input tokens | ~25k (snippets kept short) | ~45k |
| Cost | ~$0.006-0.009 | ~$0.012-0.016 |
| Latency | ~6-8 s | ~12-18 s |

Gemini's cached-input price ($0.025 / 1M) on the repeated prompt start could cut input cost a lot, if caching hits **(?)**.
The hard case is above $0.01; it is rare, and the daily cap still applies.

**For future open-source models:** fewer tools per task, simple tool fields, typed answer, all stopping, dates, numbers
and checks in code, low thinking level for answers. The same tests decide whether a model is good enough.

## 4. How we prove it (extends the 40-question set)

| Group | Example | Target |
|---|---|---|
| Numbers | "Total Q2 ads spend?" | 100% exact (R-12) |
| Citations | every answer | ≥95% of claims supported by their cited piece |
| Not found | question about something never posted | ≥90% say "not found", 0 made up |
| Temporal | "what did we decide in the last planning meeting?" | ≥90% |
| Conflict | budget v2 vs v3 | newest value + "as of" + older value mentioned |
| Broad | "what happened this month?" | covers the main decisions in the digests |
| Overall | 80 questions | ≥85% correct, 0 leaks, p50 ≤ 8 s, p95 ≤ 20 s |

Run each check (rows 2, 4, 7) on/off once to see what it really adds on our data.

## Sources
Corrective RAG [2401.15884](https://arxiv.org/abs/2401.15884) · agentic RAG survey [2501.09136](https://arxiv.org/abs/2501.09136) ·
adaptive routing benchmark [RAGRouter-Bench](https://www.arxiv.org/pdf/2602.00296) · citation evaluation [CiteEval](https://arxiv.org/html/2506.01829v1) ·
claim-level grounding [ETRACER](https://arxiv.org/pdf/2601.03669) · [TableRAG (EMNLP 2025)](https://aclanthology.org/2025.emnlp-main.710/) ·
[HippoRAG 2](https://arxiv.org/abs/2502.14802) (+9.5 F1 on 2Wiki vs a strong embedding model) · [GraphRAG paper](https://arxiv.org/abs/2404.16130)
(72-83% "more complete" win rate on global questions **(?)**) · [LazyGraphRAG](https://www.microsoft.com/en-us/research/blog/lazygraphrag/)
(indexing ~0.1% of GraphRAG, vendor numbers) · [RAG vs GraphRAG](https://arxiv.org/abs/2502.11371) · plus the links in the tables.
