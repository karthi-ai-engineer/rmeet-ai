# Prototype review: what to keep, drop and fix (max-demo → max-final)

Reviewed: `../max-demo` (read only), 26 Nov 2026. Line numbers point to that folder.

**In one line:** the *ideas and contracts* are strong. The *packaging* is fragile. One 950-line `app.py`, two
LLM stacks, a live LLM writing every colleague line, and a UI that doesn't look like Teams. That last one is
probably why the demo got little reaction.

---

## 1. KEEP

| What | Where | Why |
|---|---|---|
| Max talks only through real Microsoft contracts; endpoints are config | `max/config.py`, `HANDOVER.md` §6 | Moving to real Teams = config change, not a rewrite. Most valuable idea. |
| Fake cloud with real details: RS256 JWTs + JWKS, Bot Connector, Graph paging, subscription validation + lifecycle + expiry, `$top≤50`, `410` delta reset | `simulations/teams/identity.py`, `connector.py`, `graph.py`, `subscriptions.py` | Catches real integration bugs early |
| Calling flow: meetingStart → `GET /v1/meetings` → `POST /communications/calls` → callbacks → `updateRecordingStatus` before keeping notes | `max/calling.py:86-163`, `simulations/teams/calls.py` | Correct Microsoft order, including the compliance rule |
| Media frame protocol (20 ms PCM16k, per-speaker MSI) as a seam for a later .NET media worker | `simulations/teams/calls.py:13-21` | Good boundary. Write it down as a spec. |
| Approval design: card shows full content, one click wins, payload frozen by hash, 24 h expiry, outside content gets no sending tools | `max/approvals.py`, `max/agent/tools.py` | Safe "AI does actions" story for stakeholders |
| Dedup of double delivery (bot + Graph) via `inbound_events` | `max/store.py`, `app.py:290,302` | Real Teams sends the same message twice |
| Scripted fake model + movable clock | `max/agent/testing.py`, `max/agent/clock.py` | $0, repeatable tests, incl. reminders |
| World data, answer key, exact fact matcher | `simulations/planning-department/` (`WORLD.md`, `scenario.yaml`, `expected.yaml`, `tools/check_world.py`), `rmeet/scoring.py:16` | Rich, consistent demo content; scoring without a model |
| One-command start; research notes | `run.py`; `docs/research/teams/01-03` | Right idea; contract reference |

## 2. DROP or REDO

| Problem | Example | Do instead |
|---|---|---|
| God file mixing install, Graph webhooks, messages, deadline rule, approvals, calling, admin page, test hooks | `max/app.py` (951 lines) | Split by feature: `channel/`, `meetings/`, `actions/`, `admin/`. Register routers in one small `main.py`. |
| Module globals as state | `app.py:129` `AGENT` dict, `:130` `_thread_locks` (never cleaned), `:197` `MEETING_RUNS`, `:681` `calls`, plus `knowledge`, `refs` | One `AppState` object passed in; locks with cleanup |
| Two LLM stacks + misleading names | `max/llm.py` (urllib, sync) and `max/agent/models.py` (LangChain). `qwen_chat()` actually calls Gemini when `BRAIN_PROVIDER=gemini` (`llm.py:58`) | One async model client with timeout, retry and fallback |
| Two "brains" | Threads use the agent; meetings and fallback use `brain.py`, which sends the whole memory every call (`app.py:653`) | One path. Meeting answers use the same retrieval tools. |
| Imports work only through `sys.path` hacks | `max/llm.py:22`, `rmeet/server.py:28-29`, every test file | A real package (`pyproject.toml`) and pytest |
| Hidden per-machine coupling | `llm.py:23` imports `gemini_usage` from outside the repo; `local_tts/` not in git; master keys in `voice-chat/.env`, copied into `max/.env` by `register_app.py` | One `.env` at the root; optional parts declared in config |
| Runtime data inside source folders | `simulations/teams/state/channel_state.json`; director writes `planning-department/runs/` (`director.py:491`) | Everything runtime goes in `data/` |
| Simulator is hand-made threads | `ThreadingHTTPServer`, hand-rolled WebSocket (`teams/ws.py`), SSE, `ThreadPoolExecutor` (`director.py:92`), `threading.Thread(...sleep(3))` (`director.py:484-489`) | Use the same async framework as Max (FastAPI + real websockets) |
| Leftovers and drift | `max/agent/spike.py` (dead code); `graph.py:4` says "max 6 passes" but `MAX_STEPS = 8`; `BRAIN_PROVIDER` vs `MAX_BRAIN_PROVIDER` (`run.py:91-92`) | Delete, or test it |
| Times stored as "wall-clock-as-UTC" | `HANDOVER.md` §5 | Real UTC in storage; convert only in the UI |
| 1,518-line UI script, generic indigo/Inter look, dev controls on screen (beat goals, speed 1×/2×/4×, scores) | `rmeet/static/app.js`, `app.css:69` | A Teams look-alike (Segoe, Teams purple, Teams layout). Dev panel hidden behind a switch. |

## 3. Demo-reliability risks

