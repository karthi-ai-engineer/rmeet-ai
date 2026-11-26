# Open topics: everything still to decide before coding (agent side)

**Rule (Karthi, 25 Nov 2026): discuss and decide ALL of these, one part at a time, before writing code.
Don't miss any.** Tick a topic only when Karthi agrees.

## Needed before coding R1
| # | Topic | Status | Notes |
|---|---|---|---|
| 1 | **Memory** (6 parts: working memory + compaction, thread memory, people facts, episodic, forgetting, Max Personal) | ✅ Agreed (26 Nov) | `docs/plans/06-memory.md`, research `docs/research/memory-*.md` |
| 2 | **Max Personal / scope** (one Max per channel, per person, or both) | ✅ Agreed (26 Nov) | `06-memory.md` Part 6 |
| 3 | **RAG: the live knowledge system** (own big design session) | ✅ Agreed (26 Nov): `docs/plans/07-rag.md` (8 parts + Decisions 1-4) | Import, extraction (+ OCR pipeline), chunking, keyword + embeddings, **live updates** (new/edited/deleted posts, files, transcripts), privacy filter, link briefs (U45), evaluation, **keep personal (non-work) chat messages out of the index?** Karthi's concerns (26 Nov): how much history to read when Max joins, scale (a company lives in Teams: 100k+ messages, many files), telling users what Max hasn't read yet ('knowledge horizon'), always up to date and correct. Research: `docs/research/rag-history-scale.md`, `rag-live-updates.md`, `docs/research/knowledge.md`, `storage.md` |
| 4 | **Tool contracts** (exact input/output of each R1 tool) | ✅ Agreed (26 Nov): `docs/plans/05-tools.md` (4 parts) | Like `make_document` in use-cases §9 |
| 5 | **Max's personality and answer style** | ✅ Agreed (26 Nov): `docs/plans/08-personality.md` (4 parts) | Tone, length, sources panel, error wording. Karthi: **friendly and flexible in chat, precise when working** |
| 6 | **Message and card formats** | ✅ Agreed (26 Nov): `docs/plans/09-cards.md` (5 parts; visual design pass before implementation) | Approval, Continue, living plan card, notes, digest, brief, chase, Stop |
| 7 | **Max Meeting: separate module** (Karthi, 26 Nov: own section, can grow into many use cases) | ⏸️ **Paused (26 Nov): finish chat Max first**, then continue. Own list in `docs/plans/meeting/01-overview.md` (7 parts); research `docs/research/meetings-live.md`, `meetings-asr.md`, `meetings-live-agent.md` | Max joins the call, own live speech-to-text pipeline, understands + answers live, notes |
| 8 | **Skill files list** | ✅ Agreed (26 Nov): `docs/plans/10-skill-files.md` | Which task types get one (writing them comes later) |
| 9 | **Simulated team world + test set** | ✅ Agreed (26 Nov): `docs/plans/11-sim-world.md` (scale test later) | Designed part by part |
| 10 | **Build plan** | ✅ Agreed (26 Nov): `12-build-plan.md` (steps + "R1 done"); UI design `13-ui-design.md` | Coding steps, last. **Must include: make Step 0 provider-neutral** (settings `LLM_*` instead of `GEMINI_*`, an OpenAI-compatible backend for company-server models, a provider-neutral usage meter) |

## Later (parked, own sessions)
Agent watcher dev tool (asked: R1?) · extractor/OCR details (part of RAG) · routines (U38) · third-party apps
(MCP, Jira, Notion; no Microsoft Planner: Karthi 26 Nov, own plans only) · Document Agent · ask_agent · live voice.
