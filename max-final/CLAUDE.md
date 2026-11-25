# Max final: rules for Claude

**Max** is an AI teammate for Microsoft Teams. This folder is the professional rebuild.
The old prototype lives in `../max-demo`: read it for ideas, **never modify it**.

## How to work with Karthi
- Explain things **short and simple**, plain language, small tables. Lead with the answer.
  End with clear questions.
- Act as team lead of a small expert team: researcher, architect, UI/UX designer,
  frontend expert (Apple/Google-level polish and animation), developer, tester.
  Use sub-agents for research, reviews and testing when it helps.
- Karthi's ideas are not automatically right. Research first, point out flaws honestly,
  then recommend the best option.
- **Decide before building.** Tech stack, AI stack, frameworks and folder layout are fixed
  and written down (in `docs/decisions.md`) before any feature code.

## Hard rules
- **Models allowed:**
  - Company Qwen gateway: `unsloth/Qwen3.8-27B-NVFP4` (send `enable_thinking: false` for speed).
    **Not used for now (25 Nov 2026): no access. Gemini only.** Keep the model client provider-neutral.
  - Gemini: cheapest first, `gemini-3.1-flash-lite`; other Gemini models only when needed.
    Keep Gemini usage visible and cheap.
  - A local voice server on the PC (Kokoro).
  - Other **local** models only if they run well and fast on this PC (agree with Karthi first).
  - No GPT or other gateway models.
- **Secrets never in chat or git.** Keys live only in `.env` files. When showing an env file,
  hide the values (`GEMINI_API_KEY=***`).
- **Git:** never add Claude as co-author (no `Co-Authored-By` line). Commits are Karthi's,
  from the `karthi-ai-engineer` account only. Commit only when Karthi asks.
- **Test end to end** before saying something works. Report failures honestly.
- **Keep it simple.** Few folders, clear names, no clever abstractions. A new developer
  should understand the layout in 2 minutes.
- **Follow `docs/decisions.md`** (approved stack). Change it only with Karthi's OK.
- **Agent framework stays swappable:** Pydantic AI only inside `max/agent/runner.py`.
  Tools, prompts, model clients, approvals and history are plain Python, so LangGraph can
  replace the runner later.

## How we build (agreed 25 Nov 2026)
Small, tested steps, one at a time. Each step adds one complete, visible feature.
1. **Plan:** a 1-page plan of what we build and how we check it. Karthi approves.
2. **Tests first** for core logic.
3. **Build.**
4. **Review:** a separate reviewer sub-agent checks the code with fresh eyes.
5. **Test** end to end, plus a demo check in the browser.
6. **Done:** docs updated, Karthi commits. One git branch per step.

"Done" = `run.py test` passes, it works end to end in the browser, earlier steps still work, and docs
are updated. Every bug found gets a test. Never start the next step while one is half done.

## Folder layout (draft, final after the stack decision)

| Folder | What goes there |
|---|---|
| `max/` | Max, the bot. Talks only through real Microsoft contracts (Bot Framework, Graph, calling). |
| `gemini_cost/` | Gemini usage meter + cost dashboard. Every Gemini call goes through it. Shared by all programs. |
| `teams_sim/` | Demo only: fake Teams app (UI) + fake Microsoft cloud that Max connects to. |
| `world/` | Demo data: the team, channel posts, files, past meetings. Max never reads it directly. |
| `voice/` | Local voice server (text-to-speech on the PC). Model files are not in git. |
| `tests/` | `unit/` = fast, offline, free. `e2e/` = full demo runs. |
| `docs/` | Decisions, research, plans. |
| `data/` | Runtime data (databases, logs, caches). Not in git. |

## Open topics (to discuss before building)
- Demo review feedback: what went wrong, what must change.
- Real Teams: which permissions to ask IT for, and how to develop without disturbing
  other chats (separate test team / dev tenant), **or** keep a fully simulated Teams for the demo.
- Final tech stack, AI stack, frontend stack.
