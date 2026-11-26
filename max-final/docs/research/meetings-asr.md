# Live meeting speech-to-text (ASR) for Max

Research, 26 Nov 2026. Design phase only, no code. Figures come from model cards and leaderboard snapshots linked
at the end. "Not verified" means we found no first-hand source, or it is our own estimate.

## Answer first
1. Use a **true streaming** model (cache-aware FastConformer from NVIDIA), not chunked Whisper. It gives partial text
   every 80-560 ms and final text about **0.4-0.8 s after someone stops talking** (our estimate, not verified).
2. R1 model: **Nemotron Speech Streaming EN 0.6B** at 0.56 s chunks (AMI 11.9 % WER, 7.1 % average), one stream per speaker.
   **Parakeet Unified EN 0.6B** is the challenger (6.5 % average at 0.56 s). We pick the winner by testing on our own audio.
3. Endpointing: **Silero VAD + Smart Turn v3.2** (it listens to the audio and judges whether the sentence is finished,
   BSD licence, runs on CPU in 10-65 ms). Hard cut at 15 s for long monologues. Silero VAD on its own is not enough.
4. "Max": **boost the word in the ASR** (per-stream phrase boosting in NeMo), detect it **in the text** (including partials),
   then confirm with a cheap "is this addressed to Max?" check. A separate audio wake-word model only if tests say we need it.
5. Our overall plan (unmixed per-speaker audio, then our own ASR, then text to a swappable LLM) is the right one. Two weak
   spots need fixing: VAD-only endpointing and meeting-room devices (several people on one stream). See section 1.

| Part | R1 choice | Backup / later |
|---|---|---|
| ASR model | Nemotron Speech Streaming EN 0.6B (NeMo, GPU) | Parakeet Unified EN 0.6B (challenger); Nemotron 3.5 Streaming (other languages later) |
| Streaming method | Cache-aware streaming, 0.56 s chunk, 1 stream per speaker, batched on 1 GPU | 0.16 s chunk if we need faster partials (costs about 3 WER points on AMI) |
| Voice detection | Silero VAD (already in stack) | none |
| End of turn | Smart Turn v3.2 (audio, CPU) | LiveKit turn detector (text): licence unclear, skip for now |
| Name and jargon | NeMo GPU-PB phrase boosting per stream + fuzzy text match | openWakeWord / livekit-wakeword (audio, Apache 2.0) if "Max" recall is too low |
| Cloud (switch, comparison only) | Deepgram Flux or Nova-3 | AssemblyAI Universal-3.5 Pro streaming |
| Laptop (i5, no GPU) | Cloud switch, or the same model in NeMo-Speech.cpp on CPU (speed not verified) | none |

## 1. Is this the right approach?
Short answer: **yes, mostly**. Here is the honest comparison.

| Option | Good | Bad | Verdict |
|---|---|---|---|
| **A. Per-speaker streaming ASR on our hardware (our plan)** | Model stays swappable. Audio stays in house. We get a clean text record for memory and search. We can test every part. Separate streams mean we know who spoke without diarization, and cross-talk is not a problem. | We run GPUs. Open streaming models are about 1-3 WER points behind the best batch models. Turn detection is ours to build. | **Keep as default.** |
| **B. Audio straight into a multimodal LLM (e.g. Gemini Live)** | Lowest reply latency, hears tone of voice. Cheap input (about $0.005 per minute, third-party figure, not verified). | Breaks our "model stays swappable" rule: open models on company servers cannot do this well today. You need one live session per speaker stream, kept open all meeting. Sessions are time-limited, and preview models get shut down (two Live previews ended 17 Nov 2026). No reliable text record, weak speaker labels, hard to test. | **Wrong for R1.** Maybe later only for voice replies. |
| **C. Cloud streaming ASR (Deepgram, AssemblyAI)** | Fastest to ship. Turn detection and keyterms are built in. Roughly $0.4-0.5 per one-hour meeting if we send only speech (estimate, not verified). | Audio leaves the company. Depends on a vendor. Goes against the move to company servers. | **Keep behind a switch** as a baseline and fallback. If our own model fails the test, we switch to this and nothing else changes. |

Weak spots in our plan, plainly:
- **Silero VAD alone is weaker than the alternatives.** Silence-only endpointing gives two bad choices. A short wait
  (0.2-0.5 s) cuts people off mid-sentence ("Max, can you check... the budget"). A long wait (1-1.5 s) makes Max feel
  slow. Fix: VAD plus a semantic turn detector (section 3).
