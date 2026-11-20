"""
Max in a Teams meeting call (Graph Cloud Communications + media).

  join     POST /communications/calls (appHostedMediaConfig, chatInfo + organizerMeetingInfo from the join URL)
  control  callbacks at /api/calling: establishing -> established -> roster -> terminated
  comply   POST /calls/{id}/updateRecordingStatus {"status":"recording"} before keeping anything derived from media
  hear     media frames (20 ms PCM16k tagged with MSIs) -> per-speaker segments -> speech-to-text,
           or Work IQ-style transcript lines when the meeting only offers text
  speak    TTS -> 640-byte frames paced 50/s up the media connection (stops if someone talks over Max);
           falls back to the meeting chat when voice isn't available
  end      notes posted in the meeting thread (channel meeting chat)

The media connection is a WebSocket to MEDIA_RELAY_URL. In the simulator that is rmeet-ai; in production
it is a thin Windows/.NET worker hosting Microsoft's real-time media SDK and relaying the same frames.
"""

import asyncio
import json
import logging
import re
import time
import uuid
from urllib.parse import parse_qs, unquote, urlsplit

import websockets

import brain
import voice
from audio import FRAME_BYTES, frames, unpack_media, wav_to_pcm16k
from auth import TOKENS
from config import CONFIG
from graph_client import GraphClient, GraphError
from llm import LLMError

log = logging.getLogger("max")
END_SILENCE = 0.6          # seconds of silence that ends a speaker's segment
MIN_SEGMENT = 0.35         # ignore shorter blips
STT_HINT = ("Max, Karthi, Prince, Daniel, Jacob, Elena, Northgate Freight, Vector Robotics, LiftLine Systems, "
            "Riverside, Eastgate, Brightpack, Corrin, Orbis, Fresh Home Spring, H1, FY2027")


def parse_join_url(url: str) -> dict:
    """https://teams.microsoft.com/l/meetup-join/{threadId}/0?context={"Tid":..,"Oid":..}"""
    parts = urlsplit(url)
    m = re.search(r"/meetup-join/([^/]+)/", parts.path)
    ctx = json.loads(unquote(parse_qs(parts.query).get("context", ["{}"])[0]))
    return {"threadId": unquote(m.group(1)) if m else None, "organizerId": ctx.get("Oid"), "tenantId": ctx.get("Tid")}


