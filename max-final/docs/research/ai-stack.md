# AI stack for Max final

Researched 25 Nov 2026. **Measured** = run on the office laptop (i5-1334U, 32 GB, no GPU).

## Short answer

| Part | Pick | Why |
|---|---|---|
| Agent loop | **Pydantic AI** (pinned). Backup: plain hand-written loop. | Works with Qwen + Gemini, built-in approvals, fake models for offline tests. LangGraph is overkill. |
| Brain | **Qwen** (thinking off); **gemini-3.1-flash-lite** as automatic fallback | Qwen is free and fast; Gemini covers outages. |
| Hearing | **Local faster-whisper `small.en`**; Gemini as fallback | **Measured**: one 5 s turn in 1.9 s, near-perfect, $0, no quota. |
| Voice | **Kokoro local**; Gemini TTS as fallback | **Measured** ~0.4 s of work per 1 s of speech, $0, no quota. |
| Live meeting | **Hand-rolled** asyncio pipeline + Silero VAD | Teams already splits audio per speaker; Pipecat is built for 1 person ↔ 1 bot. |
| Tests | Fake models + recorded cassettes + small eval set | Offline tests cost $0. |

## 1. Agent framework

| Option | Approvals | Offline tests | Qwen + Gemini | Verdict |
|---|---|---|---|---|
| LangGraph (prototype) | `interrupt()` + checkpointer | We had to build our own fake model and cassettes | Via LangChain adapters (5 packages) | **Overkill**: our flow is one loop, not a graph. |
| Plain loop (~150 lines) | Our own pending-actions table | Easy | We write the Gemini adapter (tool calls + thought signatures are fiddly) | **Backup**. |
| **Pydantic AI** | Tool marked `requires_approval` ends the run with the pending calls; resume later with approve/deny ([docs](https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/)) | `TestModel`, `FunctionModel`, block real calls in tests ([docs](https://pydantic.dev/docs/ai/guides/testing/)) | OpenAI-compatible provider (`extra_body` carries `enable_thinking:false`), native Gemini, `FallbackModel` | **Pick**. |
| Google ADK | `require_confirmation`, still experimental ([docs](https://adk.dev/tools-custom/confirmation/)) | Weaker | Gemini-first; Qwen only via LiteLLM | No. |
| OpenAI Agents SDK | Yes | OK | Other models via LiteLLM; traces go to OpenAI unless switched off | No: OpenAI-centric. |

Approvals: a card can wait hours. We save the message history (plain JSON) plus pending calls in SQLite and resume on click; no checkpointer. Who may approve, expiry and safety blocks stay in our code. Keep the prototype's rules: ≤8 tool rounds, ≤20 tools offered, every tool call gets exactly one result, runs started by outside content (emails, files) get no sending tools.

## 2. Which model for which job

| Job | Main | Fallback |
|---|---|---|
| Thread answers + tool calls | Qwen, thinking off, temp ≤0.3 (1.5–2 s/call) | flash-lite (thinking minimal) |
| Meeting notes | Qwen, thinking **on** (not time-critical) | flash-lite (1M context) |
| Live replies | Qwen, thinking off, short answers | flash-lite |
| Simulated colleagues | Scripted lines from `world/`; Qwen only for improvised replies | flash-lite |

**Fallback rule:** 10 s timeout per try, 1 retry. If Qwen fails twice, use Gemini for 2 minutes, then try Qwen again. Warm both up at start. Every Gemini call goes through one meter (log + daily $ cap), like the prototype's `gemini_usage/meter.py`.

**Gemini prices** (paid tier, per 1M tokens, [pricing](https://aistudio.google.com/docs/pricing)): flash-lite $0.25 text in / $0.50 audio in / $1.50 out. `gemini-3.8-flash-lite-tts` $0.50 in / $6 audio out (doubles on 1 Jan 2027). `gemini-3.5-transcribe-live` ≈ $0.01/min.

**Cost per demo run** (based on the prototype's real log of 24 Nov: one agent call ≈ $0.001, one notes call ≈ $0.005):

| Item | Qwen + local voice | Everything on Gemini |
|---|---|---|
| 20 questions × 3 calls | $0 | $0.06 |
| 2 sets of meeting notes | $0 | $0.01 |
| Hearing 30 min | $0 | $0.03 |
| Max speaks 3 min | $0 | $0.03 |
| **Total** | **≈ $0** | **≈ $0.15** |

The whole prototype dev day cost $0.25. Money is not the problem; **free-tier quota errors (429) are**. Use a paid key with a daily cap.

## 3. Hearing (speech-to-text)

**Measured.** 36.5 s test file, 6 speakers (made with Kokoro), lines with numbers and names; int8, 8 threads.

| Model | 36.5 s file | One 5 s turn | Text quality |
|---|---|---|---|
| faster-whisper `base.en` | 1.4 s | **0.6 s** | Near-perfect |
| faster-whisper `small.en` | 4.8 s | 1.9 s | Near-perfect |
| Parakeet TDT 0.6B v2 (ONNX, `onnx-asr`) | 3.2 s | 0.9 s | Near-perfect (first load downloads ~600 MB) |
| Gemini flash-lite (prototype log) | — | ~2.1 s incl. network | Good, but quota errors |

All three local models wrote the same text; the only real slip was "LiftLine" → "Lift Line". Caveat: clean synthetic voices are easier than a real meeting (accents, noise, crosstalk). Re-test on a real recording.

**Pick faster-whisper**: one library, Silero VAD included, and it accepts a hint list of names and product words (Parakeet via ONNX does not). `small.en` by default, `base.en` if live feels slow. Moonshine v2 ([paper](https://arxiv.org/abs/2602.12241)) is a faster streaming option for later if needed.

## 4. Voice (TTS)

| | Kokoro local | Gemini TTS |
|---|---|---|
| Speed | **Measured**: 33 s of speech in 14 s (incl. warm-up); one sentence ≈ 1 s | 2–5 s; first call can stall 20–60 s |
| Cost / limits | $0, no quota | ≈ $0.009 per spoken minute; free tier ran out after 3 lines |
| Sound | Good, a bit flat | More natural, takes style hints |

**Pick Kokoro.** Speak sentence by sentence: play the first sentence while the next one is made. Keep Gemini TTS as fallback and for recorded films. I found nothing clearly better on this CPU (Piper is faster but sounds worse; not tested here).

## 5. Live meeting pipeline

```
20 ms frames tagged per speaker → Silero VAD per speaker → turn ends after ~0.7 s silence
 → STT → line (speaker, text) → is Max addressed? (his name, or a question right after he spoke)
 → same brain as chat (live mode: short spoken answer, few tools, 3 s budget)
 → Kokoro sentence by sentence → frames paced 50/s
Barge-in: someone else talks > 0.3 s while Max speaks → stop sending audio.
```

Expected wait from end of question to Max's first word: 0.7 (silence) + 0.6–1.9 (STT) + ~2 (Qwen) + ~1 (first sentence) ≈ **4–5.5 s**. OK for a demo; say "one moment" first if it feels slow.

- Teams tags audio per participant, so no speaker-separation model is needed.
- [Pipecat](https://github.com/pipecat-ai/pipecat) (v1.x, has Kokoro, Silero, Gemini) fits 1 person ↔ 1 bot. A group meeting where Max speaks only when addressed fights its turn model and adds many dependencies. Borrow its ideas, hand-roll ~300 lines (like the prototype's `calling.py`).
- One brain: `brain.handle(event)` for a channel message, a finished transcript or a live utterance. Only prompt style, tools and time budget change.
- Real Teams later: Microsoft's real-time media SDK is .NET/Windows-only, so a thin .NET relay will be needed. The simulator can already use the same frame format.

## 6. Testing AI code

| Layer | How | Cost |
|---|---|---|
| Unit | `FunctionModel` scripts ("calls `search`, then answers") test tools, approvals, limits, errors | $0 |
| Cassettes | Record real replies once (key = hash of model + messages + tools), replay in CI; a missing recording fails and never calls the model | $0 after recording |
| Eval set | 30–50 questions from `world/` with must-have facts and expected tool calls; run on real Qwen before each demo; "contains" checks, flash-lite judge only for fuzzy cases | cents |
| Voice | Kokoro-made WAVs with known text → STT error under a threshold | $0 |
| E2E | Full simulated day on a fixed clock | small |

Demo steadiness: fixed clock and data, temperature 0, scripted colleagues, warm-up at start, pre-flight check (Qwen, Gemini key, Kokoro, STT loaded), and a visible "fallback used" badge.

## Top 5 risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | Qwen gateway hangs or is down on demo day | Warm-up, timeout + retry, auto-fallback to flash-lite, pre-flight check |
| 2 | Gemini quota errors (429) | Paid key + daily cap; Gemini only as fallback |
| 3 | Live replies too slow: STT, TTS and simulator share one low-power CPU | Sentence-by-sentence voice, `base.en` option, short answers, laptop on power; measure end to end first |
| 4 | Qwen picks wrong tools or invents facts | ≤20 tools, eval set before demos, approval on every outside action |
| 5 | Library/model churn (Pydantic AI moves fast; Gemini ids and prices change) | Pin versions; model ids only in config; meter shows prices |