- **Meeting rooms.** A Teams Room device sends one stream for the whole room, so several people share one "speaker".
  Fix: label it "Room X". Diarization inside room streams is a later topic. (Not verified with a real tenant.)
- **Only 4 dominant speakers get their own stream.** A 5th person talking quietly over others can be dropped. That is
  fine for live replies. It means the live transcript is not a perfect record.
- **Stream-to-person mapping can change.** Unmixed streams carry a source ID that we map to a participant through the
  roster. If the mapping is wrong, we label the wrong speaker. The gateway must handle remapping (not verified).
- **Where it runs.** The Teams media SDK is Windows-only. NeMo prefers Linux with an NVIDIA GPU. So ASR should be its
  own service (Linux GPU box), and the C# gateway streams PCM to it (gRPC or WebSocket). Plan this from day one.
- **Two endpoints, not one.** Cutting the *transcript* into pieces can be loose. Deciding that *Max should answer now*
  must be careful. Max should also wait while other people are talking, because someone else may answer first.

## 2. Streaming ASR models (self-hosted)
WER = word error rate, lower is better. AMI is real meeting speech, the closest match to us. Averages are on the
Hugging Face Open ASR Leaderboard (8 English sets). Numbers from different snapshots are not strictly comparable.

| Model (date) | Streaming? | Accuracy | Latency | Hardware | Licence |
|---|---|---|---|---|---|
| **Nemotron Speech Streaming EN 0.6B** (Mar 2026) | **True** (cache-aware RNNT), partials | avg 6.93 / AMI 11.73 / Earnings22 12.52 at 1.12 s chunk. **0.56 s: 7.07 / 11.88 / 12.82.** 0.16 s: 7.67 / 14.71 / 13.01 | Chunk 80 ms to 1.12 s | NVIDIA GPU (Volta and newer), Linux; GGUF CPU build exists | NVIDIA Open Model Licence (commercial OK; **custom licence**) |
| **Parakeet Unified EN 0.6B** (Apr 2026) | Streaming + offline in one model | avg 5.91 offline, **6.52 at 0.56 s**, 8.44 at 0.16 s. AMI 10.14 (offline only) | 160 ms to 2.08 s | NVIDIA GPU, Linux | NVIDIA Open Model Licence (**custom**) |
| Nemotron 3.5 ASR Streaming 0.6B (Jun 2026) | True, 40 language-locales | Leaderboard avg 9.75; FLEURS 8.8-10.4 | 80 ms to 1.12 s; about 240 streams on 1 H100 at 80 ms | NVIDIA GPU | OpenMDW-1.1 (permissive) |
| Voxtral Mini 4B Realtime (Feb 2026) | True (vLLM WebSocket) | Leaderboard avg 8.44; FLEURS 5.90 offline to 8.72 at 480 ms | 240 ms to 2.4 s | GPU, 4B params (about 10 GB+ VRAM, not verified) | Apache 2.0 |
| Kyutai STT 2.6B EN / 1B EN-FR (Jun 2025) | True | 2.6B: avg 6.40 (secondary source). 1B: no official WER | Fixed delay: 2.5 s (2.6B), 0.5 s (1B); 1B has built-in semantic VAD | GPU | CC-BY 4.0 weights |
| Qwen3-ASR 1.7B / 0.6B (Jan 2026) | Chunked (1-8 s attention window), vLLM only | avg 6.15 (1.7B), 7.07 (0.6B), Nov 2026 snapshot | Not published | GPU | Apache 2.0 |
| Moonshine v2 streaming (Feb 2026) | True, built for edge | avg 6.65 (Medium) / 7.84 (Small) / 12.0 (Tiny) | Under 250 ms to first text | **CPU**, 34-245M params | MIT (English); some other-language weights non-commercial |
| Whisper large-v3 / turbo + SimulStreaming or WhisperLiveKit | **Chunked** (AlignAtt or LocalAgreement re-decoding) | avg 8.24 / 8.75 (Nov 2026 snapshot). Whisper is known to hallucinate in silence | About 1-2x the chunk length, usually 1-2 s+ | GPU with 10 GB+ recommended; too slow on CPU for real time | MIT |
| Parakeet TDT 0.6B v2 (May 2025) | Batch only | avg 6.05, AMI 11.16, Earnings22 11.15, word timestamps | Batch | GPU (very fast, RTFx about 6,000) | CC-BY 4.0 |
| IBM Granite Speech 5.0 / Cohere Transcribe / Nemotron 3.5 Transcribe | Batch only | avg 6.68 / 6.72 / 6.13 (leaderboard top) | Batch | Nemotron Transcribe needs an 80 GB GPU | Apache / Apache / OpenMDW |

