# Max Meeting: overview (separate module)

**Status: ⏸️ PAUSED (Karthi, 26 Nov 2026): finish the chat Max first, then continue here (Part 1 proposed,
Parts 2-7 open).**
**Karthi (26 Nov 2026): Max Meeting is its own module and its own section of the plans**, because it has many parts
and can grow into many more use cases later. It uses the same Max brain (knowledge, memory, tools, personality,
cards) through a clear interface; meeting-specific work lives here. Files in this folder are numbered in reading order.

Research: `docs/research/meetings-live.md` (Microsoft options), `meetings-asr.md` (speech-to-text, boundaries,
hearing "Max"), `meetings-live-agent.md` (addressee detection, live understanding, speaking, real systems).
Pictures (in `docs/plans/pictures/`): `meetings-1-how-max-joins.png`, `meetings-2-audio.excalidraw`
(quick view `meetings-2-audio-preview.png`).
Already agreed in the main plans: brief + live countdown, "taking notes" notice + pause, notes with review, owners
confirm (`../09-cards.md` Part 3).

## Direction (Karthi, 26 Nov 2026)
- Max is in the meeting **like a real person** and responds whenever it's called (like chat).
- **Our own pipeline**, not dependent on extra Microsoft services: audio → processing → **streaming speech-to-text**
  with dynamic boundaries → transcript → Max understands continuously. Never "raw audio straight to an LLM".
- **Process naturally; don't over-engineer edge cases.** Meeting-room devices, open mics, people talking over each
  other in one room: best effort only (Microsoft's own tools struggle there too). No special handling in R1.
- Research verdict: the pipeline is right (all group-meeting products use it); speech-to-speech "audio AI" models are
  not suited to group meetings (one person, no transcript, one provider, ~10x cost).

## Parts
| # | Part | Status |
|---|---|---|
| 1 | How Max joins and hears the call | 🔄 Proposed |
| 2 | Speech → text: which live transcription model, boundaries, hearing "Max" | ⬜ |
| 3 | Understanding live: "was Max called?", meeting state, "what did I miss?" | ⬜ |
| 4 | Speaking: chat vs voice, never over people, confirm before acting | ⬜ |
| 5 | After the meeting: notes from our own transcript | ⬜ |
| 6 | Testing | ⬜ |
| 7 | Module boundary: what Max Meeting owns vs the shared Max brain; code layout | ⬜ |

## Part 1: how Max joins and hears (PROPOSED 26 Nov 2026)
- **Max joins the call as a participant** ("Max (bot)" tile). Added by the organizer, in channel meetings of its
  team, or in meetings it booked (agreed: people add Max; it doesn't add itself).
- **Media gateway:** a small C# program (Microsoft's real-time media kit exists only for .NET on Windows). Its only
  job: join the call, pass audio in and out. Everything after the audio is Python and ours.
- **Each speaker arrives as a separate audio stream** (Teams gives a bot the up-to-4 loudest speakers unmixed, each
  labelled), so who-said-what comes for free.
- Until a real tenant exists, the **simulated Teams plays each person's voice as its own stream**; the C# gateway is
  added later.
- The meeting chat is still used: full answers, sources, cards, and "@Max" typed there as a backup.

## Part 2 preview: live transcription model candidates (checked 26 Nov 2026)
Behind one swappable `transcribe_stream(speaker)` function (partial + final text), chosen by our own test:
| Candidate | Type | Notes |
|---|---|---|
| **Gemini 3.5 Transcribe Live** (`gemini-3.5-transcribe-live`) | Cloud, Google (our current provider) | Public preview since Aug 2026; streaming with partial + final text, built-in voice detection; Google reports ~4.0% average WER streaming; ~$0.009/min (secondary source); sessions cap at 10 min (auto-reconnect needed). No GPU needed: runs from any laptop |
| NVIDIA streaming models (Nemotron / Parakeet) | Own hardware, free | 11.9% WER on real meeting audio (AMI); needs a GPU (Omen / server); custom NVIDIA licence (legal check) |
| Deepgram / AssemblyAI | Cloud | Strong streaming options; fallback / comparison |
Cost idea: only send audio while someone is actually speaking (voice detection first), so a 1-hour, 4-person meeting
is billed for speaking time only, not 4 x 60 minutes.

**Superseded (history):** first plan = text mode via meeting chat + Microsoft "Work IQ" live transcript + the
after-meeting transcript API. Dropped by Karthi on 26 Nov (too dependent on Microsoft services).
