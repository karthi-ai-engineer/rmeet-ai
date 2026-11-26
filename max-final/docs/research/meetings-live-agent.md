# Research: Max as a live meeting agent (26 Nov 2026)

Scope: everything **after** the transcript line (speaker + time), plus the live loop: "was Max called?", live
understanding, "what did I miss?", when Max may speak, latency, cost, failures. ASR models and endpointing are in
`meetings-asr.md`. Anything we could not confirm is marked **(not verified)**.

## Answer first
1. **Keep the cascaded pipeline** (audio → ASR → text → brain → TTS). Every product that works in group meetings does this, and we need the text anyway for notes and citations.
2. **"Was Max called?" = code first, small LLM check second.** Name match ("Max", "Mac", "Macs") + position rules + a 30 s follow-up window; the cheap LLM only checks unclear cases. Research shows LLMs are bad at deciding *on their own* when to speak in a group.
3. **Live understanding = one small "meeting state"** (topics, decisions, action items, numbers, each linked to transcript lines), patched every ~2 min from only the new lines. About **$0.10 per meeting hour** on flash-lite.
4. **Max speaks only when spoken to, and only when the floor is free.** It stops within one audio frame when someone talks (2+ words). Spoken = 1–2 sentences. Details, sources and long answers go to the meeting chat.
5. **Realistic latency:** chat answer 3–7 s, spoken answer 3–5 s (simple) or 5–8 s (needs a search), with a short "One sec, checking" when a tool is needed. The weak spots are LLM first-token time and Kokoro on a laptop CPU. Both must be measured.

| Decision | Recommendation for R1 |
|---|---|
| Architecture | Cascaded, per-speaker streams, text "meeting feed" in the middle. No speech-to-speech model. |
| Addressee detection | Rules on ASR text (fuzzy "Max" + position + follow-up window), LLM check only for unclear cases. No proactive talking. |
| Live state | LLM patch every 2 min or 40 lines. Code keeps the transcript, join/leave times, timestamps. |
| "What did I miss?" | State items before the person joined + raw lines since the last patch → short private recap. |
| Speaking | Only when addressed by voice, floor free ≥0.6 s, barge-in on, max ~2 sentences, rest in chat. |
| Actions | Never act from voice alone. Confirm card in chat (same approvals as chat). |
| Model | Provider-neutral client. Measure TTFT with thinking off/minimal before trusting the voice budget. |

---

## 1. How real systems build live agents

