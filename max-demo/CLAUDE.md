# rmeet-ai: rules for Claude

Read `HANDOVER.md` first: it has the full status, architecture, setup and next steps.

## How to work with Karthi
- Keep explanations **short, simple, plain language**. Small tables or simple diagrams are good; long
  technical reports are not. Lead with the answer, explain new terms, end with one clear question if needed.
- Act as team lead of a small expert team (researcher, UI expert, system designer, tester, developer).
- Test end to end before saying something works; report failures honestly.

## Hard rules
- **Models: ONLY the company Qwen (TW gateway, `unsloth/Qwen3.8-27B-NVFP4`) + Gemini + a local voice server.**
  No GPT, whisper, embedding models or other gateway models, even though the gateway offers them.
  Current setup (Karthi, 24 Nov 2026): **Max** thinks and hears on the cheapest Gemini, `gemini-3.1-flash-lite`
  (`MAX_BRAIN_PROVIDER=gemini`, `MAX_GEMINI_BRAIN_MODEL`, `MAX_GEMINI_MODEL` in `voice-chat/.env`); the
  **simulated colleagues** stay on the company Qwen (send `chat_template_kwargs: {enable_thinking: false}`);
  **voices** come from a local Kokoro server on the PC (`TTS_PROVIDER=local`, `local_tts/`, not in git), with
  Gemini TTS as the alternative. Keep Gemini usage visible and cheap (usage dashboard, see README).
- **Secrets never go in chat or git.** Keys live only in `voice-chat/.env` (copied to `max/.env` by
  `simulations/teams/register_app.py`). When showing env files, hide the values.
- **Git: do not add Claude as a contributor/co-author** (no `Co-Authored-By` trailer). Commits are Karthi's.
- **Max is a separate program** in `max/` and must only use real Microsoft contracts (Bot Framework,
  Graph, calling API). Everything fake-Microsoft lives in `simulations/teams/`; the meeting app/UI in
  `simulations/rmeet/`; the world data in `simulations/planning-department/`. Max never reads the world
  files directly.
