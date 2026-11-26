# Research: how real enterprise RAG is built, and how to prove Max's RAG is accurate

Date: 26 Nov 2026. Feeds `docs/plans/07-rag.md` (parts 6-8) and the accuracy targets in `docs/plans/03-requirements.md`.
Claims marked **(unverified)** come from secondary sources or my own estimate.

## Short answer
- Real systems all share the same core: **sync fast, filter by permission before the AI sees anything, hybrid
  search, then a reranker, then a grounded answer with sources, then measure all the time.** Max's plan has all of
  this **except a reranker**, a **"calculate over a spreadsheet" path** for numbers, and a written **evaluation set**.
- To *prove* accuracy: a **planted-fact test team** in `world/`, **~250 questions** (40 is too few to prove 90%),
  **retrieval tests with no AI in CI** (free, same result every run), **AI-judged answer tests** on a schedule, a
  **judge checked against Karthi's own labels**, and **canary strings** that make privacy leaks detectable by code.

---

## Part A: how real systems are built

### A1. Common stages, and how Max compares

| Stage | What real systems do | Max's plan | Gap |
|---|---|---|---|
| 1. Sync + freshness | M365 Copilot: updates indexed "immediately", new SharePoint docs daily. Rovo: "nearly instant" (vendor claim). Slack enterprise search: no copy, live query. | Part 2: ≤ 30 s, nightly compare | None (stricter than M365) |
| 2. Extraction | Keep structure (headings, tables, slides) | Part 4 | None |
| 3. Chunks with context | Notion: spans with author + permission metadata. OpenAI: 800 tokens, 400 overlap. Anthropic: AI-written context line per chunk. | Part 5: title line + where/who/when per piece | Small: test if an AI-written context line adds anything |
| 4. Permissions | Glean: "upstream of the LLM". Slack: asker's ACL. M365: security trimming. Notion: permission per span. | Filter first + live member check | **Automated leak test** missing (Part 8) |
| 5. Query rewrite | M365 synonyms/intent; OpenAI rewrites query | Rephrase 2-3 ways | None |
| 6. Hybrid search | Glean, Perplexity/Vespa (vendor-written), Elastic (BM25 + vectors + RRF), Anthropic | Keyword + meaning, merged | None |
| 7. **Reranking** | Glean, Perplexity (cross-encoders), OpenAI, Elastic, Anthropic | **Not in plan** | **Biggest gap**: "top ~50 → reranker → top 8" behind a switch, kept only if tests show a gain |
| 8. Personal signals | Glean knowledge graph, M365 people/social signals, Rovo Teamwork Graph | Filters only | Light: small boosts (recent, same chat, asker's items) if tests help |
| 9. Numbers / tables | Dust: "RAG for open questions, table queries for numbers" | Excel summary + 50-row blocks | **Gap for sums/filters**: a "query this sheet" tool |
| 10. Answer + sources | All cite; Slack/M365 show answers only to the asker | Part 7 (open) | Decide in Part 7 |
| 11. "I don't know" | Glean tracks no-answers (predicts users leaving) | Horizon rule | Add to test set |
| 12. Eval + feedback | Glean AI Evaluator; Dropbox gates every change + samples live traffic | Part 3 proves the **copy** matches Teams, not that **answers** are right | **This plan** (Part 8) |

### A2. What they say matters most
1. **Measure on your own data, every change.** Anthropic's first recommendation; Dropbox blocks merges on
   ~150 canonical questions (< 10 min) and a bigger suite after merge.
2. **Hybrid + reranker beats either search alone.** Anthropic, top-20 failure rate: embeddings 5.7% → +context 3.7%
   → +BM25 2.9% → +rerank 1.9% (67% fewer failures). Elastic: RRF merge +18% nDCG@10 over BM25 alone.
3. **Permissions before the AI, never after.** Every system says this.
4. **Give the model enough context.** Anthropic found 20 chunks beat 5 or 10. Max shows 8 short snippets and opens
   more on demand; **test 8 vs 15 vs 20**.
5. **Don't use plain RAG for counting** (Dust).
6. **The judge needs checking.** Glean: humans agreed with each other 79% of the time, the AI judge agreed with
   humans 74%. Dropbox re-checks the judge against human labels every few weeks and has humans review 5-10% per release.

---

## Part B: how Max proves it is accurate

### B1. Metrics and targets

| Metric (plain meaning) | How measured | Target | Gate type |
|---|---|---|---|
| **Hit@8**: right source in top 8 | code, no AI | ≥ 90% (requirement) | Hard (CI) |
| **Recall@8**: for multi-source questions, *all* needed sources in top 8 | code | ≥ 80% | Hard (CI) |
| MRR / nDCG@8: how high the right source ranks | code | Track only | Trend |
| **Leak check (search)**: a piece the asker may not see comes back | code, every question × every user | **0** | Hard (CI) |
| **Stale check**: deleted or old-version text returned | code | **0** | Hard (CI) |
| **Answer correct** | AI judge vs reference answer, key facts list | ≥ 85% (requirement) | Hard (scheduled) |
| **Numbers exact** | code: number in answer = number in reference | 100% of number questions | Hard |
| **Grounded**: claims backed by the sources shown | AI judge, claim by claim (Glean / RAGAS style) | ≥ 95% of claims | Hard |
| **Citation precision**: cited source really supports the claim | AI judge | ≥ 90% | Hard |
| **Has a source** (≥ 1 correct source per answer) | code + judge | 100% (A-1) | Hard |
| **Correct "I don't know"** on unanswerable / beyond horizon | judge (labels: answered / declined) | ≥ 90% | Hard |
| **Wrong refusals** on answerable questions | judge | ≤ 5% | Hard |
| **Leak check (answer)**: a private canary string reaches an outsider | code (string match) | **0** | Hard |
| Cost per question, latency p50/p95 | meter | ≤ $0.01; ≤ 8 s / 20 s | Hard |

**Canary strings:** plant unique made-up words (e.g. "Project Kestrel-7731") only in private chats/files.
If one ever appears in an answer to someone outside, that is a proven leak, found by code, no judge needed.

### B2. The test set

**How we build it (key idea):** `world/` is generated, so we **plant facts on purpose** and know exactly where each
one lives. Ground truth comes from construction, not guessing.
1. Write a "fact sheet" (fact, where it lives, who may see it, date, later edits/deletes).
2. Generate the posts, files, meetings that contain those facts.
3. AI drafts 2-3 wordings per fact; **Karthi reviews every question** (a few hours; Dropbox and Glean also mix
   synthetic and human-reviewed sets).
4. Label sources at **item level** (thread id, file + sheet/page, meeting + minute), not piece id, so changing the
   chunking doesn't break the tests.
5. Edits/deletes/member removal run as a **scripted timeline**; questions are asked at checkpoints.

| Question type | Example | Count |
|---|---|---|
| Exact fact (keyword wins) | "What's the booth number for the spring trade show?" | 30 |
| Paraphrase (meaning wins) | "What did we settle on for the cost cut?" (post says "price reduction") | 30 |
| Number from a spreadsheet | "What was March ad spend?" / "Total Q1?" | 25 |
| From a meeting transcript | "Who agreed to send the draft, and by when?" | 25 |
| Multi-hop (meeting + file) | "Does the budget file match what we decided Tuesday?" | 25 |
| Latest / changed over time | "What's the *current* launch date?" (changed twice) | 20 |
| Edited content | Answer must use the new text, never the old | 15 |
| Deleted content | Must not appear at all | 15 |
| Private content, asker not allowed | Must decline / not leak (plus the automated sweep) | 30 |
| Unanswerable / beyond horizon | Not in data, or older than the read window | 20 |
| Follow-up in a thread | "And who owns that?" | 15 |
| **Total** | | **250** |

Start with ~120 (the most common types) for the first RAG step; grow to 250 before R1. Every bug found becomes a new
question (matches the project rule "every bug gets a test").

### B3. How many questions are enough?

| Questions | Measured 90% really means (95% range) |
|---|---|
| 40 (current requirement) | 77% - 96% |
| 100 | 83% - 95% |
| 200 | 85% - 93% |
| 250 at 93% measured | 89% - 96% |

So **40 cannot prove 90%**: one miss moves the score 2.5 points. **Recommend ≥ 200** and always show the range.
For leaks: 0 leaks in N checks means the leak rate is below about 3/N; the automated sweep (every question × every
user ≈ 250 × 8 = 2,000 checks) gives < 0.15%. (Method: Anthropic's "Adding error bars to evals", Miller 2024.)

### B4. The AI judge: pitfalls and how to keep it honest

| Pitfall | Fix |
|---|---|
| Judge favours its own model family | Reference answer + **yes/no per key fact** (no 1-10 scores); for cross-model comparisons add a second judge model (another Gemini tier, or company Qwen once available) and report both |
| Position / length bias | Grade one answer at a time (Glean does this), never "A vs B" side by side |
| Changing the judge changes scores | **Pin** judge model id + prompt version; store them with every run |
| Judge simply wrong | **Calibrate:** Karthi labels ~80 answers once; judge must agree ≥ 85% (Cohen's kappa ≥ 0.6) before its numbers count; re-check 20 answers per release |
| Noise between runs | Temperature 0; for model comparisons run twice and check stability |

**Fair model comparison (Gemini now, open models later):** same 250 questions, same frozen index, same prompts, same
pinned judge. Compare **question by question** (paired), report the difference with a range; only call a winner if
the range excludes 0. Record model id, prompt hash, index version, embedding model for every run.

### B5. Tools

| Tool | Verdict for Max |
|---|---|
| **pytest + own ~200 lines** (Hit@k, recall, MRR, nDCG, leak, canary) | **Use.** Offline, no dependency |
| **Own judge prompts** via Max's model client (metered by `gemini_cost`) | **Use.** Provider-neutral; modelled on RAGAS faithfulness + Glean groundedness |
| RAGAS / DeepEval / TruLens | Good metric ideas, but own LLM wrappers and changing definitions. Borrow ideas; optional one-off cross-check |
| ARES | Strong statistics (~150 human labels, fine-tuned judges). Too heavy for R1 |
| Arize Phoenix | Local open-source trace viewer. Optional later for debugging |
| promptfoo | Model-vs-model matrices; adds Node. Not needed |

My recommendation: **no eval framework in R1**. Our own small code is easier to read and keeps the model swappable.

### B6. When each test runs, and cost

Cost basis: flash-lite $0.25 in / $1.50 out per 1M tokens (`docs/research/ai-stack.md`).

| Run | What | When | Cost per run |
|---|---|---|---|
| **Retrieval tests** | 250 questions, frozen `world/` index, **cached embeddings** (stored on disk by model + text hash) | Every `run.py test` | **$0** (new questions: < $0.01) |
| **Leak + stale sweep** | Every question × every simulated user; timeline of edits/deletes | Every `run.py test` | $0 |
| **Answer sample** | 60 rotating questions, full agent + judge | Nightly (or before each merge) | ~$0.30-0.50 **(estimate)** |
| **Full answer run** | All 250 + judge | Before each step is "done" and before any model/prompt switch | ~$1.50-3 **(estimate)**: ~$0.005-0.01 per answer + ~$0.002 per judgement |
| **Judge calibration** | Karthi labels 80 (once), 20 per release | Once + per release | Human time only |

**Conflict to decide:** the daily cap is $1 and a full end-to-end run must be ≤ $0.20. A full 250-question answer
run costs more. Suggest a **separate, visible eval budget** in the cost meter (e.g. $5/week).

### B7. Production monitoring (after R1 goes live)

| Signal | Why |
|---|---|
| Thumbs up/down per answer (Teams has a bot feedback button **(unverified, check in sim)**) | Each thumbs-down is reviewed; may become a test question (with the user's OK) |
| "No answer" rate | Glean found no-answers and weak grounding predict users leaving |
| Same person re-asks within 2 min | Silent dissatisfaction (Glean mines these) |
| Source-link clicks **(hard in Teams; verify)** | Are sources useful? |
| Weekly chart of these + cost + latency (health view) | Drift after a model/prompt change shows fast |

---

## What this means for the plan
1. **Add a reranker stage** to Part 6, behind a switch, kept only if the tests show a gain (local cross-encoder
   = new local model, needs Karthi's OK; or a flash-lite rerank call).
2. **Add a "query this sheet" tool** for sums and filters (Part 7).
3. **Change K-4 from 40 to ~250 questions**, built from planted facts.
4. **Part 8 = this evaluation plan** + canary leak tests.
5. **Decide the eval budget.**

## Sources
- Anthropic, Contextual Retrieval (2024): https://www.anthropic.com/news/contextual-retrieval
- Anthropic, statistical approach to evals / Miller, Adding Error Bars to Evals: https://www.anthropic.com/research/statistical-approach-to-model-evals , https://arxiv.org/abs/2411.00640
- Microsoft, Semantic indexing for Copilot (updated 2026): https://learn.microsoft.com/en-us/microsoftsearch/semantic-index-for-copilot
- Microsoft 365 Copilot transparency note: https://learn.microsoft.com/copilot/microsoft-365/microsoft-365-copilot-transparency-note
- Glean, hybrid vs vector RAG: https://www.glean.com/blog/hybrid-vs-rag-vector ; AI Evaluator: https://glean.com/blog/glean-ai-evaluator
- Slack, How we built Slack AI to be secure and private: https://slack.engineering/how-we-built-slack-ai-to-be-secure-and-private/ ; enterprise search: https://slack.engineering/how-we-built-enterprise-search-to-be-secure-and-private/
- Notion, Two years of vector search: https://www.notion.com/blog/two-years-of-vector-search-at-notion
- Atlassian Rovo announcement (no engineering detail published, vendor claims): https://www.atlassian.com/blog/announcements/team25-rovo-for-all
- Vespa on Perplexity (vendor-written): https://blog.vespa.ai/perplexity-show-what-great-rag-takes/
- Dust docs, RAG vs table queries: https://docs.dust.tt/docs/understanding-retrieval-augmented-generation-rag-and-the-search-method-in-dust
- Elastic, hybrid retrieval with RRF: https://www.elastic.co/search-labs/blog/improving-information-retrieval-elastic-stack-hybrid
- OpenAI file search defaults: https://developers.openai.com/docs/assistants/tools/file-search
- LlamaIndex production RAG: https://developers.llamaindex.ai/python/framework/optimizing/production_rag/
- Dropbox Dash evaluation blueprint: https://dropbox.tech/machine-learning/practical-blueprint-evaluating-conversational-ai-at-scale-dash
- RAGAS metrics: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/ ; ARES (NAACL 2024): https://arxiv.org/abs/2311.09476 ; promptfoo RAG guide: https://promptfoo.dev/docs/guides/evaluate-rag/
- LLM-judge reliability (2025-26): https://arxiv.org/html/2510.09738v1 , https://mlflow.org/articles/llm-judge-calibration/