Notes:
- **Streaming beats chunked Whisper for us.** It sends partials constantly, has no hallucinations in silence, and has
  punctuation built in. Each extra stream is cheap: about 240 streams fit on one H100 at the lowest latency.
- **Chunk size is a trade-off.** On AMI, a 0.56 s chunk gives 11.9 % and 0.16 s gives 14.7 %. For Max, 0.56 s is the
  sweet spot. Partials every half second are enough to spot "Max".
- **Word timestamps** come out of RNNT/TDT decoders through NeMo or Riva. The model cards do not document this clearly
  for the streaming models (not verified). We need timestamps only to line up the transcript, not for replies.
- **A second pass after the meeting** with a top batch model (e.g. Qwen3-ASR 1.7B) could clean up the stored record.
  Only add it if tests show the live transcript is too poor (lean scope).
- **On the laptop**, NeMo-Speech.cpp (GGUF) and Moonshine run on CPU, but 4 live streams on an i5 is not verified.
  Use the cloud switch or the Omen GPU for development.

### Cloud ASR (behind a switch, for comparison)
| Service | Why it is interesting | Price (pay as you go) |
|---|---|---|
| Deepgram Flux | End-of-turn detection inside the model; keyterm prompting; median end of turn under 300 ms (third-party figure) | $0.0065/min (EN) |
| Deepgram Nova-3 | Standard streaming plus keyterms | about $0.0043/min, keyterms +$0.0013/min (page layout unclear, not verified) |
| AssemblyAI Universal-3.5 Pro streaming | Keyterms and a prompt you can change mid-session; silence-based turn settings; P50 about 300 ms | Not checked |
| Azure Speech / Google Chirp 3 | Phrase lists / adaptation | Price not confirmed (Chirp 3 about $0.016/min via a reseller) |

## 3. Segmentation and end of turn
Each speaker stream gets its own small state machine: **silent → speaking → maybe done → done**.

| Step | Setting (start values, tune on our audio) | Why |
|---|---|---|
| Silero VAD threshold | 0.5 (0.6 if noisy) | Per-speaker streams are fairly clean. Pipecat uses 0.7 by default. |
| Speech start | 0.2 s of speech | Ignores coughs and clicks |
| "Maybe done" | 0.2 s of silence → run Smart Turn | Pipecat's recommended setting with Smart Turn |
| Smart Turn says **complete** | Finalise the segment now | Fast reply when the sentence is clearly over |
| Smart Turn says **incomplete** | Keep waiting; re-run on the whole turn if speech resumes; force "done" after 1.5 s of silence | Handles "Max, can you... um... check X" |
| Transcript-only cut | 0.6 s of silence, even if incomplete | Transcript pieces don't need to wait for a full sentence |
| Long monologue | Hard cut at 15 s, at the quietest 200 ms in the last 2 s | Keeps segments small. Streaming ASR keeps its context across the cut. |
| Very short noise | Drop segments under 250 ms with no words | Less junk |

- **Partials vs finals.** Partials go to two places: the "Max" detector, and a live caption if we ever show one. Only
  final text goes to the transcript store and the LLM. Partials may change, so never act on them alone.
- **Overlap.** Separate streams mean overlap needs no special handling. Each stream ends on its own.
- **Max replies only when:** the addressing speaker is "done", AND no other stream is speaking (or one is, but has only
  just started), AND Max is not already speaking. Otherwise Max queues the reply or drops it.
- **Max's own voice.** Teams should not send the bot its own audio in the unmixed streams (not verified, must test).
  A person without a headset can still leak Max's voice into their microphone. Teams clients cancel most echo. As a
  guard, ignore ASR text that matches what Max said in the last few seconds. If someone talks over Max (barge-in),
  Max stops speaking. That is a separate design.
- **Smart Turn limits.** It looks at 8 s of audio at most and is weak on very short clips. It does not read the text.
  Smart Turn v3 claims better accuracy than v2. A third-party test reports about 92 % accuracy (not verified).
