# Research: team and people memory, forgetting, per-person vs team (25 Nov 2026)

## Headline
- **A fact is a row with evidence**: person, kind, value, valid from/to, and links to its source messages. Old facts are **closed, not overwritten** (Zep/Graphiti), so Max can say "until Oct it was Aiko, now Ken".
- **The model proposes, code decides.** Mem0's 2025 paper let the LLM choose ADD/UPDATE/DELETE. Its April 2026 algorithm **dropped that** (ADD-only, rank by date), which suggests LLM deletes were not reliable enough to keep.
- **A fact inherits the privacy of its source.** Learned in a 1:1 means private. The R-8 filter covers facts like chunks.
- **Work facts only.** No moods, health or performance judgements. People see, correct and delete their facts (U39).
- **Cheap:** ~$0.01–0.05/day for a 10-person team.

## 1. What products do

| Product | Memory scope | Notable |
|---|---|---|
| ChatGPT | Per user. Optional **project-only** memory | Deleting a chat does **not** delete a memory made from it. Deleted-memory logs are kept up to 30 days |
| Claude | Per user, **separate memory per project** | The user edits "topics". **Org owners can't read members' memory**. Incognito chats are never remembered |
| M365 Copilot | Per user (saved + inferred + custom instructions), in a hidden mailbox folder | Admins can find and delete it via eDiscovery. Retention policies **don't apply**. Memory actions are **not audited** |
| Teams Channel Agent | **One per channel** (posts, Planner, meetings). Not allowed in 1:1 or private chats | Its memory behaviour is not documented |
| Slack AI | No memory. It sees only what the asker can see now | Nothing stored |
| Notion Agent | A normal **page** used as a "memory bank" | People edit it like any page |
| Glean | People/team/project graph. "Who knows what" from authorship, activity and HR data | Permission-filtered |
| Zep / Graphiti | Temporal graph. Each fact has valid_at / invalid_at | A contradicting fact **invalidates** the old one, and history is kept |
| Mem0 | Per user_id | 2026: ADD-only, newest dated fact wins at search time |
| Letta | Small always-in-prompt "blocks" plus archival search | Blocks can be **shared** by agents, with a lost-update risk |

**Lesson:** the big assistants keep memory **per person, private by default, editable by the person**. Team knowledge comes from the shared sources, not from a shared "memory". Microsoft uses **two agents**: personal Copilot and a per-channel agent.

## 2. Facts about people

### What to extract (and what not)
| Extract (work facts) | Example | Source |
|---|---|---|
| Owns / handles | "Ken handles supplier contracts" | Posts, meeting notes, task owners (M-5) |
| Expertise | "Aiko knows the FY27 cost model" | Files they wrote, questions they answered |
| Decision made by | "Ken decided to delay launch" | Decisions log (A-3): link, don't copy |
| Preference (self-stated) | "Karthi prefers short answers", "No pings before 10:00" | The person tells Max |
| Availability / role change | "On leave until 3 Dec", "Moved to sales" | Posts, the person |

**Never extract:** mood or sentiment ("seems annoyed"), health, private life, performance ratings ("slow"), guesses about intent. The EU AI Act bans workplace **emotion recognition** from biometrics (since Feb 2025). Guesses from text aren't banned, but they are the creepy part, so leave them out.

### Store and replace
- **Key** = (person, kind, subject), for example (Ken, handles, "supplier contracts").
- **Same value:** add the evidence and update `last_seen`.
- **Different value, same key:** close the old fact (`valid_to` = date of the new evidence) and open the new one. This is Graphiti's invalidation, done **in code by key match**, not by an LLM.
- **Evidence date** = when it was said, not when it was processed, so a late backfill can't make old news win.

### Confidence (3 levels, not a number)
| Level | Meaning | Use |
|---|---|---|
| `confirmed` | Said by the person, or corrected by them | Anywhere it is allowed |
| `seen` | Said by others, 2+ pieces of evidence | With source and "as of" date |
| `weak` | 1 piece of evidence | Only via a tool: "I think, based on [link]" |

**Decay:** facts unseen for **120 days** become stale ("as of Jul"). Weak facts are deleted after **180 days**.

