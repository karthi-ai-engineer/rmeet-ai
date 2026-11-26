# Research: accurate retrieval for Max (chunking, search, reranking) (26 Nov 2026)

Builds on `docs/plans/07-rag.md` (Parts 5-6) and `docs/research/knowledge.md`.
Marks: **[V]** = checked in the primary source · **[S]** = from a secondary summary, not checked · **[M]** = measured by us on this laptop.

## Headline
- **The biggest wins come from the basics:** a strong embedding model, pieces that follow the document's structure
  with a clear label on top, keyword + meaning search fused together, and an agent that can search again.
- **Fancy chunking rarely pays.** Semantic, LLM, late and "contextual" chunking win in some tests but lose or tie
  in large independent studies. Structure-aware pieces + a good label are the best value.
- **Rerank only with a modern reranker.** Older cross-encoders made a strong first stage *worse* in two tests
  (gte-modernbert in Thomson Reuters' test; bge-reranker-v2-m3 in the Qwen3 paper). A modern one (Qwen3-Reranker)
  or an LLM ranking the list helps. On this laptop's CPU, local rerankers are slow (see Part 3).
- **Recommended:** hybrid search (keyword + meaning, weighted RRF) → top 40 → rerank → top 8 to the agent.
  ~1-2.5 s per search, ~$0.002 per search, everything behind swappable switches.

## 1. Chunking (where accuracy starts)

### What the evidence says
| Study | Finding |
|---|---|
| Chroma, token-level eval, 2024 [V] | Recursive splitter, 200-400 tokens, **no overlap**: recall 88-90%. 800 tokens + 400 overlap: worst (85.4%, lowest precision). LLM chunker best recall (91.9%) but slow; default semantic (Kamradt) **below average** (83.6%). Spread best-worst ≈ 8 pts. |
| Vectara, NAACL Findings 2025 [V abstract, S numbers] | Semantic chunking's cost "not justified by consistent gains"; fixed-size won on 3 of 5 evidence-retrieval sets. A better embedding model gave more (+7.4% F1) than any chunking change. |
| Caspari et al., CIKM 2026 (8 methods, 3 open embedders, up to 6M docs) [V] | Semantic, late, contextual and summary-only chunking **rarely win** significantly. **Title-enriched chunks** (label prepended) were the most robust; summary-enriched helped top-10 ranking but not recall@100. |
| NVIDIA chunking study [S] | **Page-level** best average for PDFs (0.648, least variance). Factoid questions like 256-512 tokens; analytical ones like 1,024 / page. |
| Thomson Reuters, EACL 2026 industry [V] | With a strong embedder, bigger pieces did slightly better (recall@10 63% at 512 → 67.5% at 4,096 tokens). Contextual embeddings: "minimal gains". |
| Systematic study, 36 methods × 6 domains [S] | Paragraph-group (structure-aware) chunking ~0.46 nDCG@5 vs fixed character chunks < 0.25. |
| LongMemEval (chat history), ICLR 2025 [V] | Whole conversation sessions beat single turns at top-5 (recall 0.71 vs 0.58). Adding extracted facts to the index key: +9.4% recall. |
| Late chunking (Jina) [S] | +2.7-3.6% relative nDCG@10 on BEIR; needs a long-context *local* embedder (token vectors), so not provider-neutral. |
| Dense X propositions [S] | +10 recall@20, but mostly for weak unsupervised retrievers; one LLM call per paragraph. |

**Takeaway:** follow the structure, keep pieces ~300-800 tokens, little or no overlap, put a good label on top.
Use semantic splitting only where there is **no structure** (long chat streams, long transcript monologues).

### Methods compared
| Method | Accuracy | Index cost | Complexity | For Max |
|---|---|---|---|---|
| Structure-aware (headings, slides, sheets, pages, threads, speaker turns) | Best value | Free | Low | **R1 (= Part 5)** |
| Label header (title path, file, sheet, date, people) | Most robust gain (Caspari) | Free | Low | **R1** (already in Part 5) |
| Fixed-size + overlap | Baseline; big overlap hurts | Free | Lowest | Fallback inside long sections only |
| Parent/child (small-to-big) | Good; our "open section" tool does it | Free | Low | **R1, via the agent tools** |
| Doc summary as its own piece (file, meeting) | Helps "which file/meeting" questions | ~$0.5 per backfill | Low | **R1** |
| Semantic (embedding breakpoints) | Inconsistent; helps unstructured text | Extra embeddings | Medium | **Only chats + transcripts, as A/B** |
| Contextual retrieval (LLM context per piece) | Anthropic −35% failures (−49% with BM25); others: small/none | ~$2-5 per backfill | Medium | **Later, A/B on files** |
| LLM / agentic chunking | Top recall in one small test; slow | High | Medium | Skip |
| Propositions | Gains for weak retrievers | High | High | Skip |
| Late chunking | +3% relative | Free | Needs local token vectors | Skip (not swappable) |

### Recommended pieces per content type
| Content | Piece | Size / overlap | Semantic split? |
|---|---|---|---|
| Channel thread | Post + replies = 1 piece; long: groups of replies, post (first ~150 tokens) repeated on top | ≤ 800; 1 reply overlap | No: the thread *is* the unit |
| Chat (1:1 / group, no threads) | Split into **conversations by time gap** (> 45 min quiet = new), then cap | 300-700; 2 messages overlap | **Yes, A/B:** inside a long conversation, cut where topic shifts |
| Word | Heading section; long sections cut at paragraphs; tables whole or by rows with header repeated | 300-800; none (heading path repeated) | No |
| Excel | Sheet summary piece + row blocks; **header row repeated**; block by tokens, not fixed 50 rows | ≤ 800 | No |
| PowerPoint | 1 slide + notes; tiny slides keep their own piece (citation) but deck title in label | per slide | No |
| PDF | Docling sections if headings found, else **page**; short pages joined, long pages cut at paragraphs | 300-800 | No |
| Scanned / OCR | Same as PDF; OCR quality in label ("partly OCR") | same | No |
| Transcript | Speaker-turn windows 2-3 min | ~400-700; 30 s overlap | **Yes, A/B:** topic breakpoints between turns, bounded 1-4 min |
| Max meeting notes | 1 per meeting; split by section (decisions, actions) if > 800 | ≤ 800 | No |
| File / meeting summary | 1 extra piece each (what it is, key points, people, dates) | ~150-300 | No |

Label on every piece (deterministic, free): `Budget.xlsx > Q1 > rows 1-50 · Finance channel · by Priya · changed 3 Oct`.

## 2. Ranked techniques (chunking excluded; see Part 1)
Gains are typical published ranges; our own test set decides.

| # | Technique | Typical gain | Latency | Cost / question | Complexity | Max |
|---|---|---|---|---|---|---|
| 1 | **Strong embedding model** | Biggest single lever (+7% F1 vs any chunking; Gemini embeddings beat all in TR test) | 0.2-0.4 s API | ~$0.00001 | Low | **R1** |
| 2 | **Agentic multi-step search** (search, read, search again) | Multi-hop: retrieval +up to 21 pts, QA +15 pts (IRCoT) | +1 LLM turn per step | ~$0.002 / step | Already designed | **R1** |
| 3 | **Hybrid keyword + meaning, fused** | +18% nDCG over BM25, +1-3% over dense (Elastic); naive equal RRF with BM25 *hurt* in TR test | ~20 ms | Free | Low | **R1, weighted RRF** |
| 4 | **Filters: privacy, chat, person, kind, date** | Removes whole error classes | ~1 ms | Free | Low | **R1** |
| 5 | **Time expressions → date range** ("last week") | +4 pts recall@5 on time questions (LongMemEval) | ~1 ms (code) | Free | Low | **R1** |
| 6 | **Conversation-aware query** (follow-ups) | Big on follow-ups (+25-31% P@1 on CAsT) but can hurt if over-summarised | 0 (agent writes the query) | Free | Low | **R1, by the agent** |
| 7 | **Rerank, modern model** | Qwen3-Reranker-0.6B +4 pts, 4B +8 pts over its first stage (MTEB-R); LLM listwise best on 2 of 4 sets (TR) | 1-2 s | $0-0.0015 | Medium | **R1, switch** |
| 8 | **Multi-query (2-3 phrasings in one call)** | Helps recall on paraphrases; little once a reranker is in | +20 ms per phrasing | ~Free (agent writes them) | Low | **R1** |
| 9 | **Doc summaries / extracted facts as index keys** | +9.4% recall (LongMemEval facts); summary-enriched best top-10 often (Caspari) | 0 | Index only | Low | **R1 (summary pieces)** |
| 10 | **Diversity: max 2 pieces per item** | Fewer near-duplicates in the 8 slots | ~1 ms | Free | Low | **R1** (simpler than MMR) |
| 11 | **Dedup** (hash + quoted/forwarded text) | Cleaner top 8 | Index only | Free | Low | **R1** |
| 12 | Recency boost | Helps "latest/current" questions; hurts history questions | ~1 ms | Free | Low | **R1, only when the agent asks** (`prefer_recent`) |
| 13 | Contextual retrieval | −35% to −67% failures (Anthropic) vs "rarely wins" (Caspari, TR) | 0 | ~$2-5 per backfill | Medium | **Later, A/B** |
| 14 | HyDE | Mixed; "not promising" (TR); hurts keyword search | +1-2 s | +1 call | Low | Skip |
| 15 | Old cross-encoders (bge-reranker-v2-m3, MiniLM, gte-modernbert) | **Negative** over strong embeddings (TR; Qwen3 table: 57.0 vs 61.8 first stage) | 1.3-13 s laptop CPU [M] | Free | Low | Skip (fallback only for weak embedder) |
| 16 | ColBERT / multi-vector | Strong but big index, new infra | low | Free | High | Skip |
| 17 | Separate router model | Agent already picks tool + `kind` filter | +1 call | +cost | Medium | Skip |

## 3. Reranker options
| Model | Licence | Size | Quality note | CPU latency, 50 pieces [M] |
|---|---|---|---|---|
| **Qwen3-Reranker-0.6B** | Apache 2.0 | 0.6B | MTEB-R 65.8 (first stage 61.8) | **58 s** (unusable on this laptop; GPU ~sub-second, est.) |
| Qwen3-Reranker-4B | Apache 2.0 | 4B | MTEB-R 69.8 | GPU / server only |
| mxbai-rerank-base-v2 / large-v2 | Apache 2.0 | 0.5B / 1.5B | BEIR 55.6 / 57.5 (vendor) | not run |
| bge-reranker-v2-m3 | Apache 2.0 | 0.57B | MTEB-R 57.0 (below first stage) | not run (download stalled); same size as Qwen3-0.6B |
| gte-reranker-modernbert-base | Apache 2.0 | 0.15B | Hurt recall@10 in TR test | **12.5 s** |
| ms-marco-MiniLM-L6-v2 | Apache 2.0 | 23M | English only, old | **1.3 s** |
| jina-reranker-v2 / v3 | **CC BY-NC** | — | good, but **not for commercial use** | skip |
| **LLM listwise** (flash-lite, or company Qwen later) | provider's | — | GPT-4.1 listwise best on 2/4 sets (TR); flash-lite unmeasured | ~1-2 s API (est.) |

[M] = our test, 26 Nov: Intel i5-1334U laptop, PyTorch CPU fp32, 1 question × 50 pieces of ~240 tokens, best of 3.
All models put the right piece first in this tiny synthetic check (a speed test, not a quality test). ONNX/int8 could
make them ~2-4× faster (unmeasured): still too slow for a 0.6B model on this laptop.
**So: on the laptop, rerank with the LLM; a local reranker only on a GPU machine/server.**

## 4. Embedding models (all behind `embed()`; a change = re-index once)
| Model | Licence | Dims | Context | Retrieval note | Role |
|---|---|---|---|---|---|
| **gemini-embedding-2** | API | 128-3072 (use 768) | 8k | MTEB multilingual 69.9 (Google) | **R1** |
| Qwen3-Embedding-0.6B | Apache 2.0 | 32-1024 | 32k | MTEB-Eng retrieval 61.8 | **Open fallback, CPU** |
| Qwen3-Embedding-4B / 8B | Apache 2.0 | up to 2560 / 4096 | 32k | 68.5 / 69.4 | Server with GPU |
| bge-m3 | MIT | 1024 | 8k | Dense + sparse in one model | Alternative |
| snowflake-arctic-embed-l-v2.0 | Apache 2.0 | 1024 (MRL 256) | 8k | Strong, multilingual | Alternative |
| nomic-embed-text-v2-moe | Apache 2.0 | 768 (MRL 256) | 512 | Small, multilingual | Alternative |
| multilingual-e5-large-instruct | MIT | 1024 | 512 | 53.5, older | Skip |
| embeddinggemma-300m | Gemma terms | 768 | 2k | Good small model; custom licence | Maybe |
| jina-embeddings-v3 | CC BY-NC | — | — | — | Skip |

Store the model name with every vector; never mix two models in one search.

## 5. Recommended pipeline for Max
```
agent writes: query + 0-2 alt phrasings + filters (kind, chat, person, since/until, prefer_recent)
  → privacy filter (SQL, before ranking)
  → per phrasing: keyword FTS5 top 50  +  meaning top 50        (parallel)
  → weighted RRF (k=60; meaning 1.0, keyword 0.7 to start; tune on test set)
  → dedup + max 2 pieces per item → top 40
  → rerank switch: LLM listwise on snippets | local Qwen3-Reranker-0.6B | off
  → top 8 snippets (label + ~300 chars + id) to the agent → agent opens full sections if needed
```
| Stage | Candidates | Latency budget | Cost |
|---|---|---|---|
| Query embed (1-3 phrasings, one batch call) | — | 0.2-0.4 s | ~$0.00001 |
| Keyword + meaning search | 50 + 50 per phrasing | < 0.05 s | Free |
| Fusion, dedup, diversity | → 40 | < 0.01 s | Free |
| Rerank (LLM listwise, 40 × ~120 tokens) | → 8 | 1-2 s | ~$0.0015 |
| **One search total** | | **~1.5-2.5 s** | **~$0.0016** |
| Agent answer (2-3 searches + 1-2 opens) | | p50 ~6-8 s, p95 ~15-18 s | ~$0.006-0.009 |

**Fallbacks:** reranker error or > 3 s → use fused order (never fail the search). Meaning search not yet ready for a
new item → keyword finds it. Embedding API down → keyword-only, flagged in the health view.
**Rerank choice:** default LLM listwise (works with any provider, no download, the same prompt works on the company
Qwen later); local Qwen3-Reranker (0.6B or 4B) only on a GPU machine/server (58 s on the laptop CPU). Keep "off" if
the test set shows no gain: the agent already picks from snippets, so the gain must be proven.

**How we decide (test set, Part 8):** ~60 questions with correct ids (exact words, paraphrase, numbers, follow-ups,
"last week", multi-hop, file vs chat). Measure recall@8 and recall@40 per switch: keyword only → +meaning →
+weights → +rerank → +semantic chat/transcript split → +contextual. Keep a step only if it adds ≥ 2-3 pts.

## Sources
- [Anthropic: Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval)
- [Chroma: Evaluating chunking](https://www.trychroma.com/research/evaluating-chunking)
- [Qu et al.: Is semantic chunking worth it? (NAACL Findings 2025)](https://aclanthology.org/2025.findings-naacl.114) · [Vectara blog](https://www.vectara.com/blog/is-semantic-chunking-worth-the-computational-cost)
- [Caspari et al.: When is complex chunking worth it? (CIKM 2026)](https://arxiv.org/abs/2608.16586)
- [NVIDIA: best chunking strategy](https://developer.nvidia.com/blog/finding-the-best-chunking-strategy-for-accurate-ai-responses/)
- [Thomson Reuters: Retrieval enhancements for RAG (EACL 2026 industry)](https://aclanthology.org/2026.eacl-industry.13.pdf)
- [Systematic chunking study, 36 methods (arXiv 2603.06976)](https://arxiv.org/abs/2603.06976)
- [LongMemEval (ICLR 2025)](https://arxiv.org/abs/2410.10813)
- [Late chunking (arXiv 2409.04701)](https://arxiv.org/abs/2409.04701) · [Splunk benchmark roundup](https://www.splunk.com/en_us/blog/artificial-intelligence/chunking-techniques.html)
- [IRCoT: interleaving retrieval with reasoning (arXiv 2212.10509)](https://arxiv.org/abs/2212.10509)
- [Elastic: hybrid retrieval and RRF](https://www.elastic.co/search-labs/blog/improving-information-retrieval-elastic-stack-hybrid)
- [Instructed LLM query rewriting, CAsT (arXiv 2410.07797)](https://arxiv.org/abs/2410.07797) · [Rewriting can hurt (arXiv 2509.19700)](https://arxiv.org/abs/2509.19700)
- [Query expansion best practices / HyDE limits (arXiv 2401.06311)](https://arxiv.org/abs/2401.06311)
- [Qwen3 Embedding + Reranker paper](https://arxiv.org/abs/2506.05176) · [Qwen3 blog](https://qwenlm.github.io/blog/qwen3-embedding)
- [Gemini Embedding 2 paper](https://arxiv.org/abs/2605.27295) · [Gemini pricing](https://aistudio.google.com/docs/pricing)
- [mxbai-rerank v2](https://www.mixedbread.com/blog/mxbai-rerank-v2) · [Jina reranker v3 (CC BY-NC)](https://jina.ai/models/jina-reranker-v3/)
- Licences checked on Hugging Face model cards (26 Nov 2026).