- **Text-based alternative.** The LiveKit turn detector (Qwen2.5-0.5B, reads text, English true positive rate 99.3 % /
  true negative rate 87 %) uses a "LiveKit Model Licence" and is built for LiveKit Agents. It is unclear whether we may
  use it outside LiveKit, so **don't use it** unless the licence is checked.

## 4. Recognising "Max" and team words
"Max" is one short syllable and a common word ("max out", "maximum"). Plan for both misses and false alarms.

1. **Boost in the ASR.** NeMo GPU-PB phrase boosting works with cache-aware streaming RNNT, and each stream can carry
   its own list. No retraining needed. The boost list holds "Max", attendee names from the Teams roster, and project
   and jargon terms from the team glossary. Keep it short (about 50-300 phrases; too many boosts add wrong words, not
   verified). Cloud ASR takes the same list as "keyterms" or "phrase lists".
2. **Detect in the text,** on partials and on finals. Allow fuzzy matches (Max, Maxx, Mack, Mac, Macs). Use the
   position as a clue: start of the turn, after "hey" or "okay", or followed by a comma or pause ("..., Max?" also counts).
3. **Confirm addressing.** A rule says "likely". Then a small LLM check on the final text plus the last few lines
   decides whether this is really a request to Max. That drops "we maxed out the budget".
4. **Audio wake word, only if needed.** openWakeWord (Apache 2.0, aims for under 0.5 false accepts per hour) or
   livekit-wakeword (Apache 2.0, claims fewer false positives). Add one only if text recall of "Max" stays below about
   97 %. Avoid Porcupine: proprietary, and its free tier closed in June 2026.
5. **Always offer a non-voice path:** @Max in the meeting chat.

## 5. R1 setup (recommended)
| Item | Value |
|---|---|
| Service | Separate ASR service (Python, NeMo, Linux GPU). Gateway sends 20 ms PCM frames tagged with the speaker. |
| Interface | One `transcribe_stream(speaker_id)` interface that yields partials and finals. Engines: `nemotron_en`, `parakeet_unified`, `deepgram`, `assemblyai`, all behind one setting (like the LLM). |
| Model | Nemotron Speech Streaming EN 0.6B, 0.56 s chunk, punctuation on, greedy decoding with GPU-PB boosting |
| Streams | 1 per active speaker (up to 4) plus room streams; streams batched on one GPU |
| Endpointing | Silero VAD + Smart Turn v3.2 with the settings in section 3 |
| Name | Boost list + fuzzy text match + addressing check |

**Expected latency (estimate, not verified):** the person stops talking → 0.2 s VAD silence → 10-65 ms Smart Turn → ASR
flushes its last chunk (most of it is already decoded during the silence) → **final text 0.4-0.8 s after speech ends**.
Chunked Whisper would be about 1-2 s. Max's spoken reply then adds LLM time (first words) and TTS time on top.

GPU needs: a 0.6B model plus Smart Turn for a handful of streams fits easily in a gaming GPU (the Omen). Exact VRAM is
not published (not verified). Production: one data-centre GPU serves many meetings.

## 6. What to benchmark ourselves
Small, repeatable test that runs against any engine (same rule as the LLM quality tests).

**Audio set (about 3 hours):**
- **AMI "IHM" (headset) recordings**: one mic per person, which matches our per-speaker streams. Licence CC-BY 4.0.
- 1-2 hours of our own Teams test meetings recorded through the gateway, with consent, 4-6 people, mixed accents,
  one meeting-room device.
- 100 scripted "Max, ..." requests (different speakers, fillers, pauses mid-sentence), plus 50 near-misses
  ("max out", "maximum", "Matt", names close to Max).

**Measure:**
| Metric | Target to aim for (our proposal) |
|---|---|
| WER per speaker stream (AMI IHM + ours) | Within 2 points of the best cloud engine |
| Recall of names and glossary terms | ≥ 90 % |
| "Max" recall / false triggers per hour | ≥ 97 % / ≤ 1 per hour (after the addressing check) |
| End of speech → final text, p50 / p95 | ≤ 0.6 s / ≤ 1.0 s |
| Cut mid-sentence (early endpoint) | ≤ 5 % of turns |
| Max answers while someone still talks | ~0 in the test set |
| GPU memory and number of live streams per GPU | Record it, used for server sizing |