### See, correct, delete (U39)
- In a 1:1: "What do you know about me?" returns a card listing each fact with its source and buttons **Correct / Delete / Keep private**.
- A correction becomes `confirmed`. A delete writes a **tombstone** (person, kind, subject), so the fact is **not re-learned** from old messages.
- Anyone can say "that's wrong" about a team fact. Max marks it disputed and asks the person concerned. Only the person (or the Admin, for legal requests) deletes facts about them.

## 3. Team memory vs person memory, and privacy

| Scope | Examples | Who sees it |
|---|---|---|
| **Team** | Who handles what, decisions, glossary ("H1 = Apr–Sep"), team habits ("weekly sync Mon") | Team members, in that team's channels |
| **Channel / meeting** | Facts learned in a private channel or a meeting | Members of that channel or meeting only |
| **Person, public-ish** | Expertise, role, out-of-office | Team members, with source |
| **Person, private** | Style preferences, things said in a 1:1 | Only that person. Used to shape replies to them, **never quoted** to others |

Rules:
1. Every fact stores the `audience` of its **narrowest** evidence (channel, meeting, or `person:<id>`). The same SQL filter as for chunks (R-8) decides where it may be used.
2. A fact learned only in a 1:1 stays private, even if it is about the team. "Ken is leaving", said in a 1:1, never reaches the channel.
3. **Style preferences** are applied silently wherever that person asks, and are never stated aloud.
4. Leak tests: 1:1 → channel, 1:1 → digest, and private channel → standard channel must all return nothing.

## 4. Forgetting

| Event | What Max does | When |
|---|---|---|
| Teams message deleted (K-2) | Remove its evidence. A fact with **no evidence left** is deleted | Same sync run |
| Message edited | Re-extract | Next run |
| "Forget this part" in a meeting (M-6) | Delete the range, its chunks and the facts that rest only on it, plus a tombstone | Immediately |
| "Forget that about me" | Delete + tombstone | Immediately |
| Person leaves the team | Delete private facts. Team records (decisions, past owners) stay | After 30 days |
| Retention | Weak facts 180 days. The log keeps "fact X deleted by Y", **not the content** | Nightly |

Make deletes real in SQLite: `PRAGMA secure_delete=ON`, delete FTS and vector rows in the same transaction, and keep backups for at most 30 days.

**Law basics (not legal advice):**
- **GDPR**: Art. 15 (see your data) and Art. 17 (erasure). The "What do you know about me?" card covers both.
- **Japan APPI**: since 2022, a person can ask a company to stop using or delete retained data **when it is no longer needed** or when its use could harm them (Art. 35). A further amendment was promulgated in July 2026 (fines, AI use). *Its effect on deletion is unverified.*
- The Admin needs one "export / delete everything about person P" command (Copilot does this through eDiscovery).

**Audit (R-11):** log every fact add, close, correct and delete. Copilot does not audit memory actions, so Max can do better here.

## 5. One agent, many teams, many people: options

Personal assistants (ChatGPT, Claude, Copilot) keep memory **per person** with optional **project walls**. The Channel Agent is **one per channel** and stays out of 1:1s. Letta shares "blocks" between agents.

| Option | How | Pros | Cons |
|---|---|---|---|
| **A. One Max, walled per team** | Each fact has `team_id`. In a channel: that team only. In a 1:1: the person's teams, with answers labelled "[Planning]". Preferences are global | Simplest: one database, one filter, same as R-8 | 1:1s can mix teams ("the budget" of which team?) |
| **B. Team layer + personal layer** | A as base, plus a private store per person (preferences, notes, own to-dos) that follows them across teams. Used only in their 1:1 and in replies to them | Clear: "the team knows / I know". Like ChatGPT/Claude projects | Two scopes to explain and test. More leak tests |
| **C. Personal agent + team agent** | Each person has their own agent and store, and reads team memory through the audience filter (Copilot + Channel Agent model) | Strongest walls. Each agent stays simple | Two bots confuse users. More setup and cost. The two may disagree |

In any option: label the team in 1:1 answers, ask "which team?" when it is ambiguous, and never copy facts between teams.

## 6. Concrete simple design (works for A or B)

```sql
person(id, aad_id, name, active)
fact(id, person_id NULL,        -- NULL = team fact
     team_id, kind, subject, value,
     valid_from, valid_to NULL, last_seen,
     confidence,                -- confirmed|seen|weak
     audience,                  -- narrowest: channel:/meeting:/person:
     status)                    -- active|stale|disputed
fact_evidence(fact_id, source_ref, quote, said_by, said_at)
fact_tombstone(person_id, team_id, kind, subject, created_at, by)
memory_log(id, at, actor, action, fact_id, reason)  -- no content after delete
```

