"""
Voices for the simulated people (Gemini TTS, gemini-3.8-flash-lite-tts).

Each person has a prebuilt Gemini voice (team.yaml `voice`), and every line can carry a
speaking style (from the agent's emotion/style). Audio is cached on disk by
(voice, style, text) so reruns and auditions don't spend quota twice.
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

TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-3.8-flash-lite-tts")
BASE = os.environ.get("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
CACHE = Path(__file__).resolve().parent / ".tts_cache"

# Candidate voices for the audition page: Gemini's own one-word descriptions.
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


def synthesize(text: str, voice: str, style: str | None = None, timeout: float = 15) -> bytes:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise TTSError("GEMINI_API_KEY is not set")
    h = hashlib.sha1(f"{TTS_MODEL}|{voice}|{style}|{text}".encode()).hexdigest()
    cached = CACHE / f"{h}.wav"
    if cached.exists():
        return cached.read_bytes()
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
        req = urllib.request.Request(f"{BASE}/models/{TTS_MODEL}:generateContent", data=body, method="POST",
                                     headers={"Content-Type": "application/json", "x-goog-api-key": key})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.load(r)
            parts = data["candidates"][0]["content"]["parts"]
            b64 = next(p["inlineData"]["data"] for p in parts if "inlineData" in p)
            wav = base64.b64decode(b64)
            if wav[:4] != b"RIFF":
                raise TTSError("TTS did not return WAV audio")
            CACHE.mkdir(exist_ok=True)
            cached.write_bytes(wav)
            return wav
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", "replace")
            last = f"HTTP {e.code}: {err[:160]}"
            if e.code == 429 and ("quota" in err.lower() or "RESOURCE_EXHAUSTED" in err):
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
