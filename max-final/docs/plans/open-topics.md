# Open topics: everything still to decide before coding (agent side)

**Rule (Karthi, 25 Nov 2026): discuss and decide ALL of these, one part at a time, before writing code.
Don't miss any.** Tick a topic only when Karthi agrees.

## Needed before coding R1
| # | Topic | Status | Notes |
|---|---|---|---|
| 1 | **Memory** (6 parts: working memory + compaction, thread memory, people facts, episodic, forgetting, Max Personal) | ✅ Agreed (26 Nov) | `docs/plans/memory.md`, research `docs/research/memory-*.md` |
| 2 | **Max Personal / scope** (one Max per channel, per person, or both) | ✅ Agreed (26 Nov) | `memory.md` Part 6 |
| 3 | **RAG: the live knowledge system** (own big design session) | 🔄 Started 26 Nov | Import, extraction (+ OCR pipeline), chunking, keyword + embeddings, **live updates** (new/edited/deleted posts, files, transcripts), privacy filter, link briefs (U45), evaluation, **keep personal (non-work) chat messages out of the index?** Research: `docs/research/knowledge.md`, `storage.md` |
| 4 | **Tool contracts** (exact input/output of each R1 tool) | ⬜ | Like `make_document` in use-cases §9 |
| 5 | **Max's personality and answer style** | ⬜ | Tone, length, sources panel, error wording. Karthi: **friendly and flexible in chat, precise when working** |
| 6 | **Message and card formats** | ⬜ | Approval, Continue, living plan card, notes, digest, brief, chase, Stop |
| 7 | **Meetings, text mode** | ⬜ | Following a live meeting, "Max…" detection, what did I miss, notes consent |
| 8 | **Skill files list** | ⬜ | Which task types get one (writing them comes later) |
| 9 | **Simulated team world + test set** | ⬜ | Designed part by part |
| 10 | **Build plan** | ⬜ | Coding steps, last |

## Later (parked, own sessions)
Agent watcher dev tool (asked: R1?) · extractor/OCR details (part of RAG) · routines (U38) · third-party apps
(MCP, Planner, Jira, Notion) · Document Agent · ask_agent · live voice · Teams simulator (UI) design.
