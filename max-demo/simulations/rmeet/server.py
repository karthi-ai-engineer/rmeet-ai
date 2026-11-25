"""
rmeet-ai server = the Teams-style client UI + a fake "Microsoft" for Max.

  UI + meeting engine          /, /static/*, /api/*
  Fake Microsoft (teams/):
    Entra token + bot keys      /login/..., /botframework/v1/.well-known/...
    Bot Connector REST API      /teams/v3/...
    Microsoft Graph subset      /graph/v1.0/...

Run:  .venv/Scripts/python simulations/rmeet/server.py
Open: http://localhost:8100
"""

import json
import mimetypes
import os
import queue
import re
import sys
import threading
import time
import uuid
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "teams"))

import llm  # noqa: E402  (loads .env)
import voices  # noqa: E402
from calls import CallsService  # noqa: E402
from connector import Connector  # noqa: E402
from director import EventBus, Meeting  # noqa: E402
from graph import Graph  # noqa: E402
from httpx_types import Req, Router  # noqa: E402
from identity import Identity  # noqa: E402
from mail import GraphMail, MailData  # noqa: E402
from meetings import GraphMeetings, MeetingsData  # noqa: E402
from store import TeamsStore, iso  # noqa: E402
from subscriptions import Subscriptions  # noqa: E402
from world import World, doc_text  # noqa: E402

STATIC = HERE / "static"


def ui_version() -> str:
    """Changes whenever a UI file changes: open pages compare it and reload themselves (no stale scripts)."""
    return str(max(int(f.stat().st_mtime) for f in STATIC.iterdir() if f.is_file()))
AVATAR_JS = HERE.parents[1] / "bot-avatar" / "avatar.js"
CATALOG_MANIFEST = HERE.parent / "teams" / "state" / "app_package" / "manifest.json"
PORT = int(os.environ.get("RMEET_PORT", "8100"))
BASE_URL = f"http://localhost:{PORT}"
FAKE_MS_PREFIXES = ("/login/", "/botframework/", "/teams/", "/graph/")


