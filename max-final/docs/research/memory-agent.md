# Research: Max's working memory, compaction and episodic memory (25 Nov 2026)

## Headline
- **With a 1M window, Max compacts for cost and accuracy, not for space.** Accuracy drops as input grows, even when the model finds every fact ([Chroma "context rot"](https://research.trychroma.com/context-rot); [Du et al., EMNLP 2025](https://arxiv.org/abs/2510.05381): 14–85% drops). Cost also grows fast: every step re-sends everything before it.
- **Inside a run, compaction is plain code, no AI:** old tool results become one-line stubs that keep ids. A small **plan + findings notepad** stays outside the history, so it is never cut. Anthropic, OpenAI, Google ADK and Pydantic AI all ship this same idea.
- **Thread summary: update it, don't rewrite it.** Only the messages that just left the recent window are merged into a summary with fixed sections. Full rewrites slowly lose detail ("context collapse", [ACE, ICLR 2026](https://arxiv.org/abs/2510.04618)).
- **Episodic memory: yes, but small.** Keep one short "run card" per run (free, from code). Learn "lessons" only from **human** 👎 and corrections, never from Max's own guesses. Recent studies show self-written lessons can make agents worse.
- **No memory framework needed.** Six SQLite tables and about 300 lines of Python. Extra cost is about **$0.05–0.10 per day**.

## 1. How others do it

| System | Inside one run | Across conversations |
|---|---|---|
| **Anthropic** | Tool-result clearing: default trigger 100k tokens, keeps the last 3 results, can exclude tools, leaves a placeholder ([docs](https://platform.claude.com/docs/en/build-with-claude/context-editing)). Server-side compaction. Guidance: clear tool results first (the lightest step), keep notes outside the context, sub-agents return 1–2k-token summaries ([context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)) | Memory tool: files the agent reads and writes. Memory + clearing gave +39% on their eval ([news](https://www.anthropic.com/news/context-management)). Claude app: memory per project |
| **OpenAI** | Responses API `compact_threshold`, or `/responses/compact`, which returns a sealed (encrypted) item ([docs](https://developers.openai.com/api/docs/guides/compaction)). Agents SDK: `SQLiteSession` + compaction wrapper ([SDK](https://openai.github.io/openai-agents-python/sessions/)) | ChatGPT: "saved memories" (a list of facts) + "reference chat history" (a summary that keeps updating), both can be switched off ([help](https://help.openai.com/en/articles/8590148-memory-faq)) |
| **Google ADK** | `EventsCompactionConfig`: summarise every N turns with overlap, or when over a token count, keeping the last N events ([docs](https://adk.dev/context/compaction/)) | `SessionService` (events + state) separate from `MemoryService` / Memory Bank, which pulls facts out of finished sessions ([docs](https://adk.dev/sessions/memory/)) |
| **Letta (MemGPT)** | Core memory blocks pinned in context, edited by the agent | Recall (search raw history), archival (vector store), "sleep-time" agent rewrites the blocks in the background ([docs](https://docs.letta.com/guides/agents/architectures/memgpt), [blog](https://www.letta.com/blog/agent-memory)) |
| **Mem0** | — | The AI pulls facts out, then ADD/UPDATE/DELETE them. About 90% fewer tokens than sending the full history ([paper](https://arxiv.org/abs/2504.19413)) |
| **Zep / Graphiti** | — | Facts with `valid_at` / `invalid_at`. An old fact is marked invalid, not deleted ([paper](https://arxiv.org/abs/2501.13956)) |
| **LangMem / Cognee** | — | LangMem: facts, episodes, and prompt rewrites from feedback ([blog](https://blog.langchain.com/langmem-sdk-launch)). Cognee: graph + vector pipeline, heavy for us |
| **Pydantic AI** | `ProcessHistory` (history processor) runs **before every model request**, including steps inside a run. Its output **replaces** the history. Cutting between a tool call and its result is "repaired" silently, so cut only at turn boundaries. `CompactionPart` holds a summary ([docs](https://pydantic.dev/docs/ai/core-concepts/message-history/)). The Harness package has `ClearToolResults` (keep 3, `[tool result cleared]`) and `TieredCompaction` (cheap steps first, AI summary last) but is 0.x, so its API may change ([docs](https://pydantic.dev/docs/ai/harness/compaction/)) | — |

Two results that shape the design:
- **Incremental summaries beat full rewrites.** Factory tested on 36k real messages. Summarising only the part just cut, and merging it into fixed sections (goal, decisions, changes, next steps), beat OpenAI's and Anthropic's compaction. All methods were weak at tracking *which files were touched*, so track that in code ([Factory](https://factory.ai/news/evaluating-compression)).
- **Learning from its own runs is fragile.** ReasoningBank (Google) gains up to +8 points from lessons it writes itself ([paper](https://arxiv.org/abs/2509.25140)). But with the same token budget, a plain agent matched or beat such memory modules ([EMNLP 2026](https://arxiv.org/abs/2606.15017)). Lessons written after a chance failure pushed agents to the worse tool 11.6% of the time, against 0.4% normally ([2026](https://arxiv.org/abs/2610.33029)).

## 2. Working memory inside one run (mode 3 especially)

**Why it matters (our numbers).** A 30-step research run where each tool result is about 3k tokens:

| | Context at step 30 | Input tokens over the whole run | Cost |
|---|---|---|---|
| No clearing | ~96k | ~1.6M | ~$0.41 |
| Clear all but the last 3 results | ~20k | ~0.45M | ~$0.12 |

Without clearing, mode 3 can't stay near its $0.10 budget. Don't count on Gemini's cache discount: clearing changes the prompt start (which breaks the cache), and one forum report says flash-lite stopped giving the discount ([forum](https://discuss.ai.google.dev/t/gemini-3-1-flash-lite-implicit-cache-stopped-applying-cost-savings-june-30-2026/173779), **unverified**).

**Three steps, cheapest first** (in one `ProcessHistory` function in `runner.py`):

| Step | When | What | AI cost |
|---|---|---|---|
| 1. Clear | Context > **40k** tokens | Every tool result except the **last 3** becomes a stub: `[cleared] search_knowledge("Q1 budget") → T12, F3, M5 (8 results). Open by id if needed.` Keep the tool call and its arguments. Clear down to **< 25k** in one go (fewer cache breaks) | 0 |
| 2. Summarise | Still > **120k** (several big files kept) | Older turns → one `CompactionPart` with fixed sections (goal, done, findings with ids, next). Cut only at turn boundaries | ~$0.01 |
| 3. Stop | > **200k** or the budget is used up | Go to the CONTINUE card with progress so far. Continue starts fresh: request + plan + notes + last 3 results | 0 |

**The notepad (mode 2 and 3).** A `run_notes` table holds the plan (steps with status) and **findings** (one line each + source ids). The agent writes to it with an L1 tool, `note(text, source_ids)`. Instruction: "when you read something useful, note it with its id before it is cleared" (this is Anthropic's memory-tool pattern). The notepad (max ~2k tokens) is added to every request (dynamic instructions or the history processor), so compaction never touches it.

**Never dropped:**
1. The person's request and any message they send during the run.
2. The situation block (who asked, audience, task type, budget).
3. The plan + findings notepad.
4. Results of action tools (`post_message`, `propose_tasks`, `update_task`, `record_decision`, `schedule_job`) and every approval or denial: these are facts about what Max **did**.
5. Every source id seen: kept in a `run_sources` table, so the citation check ("remove ids no tool returned") uses the table, not the trimmed history.
6. Full tool results stay in the audit table (for debugging), not in the context.

Mode 1 needs none of this (code gives each step small input). Mode 2 (8 steps) rarely reaches 40k.

## 3. Thread memory (recent + rolling summary + search)

**Keep the agreed three layers.** One detail to fix: "recent" = **every message after the summary's end point** (at least 20, at most ~70). That way no message falls in a gap between the summary and the recent window.

**Update (anchored, incremental):**
- **When:** a background job (the existing `jobs` loop) once **50** messages have piled up after the summary's end point. No wait for the user.
- **Input:** the current summary (JSON) + the 50 old messages with ids → **output: a list of changes** (`add` / `update` / `close` items), Mem0-style. Code applies them. The model never rewrites the whole summary.
- **Cost:** ~4k tokens in, ~0.6k out ≈ **$0.002** per update.

**What goes in (fixed sections, each item = text + message ids + date):**

| Section | Example |
|---|---|
| Purpose | "Planning the Osaka launch" |
| Decisions | "Price stays ¥980 (Ken, 3 Nov) [m4512]" |
| Open questions | |
| Commitments / actions | who, what, due, status |
| Key facts and numbers | |
| Max's own promises here | "I said I'd remind on Fridays" |

**Against drift:**
- Code caps the size at ~1,000 tokens. Closed items are moved out first; they stay findable with search.
- Every item has message ids, so it can be checked and opened.
- Never a free-text rewrite.
- **Rebuild from the raw messages** every 20 updates (~1,000 messages, ~$0.02–0.08). Keep the old version for comparison.
- A test-set check: does the summary still contain the planted decisions?

## 4. Episodic memory: should Max remember its runs?

**Yes, in two small pieces:**

| Piece | What | How it's made | Used for |
|---|---|---|---|
| **Run card** (every run) | request, task type, asker, thread, short answer (first 300 chars), sources, tools, outcome, 👍/👎, correction text | Code, from the `runs` table. **No AI, free** | "What did you tell me last week?", "Did I already do this?", the dashboard, test cases. Searchable with FTS |
| **Lesson** (rare) | "In #sales, 'the deck' means the latest file in /Pitch" | Made only from a 👎 with a reason, or a correction ("no, I meant…"). The AI writes one line, scoped to channel / person / task type | Top **3** matching lessons (≤300 tokens) added at PREPARE |

**Rules:**
- A correction that is a **fact about a person** goes to people-facts, not to lessons.
- Lessons start as `proposed` and are listed for an admin to keep or delete. Lessons used often become candidates for skill files (LangMem's "procedural memory", done by a person).
- A lesson that isn't used for 90 days is retired.

## 5. Recommended design (summary)

**SQLite tables:** `run_notes`, `run_sources`, `run_history` (compacted messages as JSON via `ModelMessagesTypeAdapter`, for resuming after a pause), `thread_summaries(thread_id, json, covers_until, updates_since_rebuild, version)`, `run_cards` (+FTS5), `lessons(scope, task_type, text, from_run, status, uses, last_used)`.

**Context at PREPARE** (~10k tokens): instructions 2k, situation 0.5k, tools 2k, thread summary ≤1k, recent messages ≤4k, lessons ≤0.3k.

**Cost per day** (team of 20, 1,000 messages/day, 100 runs/day):

| Item | Per day |
|---|---|
| Thread summary updates (20 × $0.002) + rebuilds | ~$0.05 |
| Clearing inside runs | $0 (and it saves ~$0.25 per mode-3 run) |
| Fallback summaries (rare) | ~$0.01 |
| Run cards | $0 |
| Lessons (a few) | <$0.01 |
| **Total** | **~$0.05–0.10** (the cap is $1) |

**Tests (offline, `FunctionModel`):** clearing keeps call/result pairs, ids and action results; the notepad survives; citations pass after clearing; no gap between summary and recent.

## Could it break the demo?

| Risk | Fix |
|---|---|
| Max cites a source it can no longer see, and misquotes it | Note findings with ids. The stub says "open by id" |
| The summary loses a decision | Fixed sections, message ids, rebuild every 20 updates, test check |
| A bad lesson changes behaviour | Only from humans, admin review, max 3 per run |
| A Pydantic AI history repair hides a bug | Cut only at turn boundaries. Test it |

## Not verified
- I read the current Pydantic AI docs but did not check them against version 2.74 specifically.
- Whether dynamic instructions are re-run on every step inside a run: check before choosing between that and the history processor.
- The Gemini flash-lite cache discount.
- Claude Code's auto-compact percentage (only third-party sources).
- How often Letta's sleep-time agent runs.
- Teams 👍/👎 feedback buttons for bots (believed to exist: check the Teams SDK).
