"""
Meeting director: runs the live simulated Teams meeting.

The meeting is a Teams *channel meeting* in the fake tenant:
  1. A "Meeting started" post appears in the channel (its thread is the meeting chat).
  2. If Max is installed, Teams sends it application/vnd.microsoft.meetingStart (Bot Connector).
     Max joins through Graph POST /communications/calls and connects the media stand-in.
  3. Every line reaches Max through the call only:
       voice mode - the speaker's voice (Gemini TTS) as 20 ms PCM frames tagged with their MSI
       text mode  - a Work IQ-style real-time transcript line
  4. Max answers by voice (audio frames back up the call) or, in text mode, in the meeting chat.
  5. At the end the call is terminated (200/5001), meetingEnd is sent, Max posts the notes in the
     meeting thread, and the official transcript appears in Graph.
In autopilot the notes are scored against the answer key.
"""

import base64
import json
import queue
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from audio import pcm_to_wav, wav_to_pcm16k
from llm import LLMError, gemini_transcribe, parse_json, qwen_chat, qwen_warmup
from scoring import score
import voices
from voices import EMOTION_STYLE, TTSError, synthesize
from world import World

EMOTIONS = {"idle", "happy", "surprised", "thinking", "confused", "wink"}
MSI = {"karthi": 1, "prince": 2, "daniel": 3, "jacob": 4}
ADDRESS_RE = re.compile(r"\bmax\b", re.IGNORECASE)
LIVE_KEY = "live-budget-review"


class EventBus:
    def __init__(self):
        self._lock = threading.Lock()
        self._subs: list[queue.Queue] = []
        self.history: list[dict] = []

    def publish(self, event: dict, keep: bool = True) -> None:
        with self._lock:
            if keep:
                self.history.append(event)
            for q in self._subs:
                q.put(event)

    def subscribe(self):
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._subs.append(q)
            return q, list(self.history)

    def unsubscribe(self, q) -> None:
        with self._lock:
            if q in self._subs:
                self._subs.remove(q)

    def clear(self) -> None:
        with self._lock:
            self.history = []


def speaking_seconds(text: str) -> float:
    return max(1.6, min(14.0, len(text.split()) / 2.6 + 0.6))


