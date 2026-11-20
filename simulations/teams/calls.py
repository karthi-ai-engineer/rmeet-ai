"""
Microsoft Graph Cloud Communications (calls) for the fake tenant + the media stand-in.

Call control (exact REST/JSON contract, docs/research/teams/03-meeting-calling.md §1-4):
  POST   /communications/calls                              join a meeting (app-hosted media)
  GET    /communications/calls/{id} | /participants
  DELETE /communications/calls/{id}                         hang up (200/7000)
  POST   /communications/calls/{id}/updateRecordingStatus   must succeed before media is persisted
  POST   /communications/calls/{id}/keepAlive | mute | unmute
Callbacks: commsNotifications POSTed to callbackUri with a signed JWT
  (iss https://api.botframework.com, aud = bot app id, tid): establishing, established,
  roster (participants with audio sourceId = MSI), terminating, terminated.

Media stand-in (the real one is the Windows-only .NET media SDK), WebSocket /media/{callId}:
  downlink binary: 4-byte LE header length + JSON header + PCM16k payload, every 20 ms:
     {"t":"audio","ts":ticks,"isSilence":b,"activeSpeakers":[msi],"unmixed":[{"msi":m,"len":640}]}
     payload = 640 B mixed + 640 B per unmixed speaker
  downlink text: {"t":"session",...} {"t":"sendStatus","status":"Active"} {"t":"dominantSpeaker","msi":m}
                 {"t":"transcript",...}  (Work IQ-style real-time transcript, placeholder 'sim-v0')
  uplink binary: 640-byte PCM frames from the bot (paced 50/s; frames before sendStatus Active are dropped)
"""

import json
import queue
import threading
import time
import urllib.error
import urllib.request
import uuid
from urllib.parse import unquote

from audio import FRAME_BYTES, SILENCE, frames, pack_media
from httpx_types import Req, Resp, Router
from identity import GRAPH_AUDIENCE, Identity
from store import TENANT_ID, TeamsStore
from ws import WebSocket, WSClosed

BOT_MSI = 10
JOIN_ROLES = ("Calls.JoinGroupCall.All", "Calls.AccessMedia.All")


class Call:
    def __init__(self, call_id: str, app_id: str, callback: str, meeting: dict, body: dict):
        self.id, self.app_id, self.callback, self.meeting, self.body = call_id, app_id, callback, meeting, body
        self.state = "establishing"
        self.my_pid = str(uuid.uuid4())
        self.recording = "notRecording"
        self.ws: WebSocket | None = None
        self.send_active = False
        self.cb_queue: queue.Queue = queue.Queue()
        self.down_queue: queue.Queue = queue.Queue()     # (frames, msi, done_event)
        self.alive = True
        self.last_keepalive = time.time()


