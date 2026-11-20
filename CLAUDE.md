# rmeet-ai: rules for Claude

Read `HANDOVER.md` first: it has the full status, architecture, setup and next steps.

## How to work with Karthi
- Keep explanations **short, simple, plain language**. Small tables or simple diagrams are good; long
  technical reports are not. Lead with the answer, explain new terms, end with one clear question if needed.
- Act as team lead of a small expert team (researcher, UI expert, system designer, tester, developer).
- Test end to end before saying something works; report failures honestly.

## Hard rules
- **Models: ONLY the company Qwen (TW gateway, `unsloth/Qwen3.8-27B-NVFP4`) + Gemini.** No GPT, whisper,
  embedding models or other gateway models, even though the gateway offers them.
  Qwen = thinking/answers/agents (send `chat_template_kwargs: {enable_thinking: false}`).
  Gemini = hearing (speech-to-text `gemini-3.5-flash-lite`) and voices (TTS `gemini-3.8-flash-lite-tts`).
- **Secrets never go in chat or git.** Keys live only in `voice-chat/.env` (copied to `max/.env` by
  `simulations/teams/register_app.py`). When showing env files, hide the values.
- **Git: do not add Claude as a contributor/co-author** (no `Co-Authored-By` trailer). Commits are Karthi's.
- **Max is a separate program** in `max/` and must only use real Microsoft contracts (Bot Framework,
  Graph, calling API). Everything fake-Microsoft lives in `simulations/teams/`; the meeting app/UI in
  `simulations/rmeet/`; the world data in `simulations/planning-department/`. Max never reads the world
  files directly.