**Extraction job**
- Runs **nightly** over new messages and **after meeting notes are approved** (M-6), so rejected parts are never learned. "Remember that ..." is saved at once (L2 tool).
- Input: new messages per thread plus the active facts of the people named (max 20). Output: JSON proposals `{person, kind, subject, value, evidence_ref, self_stated}`, checked by Pydantic. Code applies the section 2 rules and tombstones, and drops unknown kinds.
- Cost: ~50–100k input tokens/day for 10 people on a Flash-class model ≈ **$0.01–0.05/day**.

**How the agent reads memory**
- **Always in the prompt:** a small "people card" for the asker and the people mentioned. ≤5 confirmed/seen facts each, ≤300 tokens, already audience-filtered.
- **Tools:** `who_handles(topic)`, `get_person(name)` (with sources), `remember` / `forget` (L2, own facts). Start with FTS. Add gemini-embedding-2 only if `who_handles` misses paraphrases.

| Number | Value |
|---|---|
| Facts per person | ~20–50 |
| People card in prompt | ≤5 facts/person, ≤300 tokens |
| Stale after | 120 days unseen |
| Weak facts deleted after | 180 days |
| Leaver cleanup | 30 days |
| Tests | 1:1 fact never in a channel · correction survives re-extraction · deleted message removes a single-evidence fact · "forget this part" leaves no fact |

## Sources
- [ChatGPT Memory FAQ (saved memories, project-only, 30-day logs)](https://help.openai.com/en/articles/8590148-memory-faq)
- [Claude: chat search and memory (project memory, admin can't see)](https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context) · [Claude memory announcement](https://claude.com/blog/memory)
- [Manage Copilot personalization and memory (Learn, updated Nov 2026)](https://learn.microsoft.com/copilot/microsoft-365/copilot-personalization-memory) · [MC1158329 memory update](https://mc.merill.net/message/MC1158329)
- [Introducing Channel Agent in Teams](https://techcommunity.microsoft.com/blog/microsoft365insiderblog/introducing-channel-agent-in-teams/4455451) · [Agents in Teams FAQ](https://support.microsoft.com/topic/f7317b78-fd53-4cfe-88f0-f0a0751a4150)
- [Security for AI features in Slack](https://slack.com/help/articles/28310650165907)
- [Notion 3.0 release (agent memory page)](https://notion.com/releases/2025-09-18)
- [Glean knowledge graph](https://glean.com/product/knowledge-graph) · [Glean people and teams indexing](https://developers.glean.com/indexing/people-teams-identity)
- [Zep: temporal knowledge graph (arXiv 2501.13956)](https://arxiv.org/abs/2501.13956) · [Zep blog: beyond static graphs](https://blog.getzep.com/beyond-static-knowledge-graphs/)
- [Mem0 paper (arXiv 2504.19413)](https://arxiv.org/abs/2504.19413) · [Mem0 README (April 2026 ADD-only algorithm)](https://github.com/mem0ai/mem0)
- [Letta memory blocks](https://docs.letta.com/guides/agents/memory-blocks) · [Letta shared memory](https://docs.letta.com/guides/agents/multi-agent-shared-memory)
- [EU AI Act: workplace emotion recognition ban](https://legalblogs.wolterskluwer.com/global-workplace-law-and-policy/the-prohibition-of-ai-emotion-recognition-technologies-in-the-workplace-under-the-ai-act/)
- [APPI 2022 amendment (DLA Piper)](https://www.dlapiper.com/insights/publications/2022/03/updates-for-the-amendment-of-japans-act-on-the-protection-of-personal-information) · [APPI 2026 amendment (A&O Shearman)](https://www.aoshearman.com/en/insights/ao-shearman-on-data/amendments-to-the-act-on-the-protection-of-personal-information-promulgated)

## Not verified
- How the 2026 APPI amendment affects deletion rights (I only read secondary summaries).
- Whether the Channel Agent keeps memory (not documented).
- Zep invalidation details: taken from the blog and summaries. I did not re-read the full paper.
- How Glean scores expertise (not public). The cost figures are estimates, to be measured on demo data.
