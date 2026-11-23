"""
Voices for the simulated people.

TTS_PROVIDER=gemini (default): Gemini TTS (gemini-3.8-flash-lite-tts).
TTS_PROVIDER=local: any local voice server at LOCAL_TTS_URL with this contract:
  POST /tts {"text", "voice", "style"} -> audio/wav ;  GET /voices -> {name: description}

Each person has a voice name (team.yaml `voice`; a local server maps it to its own voices),
and every line can carry a speaking style (from the agent's emotion/style). Audio is cached on disk by
(provider, voice, style, text) so reruns and auditions don't work twice.
Returns 24 kHz WAV bytes; simulations/teams/audio.py converts to 16 kHz Teams frames.
"""

import base64
import hashlib
import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path

import llm  # noqa: F401  (loads keys)

TTS_PROVIDER = os.environ.get("TTS_PROVIDER", "gemini").strip().lower()
LOCAL_TTS_URL = os.environ.get("LOCAL_TTS_URL", "http://127.0.0.1:8400").rstrip("/")
GEMINI_TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-3.8-flash-lite-tts")
TTS_MODEL = f"local voice server ({LOCAL_TTS_URL})" if TTS_PROVIDER == "local" else GEMINI_TTS_MODEL
BASE =os.environ.get("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
CACHE = Path(__file__).resolve().parent / ".tts_cache"

# Candidate voices for the audition page (Gemini provider): Gemini's own one-word descriptions.
# With the local provider the list comes from the voice server (candidates()).
CANDIDATES = {
    "Charon": "Informative", "Orus": "Firm", "Sadaltager": "Knowledgeable", "Iapetus": "Clear",
    "Schedar": "Even", "Achird": "Friendly", "Umbriel": "Easy-going", "Puck": "Upbeat",
    "Sadachbia": "Lively", "Alnilam": "Firm", "Gacrux": "Mature", "Algenib": "Gravelly",
    "Rasalgethi": "Informative", "Zubenelgenubi": "Casual", "Enceladus": "Breathy",
}

EMOTION_STYLE = {
    "happy": "warm and pleased", "surprised": "surprised, a bit higher energy", "thinking": "thoughtful, measured",
    "confused": "slightly puzzled", "wink": "playful", "idle": "natural, conversational",
}


class TTSError(Exception):
    pass


# Quota guard: after a 429 "quota exceeded", don't hammer Gemini (each retry costs seconds of dead air).
# Pause TTS until Google's retryDelay has passed; callers fall back (browser voice / text) instantly.
_cooldown_until = 0.0


def _retry_delay(body: str) -> float:
    m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', body)
    return min(300.0, float(m.group(1))) if m else 60.0


def cooldown_left() -> float:
    return max(0.0, _cooldown_until - time.time())


def local_voices() -> dict:
    """{name: description} from the local voice server (empty if it isn't running)."""
    try:
        with urllib.request.urlopen(f"{LOCAL_TTS_URL}/voices", timeout=3) as r:
            return json.load(r)
    except (OSError, ValueError):
        return {}


def candidates() -> dict:
    return local_voices() if TTS_PROVIDER == "local" else CANDIDATES


def _local(text: str, voice: str, style: str | None, timeout: float) -> bytes:
    req = urllib.request.Request(f"{LOCAL_TTS_URL}/tts", method="POST",
                                 data=json.dumps({"text": text, "voice": voice, "style": style or ""}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            wav = r.read()
    except urllib.error.HTTPError as e:
        raise TTSError(f"local voice server: HTTP {e.code} {e.read().decode('utf-8', 'replace')[:160]}")
    except (OSError, socket.timeout) as e:
        raise TTSError(f"local voice server not reachable at {LOCAL_TTS_URL}: {e}")
    if wav[:4] != b"RIFF":
        raise TTSError("local voice server did not return WAV audio")
    return wav


def synthesize(text: str, voice: str, style: str | None = None, timeout: float = 15) -> bytes:
    h = hashlib.sha1(f"{TTS_MODEL}|{voice}|{style}|{text}".encode()).hexdigest()
    cached = CACHE / f"{h}.wav"
    if cached.exists():
        return cached.read_bytes()
    if TTS_PROVIDER == "local":
        wav = _local(text, voice, style, timeout)
        CACHE.mkdir(exist_ok=True)
        cached.write_bytes(wav)
        return wav
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise TTSError("GEMINI_API_KEY is not set")
    if cooldown_left():
        raise TTSError(f"Gemini TTS quota reached; voices resume in {cooldown_left():.0f}s")
    part = {"text": text}
    if style:
        part["speechMetadata"] = {"style": style}
    body = json.dumps({"contents": [{"role": "user", "parts": [part]}],
                       "generationConfig": {"responseModalities": ["AUDIO"],
                                            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}).encode()
    last = "unknown"
    for attempt in range(3):
        try:
            data = llm.meter.post(f"{BASE}/models/{GEMINI_TTS_MODEL}:generateContent", body, key,
                                  GEMINI_TTS_MODEL, "tts", "rmeet", timeout)
            parts = data["candidates"][0]["content"]["parts"]
            b64 = next(p["inlineData"]["data"] for p in parts if "inlineData" in p)
            wav = base64.b64decode(b64)
            if wav[:4] != b"RIFF":
                raise TTSError("TTS did not return WAV audio")
            CACHE.mkdir(exist_ok=True)
            cached.write_bytes(wav)
            return wav
        except llm.meter.Blocked as b:
            raise TTSError(f"Gemini TTS not called: {b}")
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", "replace")
            last = f"HTTP {e.code}: {err[:160]}"
            if e.code == 429:  # quota or rate limit: retrying only burns more quota
                global _cooldown_until
                _cooldown_until = time.time() + _retry_delay(err)
                raise TTSError(f"Gemini TTS quota reached; voices resume in {cooldown_left():.0f}s")
            if e.code not in (429, 500, 502, 503, 504):
                break
            time.sleep(2 * (attempt + 1))
        except (TimeoutError, socket.timeout, urllib.error.URLError) as e:
            last = f"timeout/network: {e}"
        except (KeyError, IndexError, StopIteration, ValueError) as e:
            last = f"unexpected response: {e}"
    raise TTSError(f"Gemini TTS failed: {last}")