class ChannelBus:
    """Live channel updates for the UI (no history; the UI reloads /api/channel)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._subs: list[queue.Queue] = []

    def publish(self, ev: dict) -> None:
        with self._lock:
            for q in self._subs:
                q.put(ev)

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._subs.append(q)
        return q

    def unsubscribe(self, q) -> None:
        with self._lock:
            if q in self._subs:
                self._subs.remove(q)


WORLD = World()
BUS = EventBus()
CHANNEL_BUS = ChannelBus()
IDENTITY = Identity(BASE_URL)
STORE = TeamsStore()
STORE.on_change(CHANNEL_BUS.publish)
IDENTITY.roles_provider = lambda: STORE.admin.get("consented", [])
CONNECTOR = Connector(BASE_URL, IDENTITY, STORE, CHANNEL_BUS.publish)
GRAPH = Graph(BASE_URL, IDENTITY, STORE)
MEETINGS = MeetingsData(STORE)
GRAPH_MEETINGS = GraphMeetings(BASE_URL, IDENTITY, STORE, MEETINGS, Graph._err)
SUBSCRIPTIONS = Subscriptions(BASE_URL, IDENTITY, STORE, MEETINGS, Graph._err, CHANNEL_BUS.publish)
CALLS = CallsService(BASE_URL, IDENTITY, STORE, MEETINGS, Graph._err, CHANNEL_BUS.publish)
CONNECTOR.meetings = MEETINGS
MAIL = MailData(STORE, HERE.parent / "teams" / "state")
MAIL.listeners.append(CHANNEL_BUS.publish)
MEETINGS.on_change(lambda ev: CHANNEL_BUS.publish(ev) if ev.get("type") == "calendar" else None)
GRAPH_MAIL = GraphMail(BASE_URL, IDENTITY, STORE, MAIL, Graph._err)
ROUTER = Router()
for svc in (IDENTITY, CONNECTOR, GRAPH, GRAPH_MEETINGS, GRAPH_MAIL, SUBSCRIPTIONS, CALLS):
    svc.routes(ROUTER)
MEETING = Meeting(WORLD, BUS, IDENTITY, STORE, MEETINGS, CALLS, CONNECTOR)
SAMPLES: dict[str, bytes] = {}


class CalendarCall:
    """Listener for a meeting started from the Calendar view (any Teams meeting, e.g. one Max booked),
    as opposed to the scripted live meeting run by the director. Text mode: people type their lines."""

    def __init__(self, key: str, people: list[str] | None = None):
        self.key, self.t0, self.people = key, time.time(), people or []
        self.lines: list[dict] = []               # what was said (people's typed lines), for the meeting view
        self.recording, self.bot = "", ""

    def _ev(self, **kw) -> None:
        CHANNEL_BUS.publish({"type": "calendar_call", "key": self.key, **kw})

    def said(self, who: str, text: str) -> None:
        line = {"speaker": who, "text": text, "t": round(time.time() - self.t0, 1)}
        self.lines.append(line)
        self._ev(line=line)

    def on_recording(self, status: str) -> None:
        self.recording = status
        self._ev(recording=status)

    def on_bot_joined(self, call) -> None:
        self.bot = "joined"
        self._ev(bot="joined")

    def on_bot_left(self) -> None:
        self.bot = "left"
        self._ev(bot="left")

    def on_bot_audio(self, data: bytes) -> None:
        pass

    def on_media_lost(self) -> None:
        self._ev(bot="media-lost")


def max_models() -> dict:
    """What Max runs on (read from max/.env, written by register_app.py) and where the voices come from,
    so the UI can show colleagues / Max / mic / voices separately."""
    env = {}
    try:
        for line in (HERE.parents[1] / "max" / ".env").read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    except OSError:
        pass
    gem = env.get("GEMINI_BRAIN_MODEL", "gemini-3.1-flash-lite")
    max_brain = gem if env.get("BRAIN_PROVIDER", "qwen").lower() == "gemini" else env.get("TW_MODEL", llm.BRAIN_MODEL)
    return {"maxBrain": max_brain, "maxHearing": env.get("GEMINI_MODEL", llm.GEMINI_MODEL),
            "voices": "local (Kokoro)" if voices.TTS_PROVIDER == "local" else voices.TTS_MODEL}


def calendar_person(key: str) -> dict:
    u = STORE.users[key]
    return {"key": key, "name": u["name"], "aadObjectId": u["aadObjectId"], "msi": MEETING.msi[key],
            "participantId": str(uuid.uuid5(uuid.NAMESPACE_URL, "participant/" + key))}


THREAD_LINK = re.compile(r"teams\.microsoft\.com/l/message/[^/\s]+/(\d+)")


def chat_root(body: str) -> str | None:
    """The meeting's chat thread, from the Teams deep link Max puts in invites it books."""
    m = THREAD_LINK.search(body or "")
    return m.group(1) if m else None


def calendar_live() -> dict:
    """The calendar meeting running now (for the meeting view), or {"live": False}."""
    live = CALLS.live or {}
    m = MEETINGS.meetings.get(live.get("key") or "")
    lst = live.get("listener")
    if not m or not isinstance(lst, CalendarCall):
        return {"live": False}
    return {"live": True, "key": m["key"], "title": m["title"], "people": lst.people, "lines": lst.lines,
            "t": round(time.time() - lst.t0, 1), "recording": lst.recording,
            "botInCall": bool(CALLS.bot_call()), "threadRoot": chat_root(m.get("body") or "")}


def calendar_view(user: str) -> list[dict]:
    tu = STORE.tenant_users()
    live = (CALLS.live or {}).get("key")
    out = []
    for m in sorted(MEETINGS.meetings.values(), key=lambda m: m["startMs"]):
        if user != m["organizer"] and user not in m["attendees"]:
            continue
        out.append({"key": m["key"], "title": m["title"], "start": iso(m["startMs"]), "end": iso(m["endMs"]),
                    "organizer": tu.get(m["organizer"], {}).get("name", m["organizer"]),
                    "attendees": [tu.get(k, {}).get("name", k) for k in m["attendees"]],
                    "online": m.get("online", True), "joinUrl": m["joinUrl"] if m.get("online", True) else None,
                    "body": m.get("body") or "", "createdByMax": m["organizer"] == "max",
                    "threadRoot": chat_root(m.get("body") or ""),
                    "live": live == m["key"], "botInCall": bool(live == m["key"] and CALLS.bot_call())})
    return out