| Risk | Where | What happens live |
|---|---|---|
| Every colleague line is written live by Qwen; on failure the line is **skipped** | `director.py:308-343, 404` | Gaps and odd flow; a model hang means silence |
| Timeouts don't match: a meeting answer can take 30 s × 3 tries + backoff (~95 s), the director waits 75/90 s | `brain.py` (`timeout=30`), `director.py:284` | "Max didn't answer in time", then Max answers late, out of order |
| Notes: 60 s × 3 tries vs the director's 180 s wait | `brain.py` (`timeout=60`), `director.py:456` | Notes arrive after the UI says "no notes" |
| Notes failure is only logged | `calling.py:401-402` | Meeting ends with no notes and no message |
| Agent has no overall deadline: 8 rounds × 60 s | `agent/graph.py:30`, `agent/models.py:108` | An @mention can hang for minutes |
| Questions asked while Max is busy are **dropped** (flag, not queue) | `calling.py:262-264` | Back-to-back questions: the second gets no answer |
| Voice: speech-to-text worker only starts if the first media connect works | `calling.py:176-178` | After one reconnect, Max is deaf in voice mode |
| `wait_for(send_active, 10)` timeout not caught | `calling.py:332` | Spoken answer lost, with no chat fallback |
| Busy-wait for the call id; dedup of own meetings by title | `app.py:788`, `app.py:742` | Race on slow machines; two meetings with the same title get confused |
| Gemini free-tier 429 on TTS/STT | `voice.py` quota guard | Voices fall back to browser/text mid-demo |
| e2e tests reset the channel and reinstall Max | `tests/e2e_lib.py:96` | Running a test before a demo wipes the demo state |
| Fixed ports 8100/3978/8400/8600; `run.py` stops if busy | `run.py:209-211` | Can't start if a stale process holds a port |
| Windows encoding: Max needs `PYTHONIOENCODING=utf-8` (¥, emoji); first call after idle slow (Gemini TTS 20-60 s) | `HANDOVER.md` §4-5 | Encoding errors on manual start; the first answer is the slowest |

## 4. Test quality

| Area | Coverage | Notes |
|---|---|---|
| Agent graph, approvals, policies, store, follow-ups, uploads rules, meeting actions/recap/brief | Good, offline, $0 | `tests/test_*.py` with `ScriptedChatModel` |
| Contracts (Connector, Graph, subscriptions, calls) | Only through e2e | No fast contract tests for the fake cloud alone |
| `calling.py` (media, segmenting, barge-in, reconnect) | Weak | The bugs in §3 are untested |
| UI | None | No browser test of the demo path |

Problems:
- Tests are **scripts with their own `check()`**, not pytest. There is no single "run all" command and no CI.
- e2e tests share live servers, reset shared state, use `sleep`/polling (`e2e_lib.py:49`), and must run one at a time.
- **Need live models** (slow, flaky, cost money): `eval_phase4_agent.py`, `e2e_phase3_*` (scoring uses a Qwen judge, `scoring.py:71`), `e2e_phase5_*`, `e2e_conversation_fixes.py`, `check_voice_pipeline.py`, `spike_gemini_tools.py`. Pass/fail depends on wording and quota.
- No model needed: `e2e_phase4_followups.py` and all offline `test_*.py`.

## 5. Gaps vs real Microsoft (will hurt later)

| Gap | Real Teams |
|---|---|
| Media is a WebSocket stand-in | Needs the Real-time Media SDK: Windows + .NET, public IP, certificate. Biggest piece of work. |
| Real-time transcript ("Work IQ" text mode) is invented (`sim-v0`) | No equal public API today. Text mode may not exist for real. |
| Official transcript appears 3 s after the meeting (`director.py:485`) | Minutes later; needs an application access policy for `getAllTranscripts` |
| Everything is `http://localhost` | Public HTTPS for messages, notifications and calling callbacks |
| No throttling (429 / `Retry-After`) | Graph throttles; Max has no backoff for it |
| Connector waits 25 s and never redelivers | Teams times out around 15 s and retries |
| Max's own mailbox and calendar, Exchange RBAC, Sites.Selected are admin switches in the UI | Real tenant setup by IT; weeks of lead time |
| Cards are rendered by the custom UI | The real Teams client renders Adaptive Cards differently (versions, Action.Execute refresh) |

## 6. Top 10 lessons for the rebuild (ranked)

1. **Make it look like Teams.** Stakeholders react to what feels familiar. Copy the Teams layout and colours, and hide the dev controls.
2. **A scripted demo mode.** Pre-generate the colleague lines and audio, then replay them. Live LLM only for Max. Same result every time.
3. **One time budget for every model call** (e.g. 8 s answer, 30 s notes), with a polite fallback message. Never a silent failure.
4. **Max never drops a question.** Use a per-meeting queue; always post *something* (answer, "still thinking", or an apology).
5. **Small modules, no globals.** One feature per file, one state object, a real package.
6. **One model client, one brain path.** Async, retries, provider switch, usage meter built in.
7. **pytest from day one**: offline unit and contract tests with a fake model in CI; live-model evals kept separate and labelled.
8. **Isolated demo state.** Tests use their own data folder and ports; a "reset demo" button restores a known snapshot.
9. **Keep the contract boundary strict and write it down.** Max imports nothing from the simulator; the media protocol and fake-cloud behaviour are pinned by tests.
10. **Health check before the demo**: one command that checks ports, keys, model latency, quota and warmup, and prints red or green.
