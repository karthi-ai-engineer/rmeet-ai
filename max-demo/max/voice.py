"""
Max's voice and hearing.
  speak  : text -> WAV, voice MAX_VOICE (default 'Charon').
           TTS_PROVIDER=gemini (default): gemini-3.8-flash-lite-tts.
           TTS_PROVIDER=local: a local voice server at LOCAL_TTS_URL (POST /tts {text, voice, style} -> WAV).
  listen : 16 kHz PCM speech segment -> text (Gemini speech-to-text)
Gemini tries are capped and retried: the free tier sometimes stalls on the first call.
"""

import base64
import json
import os
import re
import socket
import time
import urllib.error
import urllib.request

import config  # noqa: F401  (loads max/.env)
from audio import pcm_to_wav
from llm import meter

BASE = os.environ.get("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-3.8-flash-lite-tts")
STT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
VOICE = os.environ.get("MAX_VOICE", "Charon")
TTS_PROVIDER = os.environ.get("TTS_PROVIDER", "gemini").strip().lower()
LOCAL_TTS_URL = os.environ.get("LOCAL_TTS_URL", "http://127.0.0.1:8400").rstrip("/")
STYLE = "warm, clear and helpful, like a calm colleague"


class VoiceError(Exception):
    pass


# Quota guard per model: after 429 "quota exceeded", pause that model until Google's retryDelay
# has passed, so Max falls back (answers in the meeting chat) immediately instead of stalling.
_cooldown_until: dict[str, float] = {}


def _retry_delay(body: str) -> float:
    m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', body)
    return min(300.0, float(m.group(1))) if m else 60.0


def cooldown_left(model: str) -> float:
    return max(0.0, _cooldown_until.get(model, 0.0) - time.time())


def _post(model: str, body: dict, timeout: float) -> dict:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise VoiceError("GEMINI_API_KEY is not set in max/.env")
    if cooldown_left(model):
        raise VoiceError(f"{model} quota reached; available again in {cooldown_left(model):.0f}s")
    url = f"{BASE}/models/{model}:generateContent"
    data = json.dumps(body).encode()
    last = "unknown"
    for attempt in range(3):
        try:
            return meter.post(url, data, key, model, "tts" if model == TTS_MODEL else "stt", "max", timeout)
        except meter.Blocked as b:
            raise VoiceError(f"{model} not called: {b}")
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", "replace")
            last = f"HTTP {e.code}: {err[:160]}"
            if e.code == 429:  # quota or rate limit: retrying only burns more quota
                _cooldown_until[model] = time.time() + _retry_delay(err)
                raise VoiceError(f"{model} quota reached; available again in {cooldown_left(model):.0f}s")
            if e.code not in (429, 500, 502, 503, 504):
                break
            time.sleep(2 * (attempt + 1))
        except (TimeoutError, socket.timeout, urllib.error.URLError) as e:
            last = f"timeout/network: {e}"
    raise VoiceError(last)


def _speak_local(text: str) -> bytes:
    req = urllib.request.Request(f"{LOCAL_TTS_URL}/tts", method="POST",
                                 data=json.dumps({"text": text, "voice": VOICE, "style": STYLE}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            wav = r.read()
    except urllib.error.HTTPError as e:
        raise VoiceError(f"local voice server: HTTP {e.code} {e.read().decode('utf-8', 'replace')[:160]}")
    except (OSError, socket.timeout) as e:
        raise VoiceError(f"local voice server not reachable at {LOCAL_TTS_URL}: {e}")
    if wav[:4] != b"RIFF":
        raise VoiceError("local voice server did not return WAV audio")
    return wav


def speak(text: str) -> bytes:
    if TTS_PROVIDER == "local":
        return _speak_local(text)
    body ={"contents": [{"role": "user", "parts": [{"text": text, "speechMetadata": {"style": STYLE}}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}}}}
    data = _post(TTS_MODEL, body, timeout=15)
    try:
        parts = data["candidates"][0]["content"]["parts"]
        return base64.b64decode(next(p["inlineData"]["data"] for p in parts if "inlineData" in p))
    except (KeyError, IndexError, StopIteration) as e:
        raise VoiceError(f"no audio in TTS response: {e}")


def listen(pcm16k: bytes, hint: str = "") -> str:
    """Transcribe one speaker's segment. `hint` lists names/terms to improve recognition."""
    body = {"contents": [{"role": "user", "parts": [
        {"inlineData": {"mimeType": "audio/wav", "data": base64.b64encode(pcm_to_wav(pcm16k)).decode()}},
        {"text": "Transcribe exactly what is said, in English. Return only the words spoken, no labels. "
                 "If there is no speech, return an empty string." + (f" Names and terms that may appear: {hint}." if hint else "")},
    ]}], "generationConfig": {"temperature": 0, "maxOutputTokens": 400}}
    data = _post(STT_MODEL, body, timeout=12)
    parts = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts).strip().strip('"')