class CallsService:
    def __init__(self, base_url: str, identity: Identity, store: TeamsStore, meetings, err, notify_ui):
        self.base = base_url.rstrip("/")
        self.identity, self.store, self.meetings, self._err, self.notify_ui = identity, store, meetings, err, notify_ui
        self.calls: dict[str, Call] = {}
        self.live = None              # {"key", "participants": [...], "mode": "voice"|"text", "listener": obj}
        self.lock = threading.RLock()

    # ============================================================== live meeting (director side)
    def open_meeting(self, key: str, participants: list[dict], mode: str, listener) -> None:
        """participants: [{key, name, aadObjectId, msi}] humans in the meeting."""
        with self.lock:
            self.live = {"key": key, "participants": participants, "mode": mode, "listener": listener}

    def bot_call(self) -> Call | None:
        with self.lock:
            if not self.live:
                return None
            return next((c for c in self.calls.values() if c.alive and c.meeting["key"] == self.live["key"]), None)

    def close_meeting(self, code: str = "200", subcode: str = "5001", message: str = "The conversation has ended.") -> None:
        call = self.bot_call()
        with self.lock:
            self.live = None
        if call:
            self._terminate(call, code, subcode, message)

    def play(self, msi: int, pcm16k: bytes, wait: bool = True) -> None:
        """A participant speaks: stream their audio to the bot at real-time pace."""
        call = self.bot_call()
        if not call or not call.ws:
            return
        done = threading.Event()
        call.down_queue.put((frames(pcm16k), msi, done))
        if wait:
            done.wait(timeout=len(pcm16k) / 32000 + 5)

    def transcript(self, msi: int, name: str, aad: str, text: str, offset_ms: int) -> None:
        """Work IQ-style real-time transcript line (placeholder protocol 'sim-v0')."""
        call = self.bot_call()
        if call and call.ws:
            try:
                call.ws.send_text(json.dumps({"t": "transcript", "protocol": "sim-v0", "msi": msi,
                                              "speaker": {"displayName": name, "id": aad}, "text": text,
                                              "offsetMs": offset_ms, "isFinal": True}))
            except WSClosed:
                pass

    # ===================================================================== REST
    def routes(self, r: Router) -> None:
        c = r"/graph/v1\.0/communications/calls"
        r.add("POST", c, self._create)
        r.add("GET", c + r"/([^/?]+)", self._get)
        r.add("GET", c + r"/([^/?]+)/participants", self._participants)
        r.add("DELETE", c + r"/([^/?]+)", self._delete)
        r.add("POST", c + r"/([^/?]+)/updateRecordingStatus", self._recording)
        r.add("POST", c + r"/([^/?]+)/keepAlive", self._keepalive)
        r.add("POST", c + r"/([^/?]+)/(mute|unmute)", self._mute)

    def _claims(self, req: Req):
        return self.identity.verify_app_token(req.bearer(), GRAPH_AUDIENCE)

    def _call_json(self, call: Call) -> dict:
        b = call.body
        return {"@odata.type": "#microsoft.graph.call", "@odata.context": f"{self.base}/graph/v1.0/$metadata#app/calls/$entity",
                "id": call.id, "state": call.state, "direction": "outgoing", "callbackUri": call.callback,
                "requestedModalities": b.get("requestedModalities", ["audio"]), "mediaConfig": b.get("mediaConfig"),
                "chatInfo": {**(b.get("chatInfo") or {}), "replyChainMessageId": None},
                "meetingInfo": b.get("meetingInfo"), "tenantId": TENANT_ID, "myParticipantId": call.my_pid,
                "resultInfo": None, "mediaState": None, "toneInfo": None}

    def _create(self, req: Req) -> Resp:
        claims = self._claims(req)
        if not claims:
            return self._err(401, "InvalidAuthenticationToken", "Access token validation failure.")
        b = req.json()
        roles = claims.get("roles", [])
        needed = JOIN_ROLES if "appHostedMediaConfig" in json.dumps(b.get("mediaConfig") or {}) else JOIN_ROLES[:1]
        missing = [r for r in needed if r not in roles]
        if missing:
            return self._err(403, "Forbidden", f"Application is not authorized: missing {', '.join(missing)} "
                                               f"(requires admin consent).")
        if b.get("tenantId") and b["tenantId"] != TENANT_ID:
            return Resp.json(403, {"error": {"code": "7505", "message": "Request authorization tenant mismatch."}})
        cb = b.get("callbackUri") or ""
        if not (cb.startswith("https://") or cb.startswith("http://localhost") or cb.startswith("http://127.0.0.1")):
            return self._err(400, "BadRequest", "callbackUri must be an https URL.")
        thread = unquote(((b.get("chatInfo") or {}).get("threadId")) or "")
        meeting = next((m for m in self.meetings.meetings.values() if m["threadId"] == thread), None)
        if not meeting:
            return self._err(404, "NotFound", "The meeting was not found (chatInfo.threadId).")
        org = (((b.get("meetingInfo") or {}).get("organizer") or {}).get("user") or {}).get("id")
        if org and org != self.store.users[meeting["organizer"]]["aadObjectId"]:
            return self._err(400, "BadRequest", "meetingInfo.organizer does not match the meeting.")
        with self.lock:
            if not self.live or self.live["key"] != meeting["key"]:
                return self._err(404, "NotFound", "The meeting is not in progress.")
            if self.bot_call():
                return self._err(409, "Conflict", "The application is already in this meeting.")
            call = Call(str(uuid.uuid4()), claims["appid"], cb, meeting, b)
            self.calls[call.id] = call
        threading.Thread(target=self._callback_worker, args=(call,), daemon=True).start()
        self._notify(call, "updated", f"/communications/calls/{call.id}",
                     {"@odata.type": "#microsoft.graph.call", "state": "establishing", "id": call.id})
        self.notify_ui({"type": "call", "state": "establishing"})
        return Resp.json(201, self._call_json(call), {"Location": f"{self.base}/graph/v1.0/communications/calls/{call.id}"})

    def _own(self, req: Req, cid: str):
        claims = self._claims(req)
        if not claims:
            return None, self._err(401, "InvalidAuthenticationToken", "Access token validation failure.")
        call = self.calls.get(unquote(cid))
        if not call or call.app_id != claims["appid"] or not call.alive:
            return None, self._err(404, "NotFound", "Call not found.")
        return call, None

    def _get(self, req: Req, cid: str) -> Resp:
        call, err = self._own(req, cid)
        return err or Resp.json(200, self._call_json(call))

    def _participants(self, req: Req, cid: str) -> Resp:
        call, err = self._own(req, cid)
        return err or Resp.json(200, {"value": self._roster(call)})

    def _delete(self, req: Req, cid: str) -> Resp:
        call, err = self._own(req, cid)
        if err:
            return err
        self._terminate(call, "200", "7000", "Ended by bot.")
        return Resp(204, b"", {})

    def _op(self, kind: str, call: Call, body: dict, extra: dict | None = None) -> Resp:
        op_id = str(uuid.uuid4())
        return Resp.json(200, {"@odata.type": f"#microsoft.graph.{kind}", "id": op_id, "status": "completed",
                               "clientContext": body.get("clientContext"),
                               "resultInfo": {"@odata.type": "#microsoft.graph.resultInfo", "code": 200, "subcode": 0,
                                              "message": "Action completed successfully."}, **(extra or {})},
                         {"Location": f"{self.base}/graph/v1.0/communications/calls/{call.id}/operations/{op_id}"})

    def _recording(self, req: Req, cid: str) -> Resp:
        call, err = self._own(req, cid)
        if err:
            return err
        b = req.json()
        status = b.get("status")
        if status not in ("recording", "notRecording", "failed"):
            return self._err(400, "BadRequest", "status must be recording, notRecording or failed.")
        call.recording = status
        self.notify_ui({"type": "recording", "status": status})
        listener = (self.live or {}).get("listener")
        if listener:
            listener.on_recording(status)
        return self._op("updateRecordingStatusOperation", call, b)

    def _keepalive(self, req: Req, cid: str) -> Resp:
        call, err = self._own(req, cid)
        if err:
            return err
        call.last_keepalive = time.time()
        return Resp(200, b"", {})

    def _mute(self, req: Req, cid: str, action: str) -> Resp:
        call, err = self._own(req, cid)
        if err:
            return err
        call.muted = action == "mute"
        self._send_roster(call)
        return self._op("muteParticipantOperation" if call.muted else "unmuteParticipantOperation", call, req.json())

    # ================================================================ callbacks
    def _notify(self, call: Call, change: str, resource_url: str, data) -> None:
        call.cb_queue.put({"@odata.type": "#microsoft.graph.commsNotifications", "value": [{
            "@odata.type": "#microsoft.graph.commsNotification", "changeType": change,
            "resourceUrl": resource_url, "callbackUri": call.callback, "resourceData": data}]})

    def _callback_worker(self, call: Call) -> None:
        """Delivers notifications in order, each with a signed Bot Framework-style JWT."""
        while True:
            payload = call.cb_queue.get()
            if payload is None:
                return
            now = int(time.time())
            token = self.identity.sign({"iss": "https://api.botframework.com", "aud": call.app_id, "tid": TENANT_ID,
                                        "iat": now, "nbf": now - 5, "exp": now + 3600})
            req = urllib.request.Request(call.callback, data=json.dumps(payload).encode(), method="POST", headers={
                "Content-Type": "application/json", "Authorization": f"Bearer {token}"})
            for attempt in range(3):
                try:
                    with urllib.request.urlopen(req, timeout=10) as r:
                        r.read()
                    break
                except Exception:
                    time.sleep(1 + attempt)

    def _roster(self, call: Call) -> list:
        live = self.live or {"participants": []}
        out = []
        for p in live["participants"]:
            out.append({"@odata.type": "#microsoft.graph.participant",
                        "info": {"@odata.type": "#microsoft.graph.participantInfo",
                                 "identity": {"@odata.type": "#microsoft.graph.identitySet",
                                              "user": {"@odata.type": "#microsoft.graph.identity",
                                                       "displayName": p["name"], "id": p["aadObjectId"],
                                                       "tenantId": TENANT_ID}},
                                 "languageId": "en-US"},
                        "mediaStreams": [{"@odata.type": "#microsoft.graph.mediaStream", "mediaType": "audio",
                                          "label": "main-audio", "sourceId": str(p["msi"]),
                                          "direction": "sendReceive", "serverMuted": False}],
                        "isMuted": False, "isInLobby": False, "id": p["participantId"]})
        reg = self.identity.registration
        out.append({"@odata.type": "#microsoft.graph.participant",
                    "info": {"@odata.type": "#microsoft.graph.participantInfo",
                             "identity": {"@odata.type": "#microsoft.graph.identitySet",
                                          "application": {"@odata.type": "#microsoft.graph.identity",
                                                          "displayName": reg.get("botName", "Max"), "id": call.app_id}}},
                    "mediaStreams": [{"@odata.type": "#microsoft.graph.mediaStream", "mediaType": "audio",
                                      "sourceId": str(BOT_MSI), "direction": "sendReceive", "serverMuted": False}],
                    "isMuted": getattr(call, "muted", False), "isInLobby": False, "id": call.my_pid})
        return out

    def _send_roster(self, call: Call) -> None:
        self._notify(call, "updated", f"/communications/calls/{call.id}/participants", self._roster(call))

    def _terminate(self, call: Call, code: str, subcode: str, message: str) -> None:
        if not call.alive:
            return
        call.alive = False
        call.state = "terminated"
        self._notify(call, "updated", f"/communications/calls/{call.id}",
                     {"@odata.type": "#microsoft.graph.call", "state": "terminating"})
        self._notify(call, "deleted", f"/communications/calls/{call.id}",
                     {"@odata.type": "#microsoft.graph.call", "state": "terminated",
                      "resultInfo": {"@odata.type": "#microsoft.graph.resultInfo", "code": code, "subcode": subcode,
                                     "message": message}})
        call.cb_queue.put(None)
        call.down_queue.put(None)
        if call.ws:
            call.ws.close()
        self.notify_ui({"type": "call", "state": "terminated", "subcode": subcode})
        listener = (self.live or {}).get("listener")
        if listener and subcode == "7000":
            listener.on_bot_left()

    # ==================================================================== media
    def media_connect(self, handler, call_id: str, token: str | None) -> None:
        """WebSocket /media/{callId}: the media stand-in. Runs in the HTTP handler thread."""
        call = self.calls.get(call_id)
        claims = self.identity.verify_app_token(token, GRAPH_AUDIENCE)
        if not call or not call.alive or not claims or claims["appid"] != call.app_id:
            handler.send_error(401 if not claims else 404)
            return
        ws = WebSocket.accept(handler)
        if not ws:
            handler.send_error(400, "WebSocket upgrade required")
            return
        call.ws = ws
        mode = (self.live or {}).get("mode", "voice")
        ws.send_text(json.dumps({"t": "session", "callId": call.id, "protocol": "sim-media-v1",
                                 "audio": {"format": "Pcm16K", "frameMs": 20, "frameBytes": FRAME_BYTES,
                                           "unmixed": True, "direction": "sendrecv"},
                                 "audioStream": mode == "voice", "transcriptStream": mode == "text"}))
        # media connected -> call established + full roster
        call.state = "established"
        self._notify(call, "updated", f"/communications/calls/{call.id}",
                     {"@odata.type": "#microsoft.graph.call", "state": "established", "direction": "outgoing",
                      "id": call.id})
        self._send_roster(call)
        self.notify_ui({"type": "call", "state": "established"})
        listener = (self.live or {}).get("listener")
        if listener:
            listener.on_bot_joined(call)
        threading.Thread(target=self._pacer, args=(call, mode), daemon=True).start()
        time.sleep(0.2)
        try:
            ws.send_text(json.dumps({"t": "sendStatus", "status": "Active"}))
            call.send_active = True
            while call.alive:
                opcode, data = ws.recv()
                if opcode == 0x2 and call.send_active and listener:
                    for i in range(0, len(data) - FRAME_BYTES + 1, FRAME_BYTES):
                        listener.on_bot_audio(data[i:i + FRAME_BYTES])
                elif opcode == 0x1:
                    pass                                           # control messages from the bot (ignored)
        except WSClosed:
            pass
        finally:
            call.ws = None
            if call.alive and listener:
                listener.on_media_lost()

    def _pacer(self, call: Call, mode: str) -> None:
        """Sends a frame every 20 ms: queued speech, otherwise silence (voice mode only)."""
        if mode != "voice":
            return
        ticks = 0
        current, msi, done, idx = None, None, None, 0
        last_dominant = None
        next_t = time.perf_counter()
        while call.alive and call.ws:
            if current is None:
                try:
                    item = call.down_queue.get_nowait()
                    if item is None:
                        return
                    current, msi, done = item
                    idx = 0
                except queue.Empty:
                    pass
            try:
                if current is not None and idx < len(current):
                    if last_dominant != msi:
                        call.ws.send_text(json.dumps({"t": "dominantSpeaker", "msi": msi}))
                        last_dominant = msi
                    fr = current[idx]
                    idx += 1
                    call.ws.send_binary(pack_media({"t": "audio", "ts": ticks, "isSilence": False,
                                                    "activeSpeakers": [msi], "unmixed": [{"msi": msi, "len": FRAME_BYTES}]},
                                                   fr + fr))
                    if idx >= len(current):
                        done.set()
                        current = None
                else:
                    call.ws.send_binary(pack_media({"t": "audio", "ts": ticks, "isSilence": True,
                                                    "activeSpeakers": [], "unmixed": []}, SILENCE))
            except WSClosed:
                if done:
                    done.set()
                return
            ticks += 200000                       # 20 ms in 100 ns units
            next_t += 0.02
            delay = next_t - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            else:
                next_t = time.perf_counter()