class MeetingCall:
    def __init__(self, app, graph: GraphClient, team_id: str, knowledge, conversation_id: str, service_url: str,
                 title: str, on_finished):
        self.app, self.graph, self.team_id, self.kb = app, graph, team_id, knowledge
        self.conversation_id, self.service_url, self.title = conversation_id, service_url, title
        self.on_finished = on_finished
        self.session = brain.MeetingSession(str(uuid.uuid4()), title, knowledge.prompt_text())
        self.call_id = None
        self.state = "new"
        self.roster: dict[str, dict] = {}          # MSI (string) -> {"name", "id"}
        self.recording = False
        self.ws = None
        self.audio_mode = True
        self.send_active = asyncio.Event()
        self.buffers: dict[str, bytearray] = {}
        self.last_heard: dict[str, float] = {}
        self.stt_queue: asyncio.Queue = asyncio.Queue()
        self.humans_talking_since = None
        self.speaking = False
        self.answering = False
        self.finished = False
        self.tasks: list[asyncio.Task] = []

    # ================================================================ join / leave
    async def join(self, join_url: str) -> None:
        info = parse_join_url(join_url)
        body = {
            "@odata.type": "#microsoft.graph.call", "direction": "outgoing",
            "callbackUri": CONFIG.callback_url, "requestedModalities": ["audio"],
            "mediaConfig": {"@odata.type": "#microsoft.graph.appHostedMediaConfig",
                            "blob": json.dumps({"simMediaSession": {"audio": {"dir": "sendrecv", "format": "Pcm16K",
                                                                              "unmixed": True},
                                                                    "video": {"dir": "inactive"}}})},
            "chatInfo": {"@odata.type": "#microsoft.graph.chatInfo", "threadId": info["threadId"], "messageId": "0"},
            "meetingInfo": {"@odata.type": "#microsoft.graph.organizerMeetingInfo",
                            "organizer": {"@odata.type": "#microsoft.graph.identitySet",
                                          "user": {"@odata.type": "#microsoft.graph.identity",
                                                   "id": info["organizerId"], "tenantId": info["tenantId"]}},
                            "allowConversationWithoutHost": True},
            "tenantId": info["tenantId"]}
        call = await self.graph.post("/communications/calls", body)
        self.call_id, self.state = call["id"], call["state"]
        log.info("Joining '%s' (call %s, %s)", self.title, self.call_id, self.state)
        # App-hosted media is negotiated while the call is 'establishing'; the call becomes
        # 'established' once the media session is up.
        self.tasks.append(asyncio.create_task(self._media()))
        self.tasks.append(asyncio.create_task(self._keepalive()))

    async def leave(self) -> None:
        if self.call_id and self.state not in ("terminated", "terminating"):
            try:
                await self.graph.delete(f"/communications/calls/{self.call_id}")
            except GraphError as e:
                log.warning("Hang up failed: %s", e)

    async def _keepalive(self) -> None:
        while self.state not in ("terminated",):
            await asyncio.sleep(600)              # Graph requires one every 15-45 minutes
            try:
                await self.graph.post(f"/communications/calls/{self.call_id}/keepAlive", {})
            except GraphError:
                return

    # ================================================================ callbacks
    async def on_notification(self, n: dict) -> None:
        data, url = n.get("resourceData"), n.get("resourceUrl", "")
        if url.endswith("/participants") and isinstance(data, list):
            self._roster(data)
            return
        if isinstance(data, dict) and data.get("@odata.type", "").lower().endswith(".call"):
            state = data.get("state")
            if not state:
                return
            log.info("Call %s", state)
            self.state = state
            if state == "established" and not self.recording:
                await self._start_recording()
            elif state == "terminated":
                code = (data.get("resultInfo") or {})
                log.info("Call ended (%s/%s %s)", code.get("code"), code.get("subcode"), code.get("message"))
                await self.finish()

    def _roster(self, participants: list) -> None:
        for p in participants:
            ident = (p.get("info") or {}).get("identity") or {}
            who = ident.get("user") or ident.get("guest")
            if not who or p.get("isInLobby"):
                continue                           # skip the bot itself (application) and lobby
            for s in p.get("mediaStreams") or []:
                if s.get("mediaType") == "audio":
                    self.roster[str(s["sourceId"])] = {"name": who.get("displayName") or "Someone", "id": who.get("id")}
        log.info("Roster: %s", ", ".join(f"{k}={v['name']}" for k, v in sorted(self.roster.items())))

    async def _start_recording(self) -> None:
        try:
            await self.graph.post(f"/communications/calls/{self.call_id}/updateRecordingStatus",
                                  {"clientContext": str(uuid.uuid4()), "status": "recording"})
            self.recording = True
            log.info("Recording status: recording (participants see the banner)")
        except GraphError as e:
            log.warning("updateRecordingStatus failed (%s): Max will listen but not keep notes", e)

    # ==================================================================== media
    async def _media(self) -> None:
        url = f"{CONFIG.media_relay_url}/{self.call_id}"
        for attempt in range(3):
            if self.finished or self.state == "terminated":
                return
            try:
                token = await TOKENS.get(CONFIG.graph_scope)
                async with websockets.connect(url, additional_headers={"Authorization": f"Bearer {token}"},
                                              max_size=None) as ws:
                    self.ws = ws
                    if attempt == 0:
                        self.tasks.append(asyncio.create_task(self._segmenter()))
                        self.tasks.append(asyncio.create_task(self._stt_worker()))
                    async for msg in ws:
                        if isinstance(msg, bytes):
                            self._on_audio(msg)
                        else:
                            await self._on_control(json.loads(msg))
                log.info("Media connection closed")
                return
            except websockets.ConnectionClosed:
                log.info("Media connection closed")
                return
            except Exception as e:                  # handshake refused, network error, bad frame...
                log.error("Media connection failed (try %d/3): %s: %s", attempt + 1, type(e).__name__, e)
                await asyncio.sleep(1 + attempt)
            finally:
                self.ws = None

    async def _on_control(self, m: dict) -> None:
        t = m.get("t")
        if t == "session":
            self.audio_mode = bool(m.get("audioStream", True))
            log.info("Media session: %s", "audio frames (voice)" if self.audio_mode else "real-time transcript (text)")
        elif t == "sendStatus" and m.get("status") == "Active":
            self.send_active.set()
        elif t == "transcript":
            spk = m.get("speaker") or {}
            name = spk.get("displayName") or self.roster.get(str(m.get("msi")), {}).get("name", "Someone")
            await self._line(name, m.get("text", ""))

    def _on_audio(self, msg: bytes) -> None:
        header, payload = unpack_media(msg)
        now = time.time()
        humans = [str(x) for x in header.get("activeSpeakers") or []]
        if humans:
            self.humans_talking_since = self.humans_talking_since or now
        else:
            self.humans_talking_since = None
        off = FRAME_BYTES                            # mixed frame first, then one frame per unmixed speaker
        for u in header.get("unmixed") or []:
            msi = str(u["msi"])
            self.buffers.setdefault(msi, bytearray()).extend(payload[off:off + u.get("len", FRAME_BYTES)])
            self.last_heard[msi] = now
            off += u.get("len", FRAME_BYTES)

    async def _segmenter(self) -> None:
        """A speaker's segment ends after END_SILENCE without their audio."""
        while not self.finished:
            await asyncio.sleep(0.1)
            now = time.time()
            for msi, buf in list(self.buffers.items()):
                if buf and now - self.last_heard.get(msi, now) >= END_SILENCE:
                    pcm = bytes(buf)
                    buf.clear()
                    if len(pcm) / 32000 >= MIN_SEGMENT:
                        await self.stt_queue.put((msi, pcm))

    async def _stt_worker(self) -> None:
        while not self.finished:
            msi, pcm = await self.stt_queue.get()
            try:
                text = await asyncio.to_thread(voice.listen, pcm, STT_HINT)
            except voice.VoiceError as e:
                log.warning("Speech-to-text failed: %s", e)
                continue
            if text:
                await self._line(self.roster.get(msi, {}).get("name", f"Speaker {msi}"), text)

    # ==================================================================== brain
    async def _line(self, speaker: str, text: str) -> None:
        if not text.strip():
            return
        addressed = self.session.hear(speaker, text)
        log.info("Heard %s: %s%s", speaker, text[:90], "  [-> Max]" if addressed else "")
        if addressed and not self.answering:
            self.answering = True
            asyncio.create_task(self._answer())

    async def _answer(self) -> None:
        try:
            reply = await asyncio.to_thread(self.session.answer)
        except LLMError as e:
            log.warning("Could not answer: %s", e)
            self.answering = False
            return
        try:
            if self.audio_mode and self.ws is not None:
                await self._speak(reply)
            else:
                await self._chat(reply)
        finally:
            self.answering = False

    async def _speak(self, text: str) -> None:
        try:
            wav = await asyncio.to_thread(voice.speak, text)
        except voice.VoiceError as e:
            log.warning("Voice unavailable (%s): answering in the meeting chat", e)
            await self._chat(text)
            return
        pcm = wav_to_pcm16k(wav)
        await asyncio.wait_for(self.send_active.wait(), 10)
        self.speaking = True
        log.info("Speaking %.1fs: %s", len(pcm) / 32000, text[:90])
        start = time.perf_counter()
        try:
            for i, fr in enumerate(frames(pcm)):
                # Barge-in: stop if someone has been talking over Max for 0.5 s.
                if self.humans_talking_since and time.time() - self.humans_talking_since > 0.5:
                    log.info("Interrupted: stopped speaking")
                    break
                if self.ws is None:
                    break
                await self.ws.send(fr)
                delay = start + (i + 1) * 0.02 - time.perf_counter()     # pace 50 frames per second
                if delay > 0:
                    await asyncio.sleep(delay)
        except websockets.ConnectionClosed:
            pass
        finally:
            self.speaking = False

    async def _chat(self, text: str) -> None:
        await self.app.send(self.conversation_id, text, service_url=self.service_url)

    # ==================================================================== end
    async def finish(self) -> None:
        if self.finished:
            return
        self.finished = True
        for t in self.tasks:
            t.cancel()
        if self.ws is not None:
            await self.ws.close()
        if not self.recording:
            log.warning("No recording status was set: not keeping notes (Microsoft media access policy)")
            await self._chat("I didn't have permission to record this meeting, so I won't keep notes for it.")
            self.on_finished(self)
            return
        if len(self.session.transcript) < 2:
            self.on_finished(self)
            return
        try:
            notes = await asyncio.to_thread(self.session.summarize)
            text = brain.notes_markdown(self.title, notes)
            sent = await self.app.send(self.conversation_id, text, service_url=self.service_url)
            root = self.conversation_id.split(";messageid=")[-1]
            self.kb.add_message(sent.id, "Max", text, root)
            log.info("Meeting notes posted in the meeting thread")
        except (LLMError, Exception) as e:
            log.error("Could not write the notes: %s", e)
        self.on_finished(self)
