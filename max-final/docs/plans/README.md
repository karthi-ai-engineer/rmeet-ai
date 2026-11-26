# Plans: read in number order

| File | What's inside | Status |
|---|---|---|
| `01-open-topics.md` | **Start here.** The master list: what's agreed, what's still open | — |
| `02-use-cases.md` | What Max does: 45 use cases, control levels L0-L4 | ✅ |
| `03-requirements.md` | Rules R-1…R-13, R1 scope, quality targets | ✅ |
| `04-agent-design.md` | The agent loop, modes, skill files | ✅ |
| `05-tools.md` | Every tool: exact inputs and outputs | ✅ |
| `06-memory.md` | Working memory, thread summaries, people facts, forgetting, Max Personal | ✅ |
| `07-rag.md` | Live knowledge: history, updates, extraction, pieces, search, re-rank, checks, testing | ✅ |
| `08-personality.md` | Tone, emoji signposts, answer shape, unsure/wrong/no, speaking first | ✅ |
| `09-cards.md` | All cards and message formats (visual design pass later) | ✅ |
| `10-skill-files.md` | Which task types get a skill file | ✅ |
| `11-sim-world.md` | The simulated team, its data, planted facts, and the test set | ✅ |
| `12-build-plan.md` | The coding steps in order, and what "R1 done" means | ✅ |
| `13-ui-design.md` | UI design: theme, all screens, cards, Max's chat (pictures `ui-*.png`) | ✅ |
| `14-avatar.md` | Max's avatar (identity), paused with 3 open questions | 🔄 |
| `step-0.md` | Coding step 0 (done). Later steps get their own `step-N.md` | ✅ |
| `step-1.md` | Coding step 1: any AI provider + one limits file (done, reviewed; branch `step-1`) | ✅ |

**`meeting/`** is the **Max Meeting module** (its own section, own numbered files, starting with
`meeting/01-overview.md`): Max joins calls, live speech-to-text, answers live, notes. ⏸️ Paused until chat Max is done.

**`pictures/`** holds every picture: an `.excalidraw` file (open at excalidraw.com or with the VS Code Excalidraw
extension) and/or a `.png` quick view. Names start with the topic (`rag-…`, `memory-…`, `cards-…`, `agent-loop…`).

Research behind these plans: `docs/research/`.
