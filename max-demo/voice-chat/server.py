"""
Voice chat test server (no external packages needed, Python 3.9+).

- Serves the web pages (voice-chat/ and bot-avatar/) on http://localhost:8000
- POST /api/chat : receives recorded audio from the browser, sends it to Gemini,
  returns {transcript, reply, emotion}.

The Gemini API key stays on this server (read from voice-chat/.env) and is never
sent to the browser.

Run:  python voice-chat/server.py
"""

import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
try:  # optional, per machine: Gemini usage log + budget guard (gemini_usage/meter.py)
    from gemini_usage import meter  # noqa: E402
except ImportError:
    class meter:  # noqa: N801  (no meter installed: send Gemini calls directly)
        class Blocked(Exception):
            pass

        @staticmethod
        def post(url, body, key, model, kind, source, timeout):
            req = urllib.request.Request(url, data=body, method="POST",
                                         headers={"Content-Type": "application/json", "x-goog-api-key": key})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
ROOT = HERE.parent  # project root, so both /voice-chat and /bot-avatar are served


def load_env(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE lines, # comments allowed."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env(HERE / ".env")

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
API_BASE = os.environ.get(
    "GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta"
).rstrip("/")
PORT = int(os.environ.get("PORT", "8000"))

MAX_BODY_BYTES = 15 * 1024 * 1024  # base64 audio + history
ATTEMPT_TIMEOUT = float(os.environ.get("GEMINI_ATTEMPT_TIMEOUT", "10"))  # seconds per try
MAX_ATTEMPTS = 3
ALLOWED_MIME = {"audio/wav", "audio/webm", "audio/ogg", "audio/mp3", "audio/mpeg"}
EMOTIONS = ["happy", "surprised", "thinking", "confused", "wink", "sleepy", "idle"]

SYSTEM_PROMPT = f"""You are Max, a friendly AI assistant shown on screen as a cute cloud character.
The user talks to you through their microphone; you receive their voice as audio.

For every audio message:
1. "transcript": write exactly what the user said, in the language they spoke.
   If you hear no clear speech, use an empty string.
2. "reply": answer naturally and briefly (1-3 short sentences). Your reply is shown
   as text on screen, so no markdown, lists or emojis. If there was no clear speech,
   politely say you didn't catch that.
3. "emotion": pick the one that best fits YOUR reply, from: {", ".join(EMOTIONS)}.

Respond with ONLY a JSON object: {{"transcript": "...", "reply": "...", "emotion": "..."}}"""


class GeminiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def friendly_error(status: int, body: str) -> str:
    try:
        msg = json.loads(body).get("error", {}).get("message", "") or body
    except ValueError:
        msg = body
    msg = msg.strip()[:300]
    if status == 429:
        return "Gemini free-tier limit reached. Wait a minute and try again. (" + msg + ")"
    if status in (401, 403) or "API key" in msg:
        return "Gemini rejected the API key. Check GEMINI_API_KEY in voice-chat/.env. (" + msg + ")"
    if status == 404:
        return f"Model '{MODEL}' was not found. Change GEMINI_MODEL in voice-chat/.env. ({msg})"
    return f"Gemini error {status}: {msg}"


def parse_reply(text: str) -> dict:
    """Parse the model's JSON answer; tolerate code fences or stray text."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    try:
        data = json.loads(cleaned)
    except ValueError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        try:
            data = json.loads(cleaned[start:end + 1]) if start != -1 and end > start else {}
        except ValueError:
            data = {}
    if not isinstance(data, dict) or "reply" not in data:
        return {"transcript": "", "reply": text.strip(), "emotion": "idle"}
    emotion = str(data.get("emotion", "idle")).lower().strip()
    return {
        "transcript": str(data.get("transcript", "")).strip(),
        "reply": str(data.get("reply", "")).strip(),
        "emotion": emotion if emotion in EMOTIONS else "idle",
    }


def call_gemini(audio_b64: str, mime: str, history: list) -> dict:
    contents = []
    for turn in history[-10:]:
        if not isinstance(turn, dict):
            continue
        text = str(turn.get("text", ""))[:2000].strip()
        if text:
            role = "user" if turn.get("role") == "user" else "model"
            contents.append({"role": role, "parts": [{"text": text}]})
    contents.append({
        "role": "user",
        "parts": [
            {"inlineData": {"mimeType": mime, "data": audio_b64}},
            {"text": "This audio is what I just said. Reply with the JSON object."},
        ],
    })
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.7,
            "maxOutputTokens": 512,
        },
    }
    url = f"{API_BASE}/models/{urllib.parse.quote(MODEL)}:generateContent"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": API_KEY},
        method="POST",
    )
    # The free tier normally answers in ~2s but now and then a request hangs for
    # ~60s on Google's side. So: wait at most ATTEMPT_TIMEOUT, then resend.
    started = time.perf_counter()
    data = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            data = meter.post(url, req.data, API_KEY, MODEL, "voice-chat", "voice-chat", ATTEMPT_TIMEOUT)
            break
        except meter.Blocked as b:
            raise GeminiError(429, f"Not sent to Gemini: {b}")
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", "replace")
            if e.code in (500, 503) and attempt < MAX_ATTEMPTS:
                print(f"Gemini {e.code} on attempt {attempt}, retrying...")
                continue
            raise GeminiError(e.code, friendly_error(e.code, body_text))
        except (TimeoutError, socket.timeout):
            print(f"Gemini slow (> {ATTEMPT_TIMEOUT}s) on attempt {attempt}, retrying...")
        except urllib.error.URLError as e:
            if isinstance(e.reason, (TimeoutError, socket.timeout)):
                print(f"Gemini slow (> {ATTEMPT_TIMEOUT}s) on attempt {attempt}, retrying...")
                continue
            raise GeminiError(502, f"Could not reach Gemini: {e.reason}")
    if data is None:
        raise GeminiError(504, f"Gemini did not answer after {MAX_ATTEMPTS} tries. Please try again.")
    latency_ms = int((time.perf_counter() - started) * 1000)

    candidates = data.get("candidates") or []
    if not candidates:
        reason = (data.get("promptFeedback") or {}).get("blockReason", "no answer returned")
        raise GeminiError(502, f"Gemini returned no reply ({reason}).")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    if not text.strip():
        raise GeminiError(502, "Gemini returned an empty reply.")

    result = parse_reply(text)
    result["model"] = MODEL
    result["latencyMs"] = latency_ms
    result["usage"] = data.get("usageMetadata", {})
    return result


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
        # Never serve hidden files such as .env
        if any(seg.startswith(".") for seg in path.split("/") if seg):
            self.send_error(404)
            return
        if path in ("", "/"):
            self.send_response(302)
            self.send_header("Location", "/voice-chat/")
            self.end_headers()
            return
        if path == "/api/config":
            self._json(200, {"model": MODEL, "hasKey": bool(API_KEY)})
            return
        super().do_GET()

    def do_POST(self):
        if urllib.parse.urlsplit(self.path).path != "/api/chat":
            self._json(404, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY_BYTES:
            self._json(413, {"error": "Recording is empty or too large."})
            return
        try:
            payload = json.loads(self.rfile.read(length))
        except ValueError:
            self._json(400, {"error": "Invalid JSON."})
            return

        audio = payload.get("audio") or ""
        mime = (payload.get("mimeType") or "audio/wav").split(";")[0].strip().lower()
        history = payload.get("history") or []
        if not audio:
            self._json(400, {"error": "No audio received."})
            return
        if mime not in ALLOWED_MIME:
            self._json(400, {"error": f"Unsupported audio type: {mime}"})
            return
        if not API_KEY:
            self._json(500, {"error": "No API key. Add GEMINI_API_KEY to voice-chat/.env and restart the server."})
            return

        try:
            self._json(200, call_gemini(audio, mime, history if isinstance(history, list) else []))
        except GeminiError as e:
            self.log_message("Gemini error: %s", e.message)
            self._json(e.status if 400 <= e.status < 600 else 502, {"error": e.message})


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Voice chat test running at http://localhost:{PORT}")
    print(f"Model: {MODEL}")
    if not API_KEY:
        print("WARNING: GEMINI_API_KEY is not set. Copy voice-chat/.env.example to voice-chat/.env and add your key.")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()
        sys.exit(0)


if __name__ == "__main__":
    main()