| System | How it hears / triggers | How it answers | Lesson for Max |
|---|---|---|---|
| **Pipecat** (open source) | Pipeline of processors passing *frames* (audio, text, control). VAD and turn strategies emit "user started/stopped speaking". | When the user talks over the bot, an `InterruptionFrame` (system frame, skips queues) cancels LLM, TTS and unplayed audio. **Only the text actually spoken is saved** to the history. Options: min-words before interrupting, a backchannel model ("uh-huh" is not an interruption). [Pipecat interruptions](https://docs.pipecat.ai/pipecat/fundamentals/interruptions) | Copy the ideas: cancel-everything signal, "only what was spoken counts", min-words rule. |
| **LiveKit Agents** | Endpointing delay 0.5 s min / 3.0 s max; turn-detector model picks inside that range. | Interruption needs ≥0.5 s speech; "false interruption" after 2.0 s silence → resume. Preemptive generation on by default (start LLM on the final transcript). [LiveKit tuning](https://docs.livekit.io/agents/logic/turns/tuning/) | Good default numbers. Both frameworks are built for **one user**; group rules are ours to add. |
| **Otter Meeting Agent** (Mar 2025) | Wake phrase "Hey Otter". | Voice or meeting chat. Uses meeting history. Admin can turn voice off. [BusinessWire 25 Mar 2025](https://businesswire.com/news/home/20250325249430/en/Otter.ai-Breaks-%24100M-ARR-Barrier-and-Transforms-Business-Meetings-Launching-Industry-First-AI-Meeting-Agent-Suite), [Otter blog](https://otter.ai/blog/otter-meeting-agent-your-new-collaborative-teammate) | Explicit wake word, not "AI decides". |
| **Talk to Fireflies** (Jun 2025) | "Hey Fireflies" or typed `/ff` in chat. | **Chat by default**, voice optional, muted unless triggered. Orb shows idle / thinking / speaking. [Fireflies guide](https://guide.fireflies.ai/articles/8186888414-talk-to-fireflies-in-live-meetings), [blog](https://fireflies.ai/blog/talk-to-fireflies-perplexity/) | Chat-first, voice opt-in; show a visible state. |
| **Zoom AI Companion** | Side panel questions over the live transcript; presets "Catch me up", "Was my name mentioned?", "Action items". | Private panel. Only knows what was said while it was running. [Cornell IT](https://it.cornell.edu/zoom/zoom-ai-companion-attendee-quick-start) | Catch-up is a standard feature; private. |
| **Google Meet** "Take notes" + "Ask Gemini" (Aug 2024 / Sep 2025) | "Summary so far" for late joiners, refreshed while notes run. Ask Gemini: private questions, catch-up. | Private. Cannot answer about the time before you joined unless notes were already running. [Meet help](https://support.google.com/meet/answer/14754931), [Workspace blog Sep 2025](https://workspaceupdates.googleblog.com/2025/09/ask-gemini-in-google-meet.html) | Rolling summary refreshed every few minutes is enough. |
| **Microsoft Facilitator** | Live notes from the transcript; "may take a few minutes" to appear. Agenda and tasks. Chat not used as grounding. | Notes in a Loop page anyone can edit. [MS support](https://support.microsoft.com/en-us/office/facilitator-in-microsoft-teams-meetings-37657f91-39b5-40eb-9421-45141e3ce9f6) | Minutes-level freshness is accepted by users. |
| **Read.ai** | Live dashboard: talk time, engagement, running summary. [ZoomInfo 2026](https://pipeline.zoominfo.com/sales/read-ai-features) | Coaching, not Q&A. | Not our use case. |

**Research on group conversations (important):**
- GPT-4o addressee recognition in 3-person dialogue: **80.9 % vs 80.1 % chance**. Only ~20 % of turns name the addressee. [Inoue et al., IWSDS 2025](https://arxiv.org/abs/2501.16643)
- "Speak or Stay Silent" (Interspeech 2026): 120K decision points from meetings; 8 recent LLMs "consistently fail" zero-shot at deciding when to speak; fine-tuning added up to 23 points. [arXiv 2603.11409, v2 24 Nov 2026](https://arxiv.org/abs/2603.11409)
- LLM agents in multi-user rooms over-respond to turns meant for others. [arXiv 2610.07732, Oct 2026](https://arxiv.org/abs/2610.07732)
- Apple: an LLM over ASR text + the previous query cuts false alarms for **follow-ups** by 20–40 % at 10 % false rejects. [arXiv 2411.00023, 2024](https://arxiv.org/abs/2411.00023)
- "Inner Thoughts" (CHI 2025) makes proactive group agents better, but it is a research system. [arXiv 2501.00383](https://arxiv.org/abs/2501.00383)

**Conclusion:** products use an explicit name/wake word and answer mostly in chat or a private panel. Letting an LLM
decide freely when to join in does not work well yet. R1: no proactive speaking.

## 2. Addressee detection ("is this for Max?")

**Stage A, code (every final ASR line, ~0 ms, free):**

| Signal | Rule | Strength |
|---|---|---|
| Name at start | `^(hey |ok |so )?(max|mac|macs|max's|maks)[,.]?\s` | Strong → for Max |
| Name at end of a question | `..., max\??$` | Strong |
| Name mid-sentence as a vocative | "can you, Max, pull..." (name between commas/pauses, followed by a verb/question) | Medium → Stage B |
| Name as a subject/object | "Max said", "ask Max", "Max's slide", "talked to Max" | Weak → usually not for Max; Stage B if a person named Max is in the roster or Max spoke recently |
| Follow-up window | Same speaker, within **30 s** after Max's reply ended, question/command form, no other name | Medium → Stage B |
| Typed chat `@Max` | Always for Max | Definitive |
| "Max, stop" / "never mind" | Stop speaking immediately (handled in the barge-in path, not the brain) | Definitive |

- Variants come from real ASR mistakes. Build the list from tests, not guesses. Ask the ASR for word confidence and
  keyword boosting of "Max" and roster names (see `meetings-asr.md`).
- **A human called Max in the meeting** (roster check): only "start/end vocative" counts; everything else goes to Stage B.
  Tell admins they can rename the bot (e.g. "Maxi") if this is common **(product question, not verified as needed)**.

**Stage B, cheap LLM (only candidates, ~5–30 per hour):** input = last 4–6 lines with speakers, roster, whether Max
just spoke (~400–700 tokens). Output: `{for_max: yes|no|unsure, request: "..."}`. `unsure` → Max stays silent but
posts nothing; optional small "Did you mean me?" chat hint only after a follow-up window **(design choice)**. To save
time, Stage B can run **in parallel** with the start of the answer and cancel it on "no".

**Trade-off:** a false trigger (Max talks when not asked) annoys the whole room; a missed trigger costs one repeat.
So tune for **few false triggers**. Targets to test: **≤1 false trigger per 2 meeting hours**, **≤5 % missed** real
requests (missed ones can still be typed in chat).

**How to measure:** scripted meetings where each line is labelled "for Max / not". Report false accepts per hour and
the false-reject rate (FA at a fixed FR, as Apple does), split by case (start, mid, end, follow-up, human Max, ASR variant).

## 3. Live understanding (keep the meeting state cheap)

**Code keeps (no LLM):** append-only transcript lines `{id, speaker, t_start, t_end, text, confidence}`;
join/leave times per person; what Max said (only the spoken part, like Pipecat); meeting start, agenda from the invite.

**LLM keeps one "meeting state" (JSON, ≤2,000 tokens):** current topic + topic list with time ranges, decisions,
action items (owner, due), open questions, numbers/facts mentioned. **Every item stores the line ids it came from**
(citations, audit, notes).

**Update policy:** every **2 min or 40 new lines**, whichever first, and only when there are new lines. Input =
instructions + current state + **only the new lines**. Output = a **patch** ("add/update/close these items; nothing
new = empty"). This is the "incremental notes" pattern: ASAPP's live system adds only new bullets
([arXiv 2510.06677, Oct 2025](https://arxiv.org/abs/2510.06677)); online meeting summarization policies are compared
in [arXiv 2502.03111, Feb 2025](https://arxiv.org/abs/2502.03111). If the state grows past its cap, compress closed topics.

**How much transcript per call:**

| Call | Context sent |
|---|---|
| State patch | state + new lines (~400–1,000 tokens) |
| "Max, ..." answer | state + last **3–5 min** raw lines (~600–1,200) + tool results (RAG) |
| Detail from earlier | brain calls a tool `meeting_transcript(query or time range)` over the stored lines, not the full transcript |
| "What did I miss?" | state items with time < join time + raw lines since the last patch |
| After the meeting | full transcript (~12k tokens/hour) → notes (agreed flow in `09-cards.md`) |

**"What did I miss?"** Join time comes from the roster/gateway. Code selects state items from before the join
(decisions, action items, topics), plus anything with the person's name, plus unsummarized recent lines. The LLM writes
a 4–6 line recap with links to transcript times. Default: **private** (1:1 chat or a private message), like Zoom and
Meet. If someone joined before Max, say so honestly ("I joined at 10:05, so I can't cover before that").

**Cost per meeting hour** (flash-lite at $0.25 in / $1.50 out per 1M tokens; speech ≈ 12k tokens/hour):

| Item | Per hour | Cost |
|---|---|---|
| State patches | 30 × (~3.2k in, ~250 out) | ~$0.035 |
| Stage B addressee checks | 30 × (~600 in, ~30 out) | ~$0.006 |
| Answers | 10 × 2 LLM calls × (~8k in, ~300 out) | ~$0.05 |
| Catch-ups | 3 × (~5k in, ~400 out) | ~$0.006 |
| **Total live** | | **≈ $0.10 / hour** (≈ $0.12 on 3.5 Flash-Lite at $0.30/$2.50) |

ASR, VAD and TTS are local: no API cost, but they need compute (a GPU server for 4 streams is advised; see ASR doc).
Prices: [Gemini pricing page, read 26 Nov 2026](https://aistudio.google.com/docs/pricing). These are estimates; the
`gemini_cost/` meter gives the real figure in tests.

## 4. Turn-taking and speaking in a group call

**When Max may speak (all must hold):** (1) addressed by **voice** (typed questions get chat answers); (2) the floor is
free: no speech on any stream for **≥0.6 s** right before audio starts; (3) the answer is short. If the floor stays
busy for **>5 s**, drop the voice and post in chat ("Answered in chat"). R1: Max never speaks unprompted.

**Barge-in:** while Max talks, any participant stream with **≥0.5 s speech and ≥2 words** → stop within one audio
frame, cancel LLM/TTS, save only the spoken part (LiveKit/Pipecat defaults). Backchannels ("mm", "yeah") don't stop it.
Don't resume after an interruption; offer the rest in chat.

**Echo:** Teams gives the bot other people's streams, each tagged with the speaker. Max's own voice should not come
back as a participant stream **(not verified: test on a real tenant)**. Guards anyway: drop any line tagged with
Max's own participant id; ignore lines whose text matches what Max is saying right now.

**Latency budget (from the end of the person's speech):**

| Stage | Typical | Notes |
|---|---|---|
| Endpoint (turn end) | 0.5–0.8 s | ASR doc. Shorter after a "Max, ..." start (likely a question). |
| ASR final | 0.1–0.3 s | Streaming ASR. |
| Addressee check | 0 s (rules) / 0.5–1.5 s (Stage B, in parallel) | |
| LLM first token | 0.5–1.5 s **(not verified)** | Artificial Analysis lists 4–6 s time-to-first-*answer*-token for 3.1 Flash-Lite with its default thinking ([AA, Nov 2026](https://artificialanalysis.ai/models/gemini-3-1-flash-lite/providers)). Must measure with thinking off/minimal. |
| Tool call (RAG) + 2nd LLM call | +1–2.5 s | Only when a lookup is needed. |
| TTS first audio (Kokoro) | ~0.3 s GPU, ~1–3.5 s CPU | [Kokoro-FastAPI](https://github.com/skyiron/Kokoro-FastAPI-TTS) (older i7: 3.5 s). |
| Gateway → Teams | ~0.1–0.2 s **(not verified)** | |
| **Total spoken** | **~3–5 s simple, ~5–8 s with a search** | Single-user voice agents aim for ~0.8 s and see P50 1.4 s / P95 3.4 s in practice ([HF playbook](https://huggingface.co/blog/dvalle08/voice-agent-latency-playbook), [AWS 800 ms rule](https://builder.aws.com/content/3JDFAfXBiuwPP5MPzgf4RUWSAIp/the-800ms-rule-budgeting-latency-for-a-real-time-voice-agent-on-aws)). |
| **Total chat** | ~3–7 s | Well inside the 15 s target. |

**Tricks:** stream LLM text → TTS sentence by sentence; start the answer on the final transcript (preemptive);
pre-load Kokoro voices; if a tool is needed and nothing is spoken within ~1.5 s, say once "One sec, checking."
(pre-made audio, no LLM). Show "thinking" in chat too.

**Chat vs voice:** voice = the direct answer in 1–2 sentences ("Q1 revenue was 4.2 million euros"). Chat = the same
answer + source links + details. Lists, tables, catch-ups and anything with many numbers: chat only.

## 5. Failure handling

| Problem | What Max does |
|---|---|
| ASR gets a name or number wrong | Boost roster/project names in ASR. Max **repeats the key part of the question** in its answer ("Q1 revenue for the EU team was ..."), so a wrong hearing is visible. The chat copy shows the transcript line it used. |
| Low confidence / unclear request | "Sorry, I didn't catch that. Could you repeat, or type it in chat?" Once only; second time → chat. |
| Request that changes something (task, email, meeting) | Never from voice alone. Post a confirm card in chat; say "I've put it in the chat for you to confirm." |
| Noisy stream | Per-stream VAD thresholds; ignore very short/low-confidence fragments for triggering; still keep them in the transcript, marked. |
| Max triggered by mistake | "Max, stop" / "never mind" stops it instantly; barge-in also stops it. Logged as a false trigger for tuning. |
| Max misheard and answered wrongly | People correct by voice or chat; the correction is a follow-up. After the meeting, notes can use a slower, more accurate second ASR pass over the recording **(option, see ASR doc)**. |
| LLM slow or down | After ~10 s: "I'm slow right now, I'll answer in chat." Never block the transcript or state updates. |

## 6. Is this the right approach? (cascaded vs speech-to-speech vs hybrid)

| Criterion | (a) Cascaded (ours) | (b) Speech-to-speech / realtime audio LLM | (c) Hybrid: ASR always + audio model when addressed |
|---|---|---|---|
| 4+ people | Per-speaker streams → per-speaker text; addressee rules work on text | Built for **one user stream**. Mixed audio loses speaker labels; 4 separate sessions = 4× cost; tends to answer everyone | Same as (a) for listening |
| Names / numbers | Visible text; keyword boosting; confidence scores; easy to test | Hidden; can't boost names; errors invisible | Audio model can re-check the one utterance; but two "versions" of what was said |
| Cost / hour | ≈ $0.10 LLM + local ASR/TTS | Gemini Live: $0.005/min audio in ⇒ **$0.30/h per stream, $1.20/h for 4**, + $0.018/min out ([pricing](https://aistudio.google.com/docs/pricing)); context re-billing per turn **(not verified)** | (a) + a few cents per addressed turn |
| Latency | ~3–5 s spoken | 0.2–0.8 s claimed (Moshi ~200 ms, Qwen3-Omni 234 ms first packet, cold start) ([Qwen3-Omni](https://arxiv.org/abs/2509.17765)) | Faster spoken answer only |
| Swappable / open models | Any LLM, any ASR, any TTS; each part replaceable | Locks the whole loop to one provider. Open options exist (Qwen3-Omni 30B-A3B, Apache 2.0; Moshi) but need a GPU and are made for 1:1 | Two model families to maintain |
| Tools + RAG | Mature (text LLM function calling) | Weaker and model-dependent ([Deepgram, May 2026](https://deepgram.com/learn/speech-to-speech-vs-cascade-voice-agent-architecture), [Dialpad arXiv 2605.15104](https://arxiv.org/abs/2605.15104)) | Mature (text) if the audio model only listens |
| Audit (notes, citations) | Text transcript is the source of truth | **No transcript by default**; we'd need ASR anyway | Transcript from ASR, but the answer may rely on audio the transcript doesn't show |

**Verdict: our direction is right; don't change it.** Speech-to-speech wins only on speed and voice feel, and a meeting
does not need sub-second replies (people accept a few seconds from a teammate). It loses on everything we must have:
speaker labels in a group, a transcript, tools, cost, and swappability. Because we need ASR for the transcript anyway,
(b) would be an *extra* system, not a replacement.

**What to keep an eye on:** (c) as an R2 experiment, narrowly: when an addressed utterance has low ASR confidence on a
name or number, send that one audio clip (a few seconds) to an audio-capable model as a second opinion. Open models with
audio input exist, so this stays swappable. Not in R1.

**Two honest risks in our direction:**
1. **LLM first-token time.** If flash-lite with minimal thinking is really ~4 s, spoken answers become 6–10 s. Mitigation:
   measure first; voice stays short with chat as the main channel; the model client is swappable to a faster model.
2. **Model name drift.** Artificial Analysis marks Gemini 3.1 Flash-Lite as deprecated and points to 3.5 Flash-Lite
   **(not verified; Google's pricing page still lists 3.1 at $0.25/$1.50 and 3.5 at $0.30/$2.50)**. Check before building.

## 7. Recommended R1 architecture

```
Teams call ──► C# media gateway (per-speaker 16 kHz PCM, speaker id) ──► Python
  per stream: VAD → streaming ASR (+ endpoint) → transcript line {id, speaker, t, text, conf}
                                                     │
        ┌───────────────── meeting feed (append-only, stored) ────────────────┐
        ▼                         ▼                                           ▼
 Addressee gate             State updater (LLM, every 2 min)          Barge-in watcher (code)
 rules → LLM if unsure      patch: topics/decisions/actions/numbers    stops TTS on 2+ words
        │                   (each item → line ids)
        ▼
 Brain (same agent loop as chat): context = state + last 3–5 min + speaker; tools = RAG, meeting_transcript, ...
        │  stream text
        ├──► meeting chat (full answer + sources)       actions → confirm card (approvals)
        └──► floor check → Kokoro (sentence streaming) → gateway → Teams
```

| Part | Code or LLM | State |
|---|---|---|
| VAD, ASR, endpointing, speaker tags | Code + local models | Transcript lines |
| Addressee gate | Code rules; LLM only if unsure | Follow-up window per speaker |
| Meeting state | LLM patch, code merges and validates line ids | State JSON + history |
| Join/leave, "what did I miss?" selection | Code | Roster with times |
| Answer | Brain (LLM + tools) | Normal conversation history |
| Floor check, barge-in, echo guard | Code | "Max speaking" flag, spoken text |

**Estimates:** LLM ≈ $0.10 per meeting hour; chat answer 3–7 s; spoken 3–5 s simple, 5–8 s with a search (to be measured).

**Tests with a simulated multi-speaker meeting** (`teams_sim` plays per-speaker audio from `world/` scripts, each line labelled):

| # | Case | Pass if |
|---|---|---|
| 1 | "Max, what was Q1 revenue?" / "..., Max?" / "Can you, Max, ..." | Answered; correct number with source |
| 2 | "I talked to Max yesterday" with a human Max in the roster; "Max said..." | No trigger |
| 3 | ASR variants "Mac, ..." "Macs ..." | Triggered |
| 4 | Follow-up "And Q2?" within 30 s (same speaker / other speaker) | Same: answered; other: Stage B decides |
| 5 | Two people talk at once, one addresses Max | Right person answered, by name |
| 6 | Someone talks while Max speaks; someone says "mm-hm" | Stops < 300 ms; doesn't stop |
| 7 | Floor busy for 6 s after the question | Answer goes to chat |
| 8 | Late joiner at minute 25 asks "what did I miss?" | Recap covers only before join; key facts match the script |
| 9 | Noise added; a number misheard | Asks to repeat or shows the heard number |
| 10 | "Max, create a task for Anna" | Confirm card, nothing done without approval |
| 11 | 60-minute meeting | False triggers ≤1/2 h, missed ≤5 %, cost ≤ $0.15, p50/p95 per stage logged |
| 12 | Decisions/action items | Live state recall vs script ≥ 80 % **(target to agree)** |