def admin_view() -> dict:
    reg = IDENTITY.registration
    return {"admin": STORE.admin, "requiredPermissions": reg.get("applicationPermissions", []),
            "appName": reg.get("botName"), "subscriptions": SUBSCRIPTIONS.public(), "log": SUBSCRIPTIONS.log[-50:]}


def app_catalog_entry() -> dict | None:
    """The uploaded Teams app package (what the 'Add app' dialog shows)."""
    if not CATALOG_MANIFEST.exists():
        return None
    m = json.loads(CATALOG_MANIFEST.read_text(encoding="utf-8"))
    return {"id": m["id"], "name": m["name"]["short"], "fullName": m["name"]["full"],
            "description": m["description"]["full"], "version": m["version"],
            "rsc": [p["name"] for p in m.get("authorization", {}).get("permissions", {}).get("resourceSpecific", [])],
            "registered": bool(IDENTITY.registration)}


class Handler(BaseHTTPRequestHandler):
    server_version = "rmeet-ai"

    # ------------------------------------------------------------ helpers
    def log_message(self, fmt, *args):
        line = str(args[0]) if args else ""
        if "/api/events" not in line and "/api/channel/events" not in line:
            super().log_message(fmt, *args)

    def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _file(self, path: Path, download_name: str | None = None) -> None:
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix == ".md":
            ctype = "text/markdown; charset=utf-8"
        extra = {"Content-Disposition": f'inline; filename="{download_name or path.name}"'}
        self._send(200, path.read_bytes(), ctype, extra)

    def _raw_body(self) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 15 * 1024 * 1024:
            return b""
        return self.rfile.read(length)

    def _fake_microsoft(self, method: str, raw: bytes) -> bool:
        """Route /login, /botframework, /teams, /graph to the fake Microsoft services."""
        url = urllib.parse.urlsplit(self.path)
        if not url.path.startswith(FAKE_MS_PREFIXES):
            return False
        req = Req(method=method, path=urllib.parse.unquote(url.path), raw_path=url.path,
                  query=urllib.parse.parse_qs(url.query), headers={k.lower(): v for k, v in self.headers.items()},
                  body=raw)
        try:
            resp = ROUTER.dispatch(req)
        except Exception as e:  # a real service answers 500, it doesn't drop the connection
            import traceback
            traceback.print_exc()
            self._json(500, {"error": {"code": "InternalServerError", "message": f"{type(e).__name__}: {e}"}})
            return True
        if resp is None:
            self._json(404, {"error": {"code": "NotFound", "message": f"No route for {method} {url.path}"}})
            return True
        self.send_response(resp.status)
        for k, v in resp.headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(resp.body)))
        self.end_headers()
        self.wfile.write(resp.body)
        return True

    def _sse(self, q, first: dict | None, unsubscribe) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            if first is not None:
                self.wfile.write(f"data: {json.dumps(first, ensure_ascii=False, default=str)}\n\n".encode())
                self.wfile.flush()
            while True:
                try:
                    ev = q.get(timeout=15)
                    self.wfile.write(f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n".encode())
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        finally:
            unsubscribe(q)

    # --------------------------------------------------------------- GET
    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        path = urllib.parse.unquote(url.path)
        qs = urllib.parse.parse_qs(url.query)
        if path.startswith("/media/"):
            # Media stand-in (WebSocket). Authenticated with the app's Graph token.
            auth = self.headers.get("Authorization", "")
            token = auth[7:] if auth.lower().startswith("bearer ") else (qs.get("access_token") or [None])[0]
            return CALLS.media_connect(self, path[len("/media/"):], token)
        if self._fake_microsoft("GET", b""):
            return
        m = re.match(r"^/api/(audio|voice-sample)/([0-9a-f]+)\.wav$", path)
        if m:
            data = (MEETING.clips if m.group(1) == "audio" else SAMPLES).get(m.group(2))
            return self._send(200, data, "audio/wav") if data else self._json(404, {"error": "Not found"})
        if path == "/api/voices":
            return self._json(200, {"candidates": voices.candidates(), "model": voices.TTS_MODEL,
                                    "assigned": {k: m.get("voice") for k, m in WORLD.members.items()},
                                    "max": "Charon"})

        if path in ("/", "/index.html"):
            return self._file(STATIC / "index.html")
        if path.startswith("/static/"):
            p = (STATIC / path[len("/static/"):]).resolve()
            if STATIC.resolve() in p.parents and p.is_file():
                return self._file(p)
            return self._json(404, {"error": "Not found"})
        if path == "/avatar.js":
            return self._file(AVATAR_JS)
        if path == "/api/world":
            return self._json(200, {**WORLD.public(), "meetingState": MEETING.snapshot(),
                                    "models": {"brain": llm.BRAIN_MODEL, "hearing": llm.GEMINI_MODEL,
                                               "qwenReady": llm.brain_ready(),
                                               "geminiReady": bool(llm.GEMINI_KEY), **max_models()}})
        if path == "/api/calendar/live":
            return self._json(200, calendar_live())
        if path == "/api/ui-version":
            return self._json(200, {"uiVersion": ui_version()})
        if path == "/api/channel":
            return self._json(200, {**STORE.ui_channel(), "app": app_catalog_entry(), "uiVersion": ui_version()})
        if path == "/api/admin":
            return self._json(200, admin_view())
        if path == "/api/people":
            return self._json(200, {"people": [{"key": k, "name": u["name"], "email": u["email"],
                                                "member": k in STORE.users, "role": u.get("role")}
                                               for k, u in STORE.tenant_users().items()]})
        if path == "/api/calendar":
            key = (qs.get("user") or ["karthi"])[0]
            if key not in STORE.tenant_users():
                return self._json(404, {"error": "Unknown person."})
            return self._json(200, {"user": key, "events": calendar_view(key)})
        if path == "/api/mail":
            key = (qs.get("user") or ["karthi"])[0]
            if key not in STORE.tenant_users():
                return self._json(404, {"error": "Unknown person."})
            return self._json(200, {"user": key, **MAIL.ui(key), "outbound": MAIL.outbound[-20:]})
        if path in ("/api/drive-doc", "/api/drive-file"):
            rec = STORE.files.get((qs.get("item") or [""])[0])
            if not rec:
                return self._json(404, {"error": "Not found"})
            if path == "/api/drive-file":
                return self._file(Path(rec["local"]), rec["name"])
            try:
                return self._json(200, {"name": rec["name"], "text": doc_text(rec["local"])})
            except Exception as e:
                return self._json(500, {"error": f"Could not read {rec['name']}: {e}"})
        if path == "/api/meeting":
            return self._json(200, MEETING.snapshot())
        if path == "/api/history":
            return self._json(200, {"events": list(BUS.history)})
        if path == "/api/doc":
            p = WORLD.safe_path((qs.get("path") or [""])[0])
            if not p:
                return self._json(404, {"error": "Not found"})
            try:
                return self._json(200, {"name": p.name, "text": doc_text(str(p))})
            except Exception as e:
                return self._json(500, {"error": f"Could not read {p.name}: {e}"})
        if path.startswith("/world/"):
            p = WORLD.safe_path(path[len("/world/"):])
            return self._file(p) if p else self._json(404, {"error": "Not found"})
        if path == "/api/events":
            q, history = BUS.subscribe()
            return self._sse(q, {"type": "replay", "events": history}, BUS.unsubscribe)
        if path == "/api/channel/events":
            return self._sse(CHANNEL_BUS.subscribe(), None, CHANNEL_BUS.unsubscribe)
        return self._json(404, {"error": "Not found"})

    # -------------------------------------------------------------- POST
    def do_POST(self):
        raw = self._raw_body()
        if self._fake_microsoft("POST", raw):
            return
        path = urllib.parse.urlsplit(self.path).path
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            body = {}
        try:
            if path == "/api/meeting/start":
                MEETING.start(body.get("mode", "live"), body.get("speed", 1), body.get("media", "voice"))
                return self._json(200, MEETING.snapshot())
            if path == "/api/meeting/say":
                import base64 as _b64
                wav = _b64.b64decode(body["audio"]) if body.get("audio") else None
                text = (body.get("text") or "").strip()
                if wav and not text:
                    text = llm.gemini_transcribe(body["audio"])     # caption for the room (Teams-side ASR)
                    if not text:
                        return self._json(422, {"error": "Didn't catch that. Try again or type."})
                MEETING.say(text, wav if MEETING.media == "voice" else None)
                return self._json(200, {"ok": True, "text": text})
            if path == "/api/voices/sample":
                voice = body.get("voice") or "Puck"
                known = voices.candidates()
                if voice not in known:
                    return self._json(400, {"error": "Unknown voice." if known else
                                            "Local voice server is not running (local-tts/server.py)."})
                wav = voices.synthesize((body.get("text") or "Hello, this is a voice test.")[:300], voice,
                                        body.get("style") or None)
                sid = __import__("hashlib").sha1(wav[:4096] + voice.encode()).hexdigest()[:20]
                SAMPLES[sid] = wav
                return self._json(200, {"url": f"/api/voice-sample/{sid}.wav"})
            if path == "/api/meeting/stop":
                MEETING.stop()
                return self._json(200, {"ok": True})
            if path == "/api/transcribe":
                audio = body.get("audio") or ""
                if not audio:
                    return self._json(400, {"error": "No audio received."})
                return self._json(200, {"text": llm.gemini_transcribe(audio, body.get("mimeType", "audio/wav"))})
            # ---- channel (the Teams client side) ----
            if path == "/api/channel/post":
                text = (body.get("text") or "").strip()
                if not text:
                    return self._json(400, {"error": "Write something first."})
                who = body.get("as") or "karthi"            # tests / demos can post as another team member
                if who not in STORE.users:
                    return self._json(400, {"error": "Unknown team member."})
                msg = CONNECTOR.user_posts(who, text, body.get("rootId") or None)
                return self._json(200, STORE.ui_message(msg))
            if path in ("/api/calendar/start", "/api/calendar/say", "/api/calendar/end"):
                m = MEETINGS.meetings.get(str(body.get("key") or ""))
                if not m or not m.get("online", True):
                    return self._json(404, {"error": "No such Teams meeting."})
                if path == "/api/calendar/start":
                    if CALLS.live or MEETING.status in ("live", "summarizing"):
                        return self._json(409, {"error": "Another meeting is in progress."})
                    people = [k for k in [m["organizer"], *m["attendees"]] if k in STORE.users]
                    people = list(dict.fromkeys(people))
                    CALLS.open_meeting(m["key"], [calendar_person(k) for k in people], "text",
                                       CalendarCall(m["key"], people))
                    CHANNEL_BUS.publish({"type": "calendar_call", "key": m["key"], "state": "live"})
                    return self._json(200, {"ok": True, "key": m["key"]})
                if (CALLS.live or {}).get("key") != m["key"]:
                    return self._json(409, {"error": "That meeting isn't running."})
                if path == "/api/calendar/say":
                    who = body.get("as") or "karthi"
                    text = (body.get("text") or "").strip()
                    if who not in STORE.users or not text:
                        return self._json(400, {"error": "Say something (as a team member)."})
                    u = STORE.users[who]
                    listener = CALLS.live["listener"]
                    CALLS.transcript(MEETING.msi[who], u["name"], u["aadObjectId"], text, int((time.time() - listener.t0) * 1000))
                    listener.said(who, text)
                    return self._json(200, {"ok": True, "botInCall": bool(CALLS.bot_call())})
                CALLS.close_meeting()
                CHANNEL_BUS.publish({"type": "calendar_call", "key": m["key"], "state": "ended"})
                return self._json(200, {"ok": True})
            if path == "/api/channel/card-action":
                who = body.get("as") or "karthi"            # the person clicking (UI 'Act as' switch)
                res = CONNECTOR.card_action(who, str(body.get("messageId") or ""), str(body.get("verb") or ""),
                                            body.get("data") or {}, body.get("inputs") or {})
                return self._json(400 if res.get("error") else 200, res)
            if path == "/api/channel/install":
                entry = app_catalog_entry()
                if not entry or not entry["registered"]:
                    return self._json(409, {"error": "Max's app isn't registered yet. Run: "
                                                     ".venv\\Scripts\\python simulations\\teams\\register_app.py"})
                IDENTITY.reload()
                if body.get("action") == "remove":
                    CONNECTOR.uninstall("karthi")
                else:
                    CONNECTOR.install("karthi", entry["rsc"])
                return self._json(200, {"install": STORE.install})
            if path == "/api/channel/reset":
                live = (CALLS.live or {})
                if isinstance(live.get("listener"), CalendarCall):    # a calendar meeting left running: end it
                    CALLS.close_meeting()
                    CHANNEL_BUS.publish({"type": "calendar_call", "key": live.get("key"), "state": "ended"})
                if STORE.install.get("installed"):
                    CONNECTOR.uninstall("karthi")
                SUBSCRIPTIONS.remove_all("Channel reset.")
                STORE.reset()
                MAIL.reset()
                MEETINGS.reset()
                return self._json(200, {"ok": True})
            if path == "/api/channel/upload":
                import base64 as _b64
                name = (body.get("name") or "").strip()
                try:
                    data = _b64.b64decode(body.get("data") or "")
                except ValueError:
                    data = b""
                if not name or not data:
                    return self._json(400, {"error": "Choose a file to upload."})
                if len(data) > 10 * 1024 * 1024:
                    return self._json(413, {"error": "Files up to 10 MB in the simulator."})
                rec, change = STORE.upload_file("karthi", name, data)
                return self._json(200, {"id": rec["id"], "name": rec["name"], "change": change})
            # ---- tenant admin (Entra admin consent, Teams admin settings) ----
            if path == "/api/admin":
                perms = IDENTITY.registration.get("applicationPermissions", [])
                changes = {}
                if "consent" in body:
                    changes["consented"] = list(perms) if body["consent"] else []
                for k in ("accessPolicy", "transcriptApiAccess", "siteGrant"):
                    if k in body:
                        changes[k] = bool(body[k])
                STORE.set_admin(**changes)
                return self._json(200, admin_view())
            if path == "/api/admin/remove-subscriptions":
                n = SUBSCRIPTIONS.remove_all("Removed by the admin (simulated).")
                return self._json(200, {"removed": n, **admin_view()})
        except KeyError:
            return self._json(404, {"error": "That thread no longer exists."})
        except (RuntimeError, ValueError) as e:
            return self._json(409, {"error": str(e)})
        except (llm.LLMError, voices.TTSError) as e:
            return self._json(502, {"error": str(e)})
        return self._json(404, {"error": "Not found"})

    def do_PUT(self):
        if not self._fake_microsoft("PUT", self._raw_body()):
            self._json(404, {"error": "Not found"})

    def do_PATCH(self):
        if not self._fake_microsoft("PATCH", self._raw_body()):
            self._json(404, {"error": "Not found"})

    def do_DELETE(self):
        if not self._fake_microsoft("DELETE", self._raw_body()):
            self._json(404, {"error": "Not found"})


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server.daemon_threads = True
    threading.Thread(target=llm.qwen_warmup, daemon=True).start()
    print(f"rmeet-ai running at {BASE_URL}")
    print(f"Brain (colleagues): {llm.BRAIN_MODEL} ({'ready' if llm.brain_ready() else 'NOT configured'})")
    print(f"Max: {max_models()['maxBrain']} (thinks + hears) · voices: {max_models()['voices']}")
    print(f"Hearing (your mic): {llm.GEMINI_MODEL} ({'ready' if llm.GEMINI_KEY else 'NOT configured'})")
    reg = IDENTITY.registration
    print(f"Max app registration: {reg.get('appId', 'NONE (run simulations/teams/register_app.py)')}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