## 7. Licence flags
| Item | Licence | Flag |
|---|---|---|
| Nemotron Speech Streaming EN, Parakeet Unified | NVIDIA Open Model Licence | **Custom licence.** Commercial use allowed, but legal should read it before release. |
| Nemotron 3.5 Streaming / Transcribe | OpenMDW-1.1 | Permissive, newer licence; quick legal read |
| Parakeet TDT v2/v3, Kyutai weights, AMI data | CC-BY 4.0 | OK, attribution needed |
| Moonshine | MIT (English) | Some non-English weights are non-commercial |
| LiveKit turn detector | LiveKit Model Licence | **Unclear outside LiveKit.** Avoid for now |
| Porcupine | Proprietary | Avoid |
| Whisper, SimulStreaming | MIT | SimulStreaming says its licence terms may change; WhisperLiveKit mentions dual-licence terms |
| Smart Turn (BSD-2), Silero VAD (MIT), Qwen3-ASR / Voxtral / openWakeWord (Apache 2.0) | Permissive | OK |
| No AGPL or CC-BY-NC in the R1 picks | | |

## Sources (accessed 26 Nov 2026)
- Nemotron Speech Streaming EN 0.6B card (Mar 2026): https://huggingface.co/nvidia/nemotron-speech-streaming-en-0.6b
- Nemotron 3.5 ASR Streaming 0.6B card (Jun 2026): https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b
- Parakeet Unified EN 0.6B card (Apr 2026): https://huggingface.co/nvidia/parakeet-unified-en-0.6b
- Parakeet TDT 0.6B v2 card: https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2
- NVIDIA blog, cache-aware streaming for voice agents: https://huggingface.co/blog/nvidia/nemotron-speech-asr-scaling-voice-agents
- NeMo word boosting (GPU-PB): https://docs.nvidia.com/nemo/speech/latest/asr/asr_customization/word_boosting.html ;
  TurboBias paper: https://arxiv.org/abs/2508.07014
- Leaderboard snapshot 9 Nov 2026 (ThinkScribe): https://thinkscribe.ai/en/blog/open-speech-recognition-models-2026
- Self-hosted ASR overview, 9 Oct 2026 (Pinggy): https://pinggy.io/blog/best_open_source_self_hosted_speech_to_text_models/
- MarkTechPost comparison (Jul 2026): https://www.marktechpost.com/2026/07/23/best-open-speech-recognition-asr-models-in-2026-wer-languages-latency-and-license-compared/
- Open ASR Leaderboard paper: https://arxiv.org/abs/2510.06961
- Voxtral Realtime paper (Feb 2026): https://arxiv.org/abs/2602.11298 ; Mistral post: https://mistral.ai/news/voxtral-transcribe-2
- Kyutai STT: https://kyutai.org/stt ; https://huggingface.co/kyutai/stt-1b-en_fr
- Qwen3-ASR: https://github.com/QwenLM/Qwen3-ASR ; report https://arxiv.org/abs/2601.21337
- Moonshine v2 (Feb 2026): https://arxiv.org/abs/2602.12241 ; accuracy: https://moonshine-voice.readthedocs.io/en/latest/models/accuracy/
- SimulStreaming: https://github.com/ufal/SimulStreaming ; WhisperLiveKit: https://github.com/QuentinFuxa/WhisperLiveKit
- Smart Turn: https://github.com/pipecat-ai/smart-turn ; v3 post: https://www.daily.co/blog/announcing-smart-turn-v3-with-cpu-inference-in-just-12ms/
- Pipecat speech input / VAD defaults: https://docs.pipecat.ai/learn/speech-input
- LiveKit turn detector: https://huggingface.co/livekit/turn-detector ; https://docs.livekit.io/agents/logic/turns/turn-detector.md
- Silero VAD settings (NVIDIA Curator): https://docs.nvidia.com/nemo/curator/latest/curate-audio/process-data/quality-filtering/vad
- Deepgram Flux: https://deepgram.com/learn/introducing-flux-conversational-speech-recognition ; pricing: https://deepgram.com/pricing
- AssemblyAI voice agent best practices: https://www.assemblyai.com/docs/voice-agents/best-practices
- Gemini Live pricing (third party, Oct 2026): https://www.cekura.ai/blogs/gemini-live-api-pricing
- openWakeWord: https://github.com/dscripka/openWakeWord ; livekit-wakeword: https://github.com/livekit/livekit-wakeword