class Meeting:
    def __init__(self, world: World, bus: EventBus, identity, store, meetings, calls, connector):
        self.world, self.bus, self.identity, self.store = world, bus, identity, store
        self.meetings, self.calls, self.connector = meetings, calls, connector
        self.status = "lobby"          # lobby | live | summarizing | ended
        self.mode = "live"             # live (you host) | autopilot
        self.media = "voice"           # voice | text
        self.speed = 1.0
        self._thread = None
        self._stop = threading.Event()
        self._host_q: queue.Queue = queue.Queue()
        self._waiting_for_host = False
        self._lock = threading.Lock()
        self.clips: dict[str, bytes] = {}
        self.pool = ThreadPoolExecutor(max_workers=3)
        store.on_change(self._on_store_event)

    # ------------------------------------------------------------------ API
    def start(self, mode: str, speed: float, media: str = "voice") -> None:
        with self._lock:
            if self.status in ("live", "summarizing"):
                raise RuntimeError("A meeting is already running.")
            self.mode = "autopilot" if mode == "autopilot" else "live"
            self.media = "text" if media == "text" else "voice"
            self.speed = 1.0 if self.media == "voice" else max(0.5, min(8.0, float(speed or 1)))
            self._stop.clear()
            self._host_q = queue.Queue()
            self.transcript: list[dict] = []
            self.max_answers: dict = {}
            self.beat_id = None
            self.t0 = time.time()
            self.identity.reload()
            self.bot_joined = threading.Event()
            self.max_spoke = threading.Event()
            self.recording = "notRecording"
            self.ever_recorded = False
            self.root_id = None
            self.notes_text = None
            self.notes_event = threading.Event()
            self._bot_buf = bytearray()
            self._bot_last = 0.0
            self._bot_chunk = bytearray()
            self._bot_lock = threading.Lock()
            self.clips = {}
            self.bus.clear()
            self.status = "live"
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def say(self, text: str, audio_wav: bytes | None = None) -> None:
        text = (text or "").strip()
        if not text:
            raise ValueError("Nothing to say.")
        if self.status != "live":
            raise RuntimeError("The meeting is not live.")
        self._host_q.put((text, audio_wav))

    def stop(self) -> None:
        self._stop.set()
        self._host_q.put(None)

    def snapshot(self) -> dict:
        return {"status": self.status, "mode": self.mode, "media": self.media, "speed": self.speed,
                "waiting_for_host": self._waiting_for_host}

    # ------------------------------------------------- call listener (CallsService)
    def on_bot_joined(self, call) -> None:
        self.bot_joined.set()
        self._emit("chat", speaker="system", text="Max joined the call (Graph communications/calls, media connected)")
        self._emit("call", state="established")

    def on_recording(self, status: str) -> None:
        self.recording = status
        if status == "recording":
            self.ever_recorded = True
        self._emit("recording", status=status)

    def on_bot_left(self) -> None:
        self._emit("chat", speaker="system", text="Max left the call")

    def on_media_lost(self) -> None:
        self._emit("error", message="Max's media connection dropped.")

    def on_bot_audio(self, frame: bytes) -> None:
        """Max is speaking: frames arrive 50/s. Stream to browsers, keep for the transcript."""
        with self._bot_lock:
            if not self._bot_buf:
                self._emit("max_speaking", on=True, keep=False)
            self._bot_buf += frame
            self._bot_chunk += frame
            self._bot_last = time.time()
            if len(self._bot_chunk) >= 640 * 10:                      # 200 ms chunks to the browser
                self._emit("max_audio", pcm=base64.b64encode(bytes(self._bot_chunk)).decode(), keep=False)
                self._bot_chunk = bytearray()

    def _bot_audio_watch(self) -> None:
        """End of Max's utterance = 700 ms without frames -> caption it (Teams-side ASR)."""
        while self.status in ("live", "summarizing"):
            time.sleep(0.15)
            with self._bot_lock:
                if not self._bot_buf or time.time() - self._bot_last < 0.7:
                    continue
                pcm, self._bot_buf = bytes(self._bot_buf), bytearray()
                if self._bot_chunk:
                    self._emit("max_audio", pcm=base64.b64encode(bytes(self._bot_chunk)).decode(), keep=False)
                    self._bot_chunk = bytearray()
            self._emit("max_speaking", on=False, keep=False)
            try:
                text = gemini_transcribe(base64.b64encode(pcm_to_wav(pcm)).decode()) or "(inaudible)"
            except LLMError:
                text = "(Max spoke; caption unavailable)"
            self._record_max(text, played=True)

    def _on_store_event(self, ev: dict) -> None:
        """Max's posts in the meeting chat (text mode answers, and the notes)."""
        if ev.get("type") != "message" or self.status not in ("live", "summarizing"):
            return
        m = ev["message"]
        if not m.get("isBot") or not self.root_id or m.get("rootId") != self.root_id:
            return
        if "meeting notes" in m["text"].lower()[:80]:
            self.notes_text = m["text"]
            self.notes_event.set()
            return
        self._emit("chat", speaker="max", text=m["text"])
        if self.status == "live":
            self._record_max(m["text"], played=False)

    def _record_max(self, text: str, played: bool) -> None:
        entry = {"id": len(self.transcript) + 1, "speaker": "max", "text": text,
                 "t": round(time.time() - self.t0, 1), "beat": self.beat_id}
        self.transcript.append(entry)
        if self.beat_id and self.beat_id not in self.max_answers:
            self.max_answers[self.beat_id] = text
        dur = 0.4 if played else speaking_seconds(text) / self.speed
        self._emit("utterance", id=entry["id"], speaker="max", text=text, duration=round(dur, 2), emotion=None,
                   played=played)
        # Don't block the caller (it may be Max's own HTTP request): release the floor after the reading time.
        threading.Timer(0 if played else dur, self.max_spoke.set).start()

    # ------------------------------------------------------------- helpers
    def _emit(self, type_: str, keep: bool = True, **data) -> None:
        self.bus.publish({"type": type_, "t": round(time.time() - getattr(self, "t0", time.time()), 1), **data}, keep)

    def _sleep(self, seconds: float) -> None:
        self._stop.wait(seconds)

    def _person(self, key: str) -> dict:
        u = self.store.users[key]
        return {"key": key, "name": u["name"], "aadObjectId": u["aadObjectId"], "msi": MSI[key],
                "participantId": str(uuid.uuid5(uuid.NAMESPACE_URL, "participant/" + key))}

    def _voice(self, text: str, speaker: str, emotion: str | None) -> bytes | None:
        """Speaker's voice as WAV (Gemini TTS), or None if TTS is unavailable."""
        voice = self.world.members[speaker].get("voice") or "Puck"
        try:
            return synthesize(text, voice, EMOTION_STYLE.get(emotion or "idle"))
        except TTSError as e:
            if "quota" in str(e).lower():
                if time.time() >= getattr(self, "_quota_warned_until", 0):       # tell people once per pause
                    self._quota_warned_until = time.time() + max(30.0, voices.cooldown_left())
                    self._emit("error", message=f"{e}. Using the backup voice meanwhile.", keep=False)
            else:
                self._emit("error", message=f"Voice unavailable for {self.world.first_name(speaker)}: {e}", keep=False)
            return None

    def _utter(self, speaker: str, text: str, emotion: str | None = None, wav: bytes | None = None,
               voiced: bool = True) -> None:
        """A person speaks. Max hears it only through the call (audio frames or live transcript)."""
        if self._stop.is_set() or not text:
            return
        entry = {"id": len(self.transcript) + 1, "speaker": speaker, "text": text,
                 "t": round(time.time() - self.t0, 1), "beat": self.beat_id}
        self.transcript.append(entry)
        person = self._person(speaker)
        clip, pcm = None, None
        if self.media == "voice":
            if wav is None and voiced:
                wav = self._voice(text, speaker, emotion)
            if wav:
                pcm = wav_to_pcm16k(wav)
                clip = uuid.uuid4().hex
                self.clips[clip] = wav
        duration = len(pcm) / 32000 if pcm else speaking_seconds(text) / self.speed
        self.max_spoke.clear()
        self._emit("utterance", id=entry["id"], speaker=speaker, text=text, duration=round(duration, 2),
                   emotion=emotion if emotion in EMOTIONS else None,
                   audio=f"/api/audio/{clip}.wav" if clip else None, browserVoice=self.media == "voice" and not clip)
        joined = self.bot_joined.is_set()
        if pcm and joined:
            self.calls.play(person["msi"], pcm, wait=True)            # real-time paced frames to Max
        else:
            if joined:
                self.calls.transcript(person["msi"], person["name"], person["aadObjectId"], text,
                                      int((time.time() - self.t0) * 1000))
            self._sleep(duration)
        self._sleep(0.35 / self.speed)
        if joined and ADDRESS_RE.search(text):
            self._wait_for_max()

    def _wait_for_max(self) -> None:
        """People pause when they ask Max something."""
        self._emit("status", who="max", state="thinking")
        limit = 90 if self.media == "voice" else 75
        t = time.time()
        while time.time() - t < limit and not self._stop.is_set():
            if self.max_spoke.wait(0.5):
                return
        self._emit("error", message="Max didn't answer in time.", keep=False)

    def _drain_interjections(self) -> None:
        while not self._stop.is_set():
            try:
                item = self._host_q.get_nowait()
            except queue.Empty:
                return
            if item:
                self._utter("karthi", item[0], wav=item[1], voiced=False)

    def _transcript_text(self, last_n: int = 30) -> str:
        return "\n".join(f"{self.world.name(u['speaker']) if u['speaker'] != 'max' else 'Max (AI)'}: {u['text']}"
                         for u in self.transcript[-last_n:]) or "(the meeting is just starting)"

    def _agent_line(self, agent_id: str, beat: dict, multi: bool, context: str | None = None) -> tuple[str, str | None]:
        m = self.world.members[agent_id]
        meeting = self.world.scenario["meeting"]
        system = (
            f"You are {m['name']}, {m['role']} at {self.world.team['company']['name']}, in the Planning "
            f"Department's live Teams meeting \"{meeting['title']}\" on Friday 20 Nov 2026.\n"
            f"Attendees: Karthi M (Planning Manager, host), Prince Raj, Daniel Ito, Jacob Thomas, and Max (AI teammate).\n"
            f"Personality: {m['personality']}\nSpeaking style: {m['speaking_style']}\n\n"
            "Rules:\n"
            "- Talk like a real person in a meeting: 1-3 short sentences, natural spoken English. A light filler\n"
            "  ('so', 'honestly', 'uh') is fine now and then, as people really talk.\n"
            "- No stage directions, no emojis, no markdown, do not start with your own name.\n"
            "- Only use facts from the fact sheet below and what was said in the meeting.\n"
            "- Karthi makes the decisions. If Karthi already decided something different, accept it.\n"
            "- Do not talk to Max unless your goal says so.\n"
            'Return ONLY JSON: {"text": "what you say", "emotion": "idle|happy|surprised|thinking|confused|wink"}\n\n'
            "FACT SHEET (what you know):\n" + self.world.agent_facts()
        )
        extra = []
        if multi:
            extra.append(f"Only say YOUR part ({m['name'].split()[0]}'s part) of this goal.")
        if beat.get("must_mention"):
            extra.append("Make sure you mention: " + ", ".join(beat["must_mention"]) + ".")
        if beat.get("max_question"):
            extra.append(f'Address Max directly by name and ask this (you may rephrase): "{beat["max_question"]}"')
        user = (f"MEETING SO FAR:\n{context or self._transcript_text()}\n\n"
                f"Your goal for this turn: {beat['goal']}\n" + "\n".join(extra) + "\nWrite your next line now.")
        raw = qwen_chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
                        max_tokens=220, temperature=0.75)
        data = parse_json(raw)
        text = (data.get("text") or "").strip() if data else ""
        if not text:
            text = re.sub(rf"^\s*{re.escape(m['name'].split()[0])}\w*\s*:\s*", "", raw).strip().strip('"')
        return text, (data.get("emotion") or "").lower() if data else None

    def _prepare(self, sp: str, beat: dict, multi: bool, context: str | None = None):
        """Line + voice for an agent (runs ahead while the previous person is still talking)."""
        text, emotion = self._agent_line(sp, beat, multi, context)
        wav = self._voice(text, sp, emotion) if self.media == "voice" else None
        return text, emotion, wav

    # ----------------------------------------------------------------- run
    def _run(self) -> None:
        meeting = self.world.scenario["meeting"]
        beats = self.world.scenario["beats"]
        self._emit("state", status="live", mode=self.mode, media=self.media, speed=self.speed, title=meeting["title"])
        self._emit("chat", speaker="system", text=f"Meeting started · {meeting['title']}")
        threading.Thread(target=self._bot_audio_watch, daemon=True).start()
        qwen_warmup()
        live = self.meetings.meetings[LIVE_KEY]
        try:
            self.root_id = self.store.add_meeting_post("karthi", live)["id"]
            people = [self._person(k) for k in ("karthi", "prince", "daniel", "jacob")]
            self.calls.open_meeting(LIVE_KEY, people, self.media, self)
            if self.connector.meeting_event("application/vnd.microsoft.meetingStart", live, self.root_id, True):
                self._emit("chat", speaker="system", text="Teams told Max the meeting started (meetingStart event)")
                if not self.bot_joined.wait(30):
                    self._emit("error", message="Max did not join the call within 30 s (check Max's log and the "
                                                "Admin center: calls need admin consent).")
            else:
                self._emit("error", message="Max isn't in this team (or lacks meeting permission), so it won't join. "
                                            "Add Max from the channel first.")
            self._beats(beats)
            self._finish()
        except Exception as e:  # keep the server alive whatever happens
            import traceback
            traceback.print_exc()
            self._emit("error", message=f"Meeting engine error: {e}")
            self.calls.close_meeting()
            self.status = "ended"
            self._emit("state", status="ended")

    def _beats(self, beats: list) -> None:
        pending = None                                # (key, future) prepared ahead of time
        plan = [(i, j, sp) for i, b in enumerate(beats) for j, sp in enumerate(b.get("speakers") or [b["speaker"]])]
        for n, (i, j, sp) in enumerate(plan):
            if self._stop.is_set():
                break
            beat = beats[i]
            multi = len(beat.get("speakers") or [beat["speaker"]]) > 1
            if j == 0:
                self.beat_id = beat["id"]
                self._emit("beat", id=beat["id"], index=i + 1, total=len(beats))
                self._drain_interjections()
            if sp == "karthi":
                pending = None
                self._host_turn(beat)
                continue
            self._emit("status", who=sp, state="preparing")
            try:
                if pending and pending[0] == (i, j):
                    text, emotion, wav = pending[1].result(timeout=120)
                else:
                    text, emotion, wav = self._prepare(sp, beat, multi)
            except (LLMError, Exception) as e:
                self._emit("error", message=f"{self.world.name(sp)} could not speak: {e}")
                pending = None
                continue
            pending = None
            # Prepare the next agent line while this one is being spoken (no dead air),
            # unless this line asks Max something (the next line must hear Max's answer).
            if n + 1 < len(plan) and not ADDRESS_RE.search(text):
                ni, nj, nsp = plan[n + 1]
                nbeat = beats[ni]
                if nsp != "karthi":
                    nmulti = len(nbeat.get("speakers") or [nbeat["speaker"]]) > 1
                    context = (self._transcript_text(29) + f"\n{self.world.name(sp)}: {text}").strip()
                    pending = ((ni, nj), self.pool.submit(self._prepare, nsp, nbeat, nmulti, context))
            self._utter(sp, text, emotion, wav=wav, voiced=wav is not None or self.media == "text")
            self._drain_interjections()

    def _host_turn(self, beat: dict) -> None:
        fallback = (beat.get("host_fallback") or "").strip()
        if self.mode == "autopilot":
            self._utter("karthi", fallback)
            return
        self._waiting_for_host = True
        self._emit("your_turn", beat=beat["id"], goal=beat["goal"], suggestion=fallback)
        item = None
        while not self._stop.is_set():
            try:
                item = self._host_q.get(timeout=0.5)
                break
            except queue.Empty:
                continue
        self._waiting_for_host = False
        self._emit("your_turn_done", beat=beat["id"])
        if item:
            text, wav = item
            # Your own voice (mic) goes to Max as-is; typed text is spoken with your autopilot voice.
            self._utter("karthi", text, wav=wav, voiced=wav is None)

    def _finish(self) -> None:
        self.status = "summarizing"
        self._emit("state", status="summarizing")
        live = self.meetings.meetings[LIVE_KEY]
        joined = self.bot_joined.is_set()
        self.calls.close_meeting("200", "5001", "The conversation has ended.")
        if joined:
            self._emit("call", state="terminated", subcode="5001")
            self._emit("chat", speaker="system", text="Call ended for everyone (200/5001)")
        if self.root_id:
            self.store.end_meeting_post(self.root_id)
        self.connector.meeting_event("application/vnd.microsoft.meetingEnd", live, self.root_id, False)
        notes, result = None, None
        if joined:
            self._emit("status", who="max", state="thinking")
            if self.notes_event.wait(180):
                notes = self.notes_text
                self._emit("summary", notes=notes, posted=True)
                self._emit("chat", speaker="max", text="Meeting notes are posted in the channel thread.")
                if not self.ever_recorded:
                    self._emit("error", message="Compliance: Max posted notes but never called updateRecordingStatus.")
                if self.mode == "autopilot" and not self._stop.is_set():
                    try:
                        result = score(self.world.expected, notes, self.max_answers)
                        self._emit("score", result=result)
                    except LLMError as e:
                        self._emit("error", message=f"Scoring failed: {e}")
            else:
                self._emit("error", message="Max did not post meeting notes within 3 minutes.")
        self._save_run(notes, result)
        self.status = "ended"
        self._emit("state", status="ended")
        self._publish_transcript()

    def _publish_transcript(self) -> None:
        """Transcription ran during the meeting: the official transcript appears in Graph shortly after."""
        if not self.transcript:
            return
        cues = [(u["t"], "Max (AI)" if u["speaker"] == "max" else self.world.name(u["speaker"]), u["text"])
                for u in self.transcript]

        run = self.t0

        def later():
            time.sleep(3)
            if self.meetings.add_live_transcript(LIVE_KEY, cues) and self.t0 == run:
                self._emit("chat", speaker="system", text="Transcript is ready in the meeting recap (Microsoft Graph).")

        threading.Thread(target=later, daemon=True).start()

    def _save_run(self, notes, result) -> None:
        runs = self.world.root / "runs"
        runs.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        (runs / f"{stamp}_{self.mode}_{self.media}.json").write_text(json.dumps({
            "mode": self.mode, "media": self.media, "speed": self.speed, "transcript": self.transcript,
            "max_answers": self.max_answers, "notes": notes, "score": result,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
