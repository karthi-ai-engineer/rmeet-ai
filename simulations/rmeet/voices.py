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


def synthesize(text: str, voice: str, style: str | None = None, timeout: float = 15) -> bytes:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise TTSError("GEMINI_API_KEY is not set")
    h = hashlib.sha1(f"{TTS_MODEL}|{voice}|{style}|{text}".encode()).hexdigest()
    cached = CACHE / f"{h}.wav"
    if cached.exists():
        return cached.read_bytes()
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
            last = f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:160]}"
            if e.code not in (429, 500, 502, 503, 504):
                break
            time.sleep(2 * (attempt + 1))
        except (TimeoutError, socket.timeout, urllib.error.URLError) as e:
            last = f"timeout/network: {e}"
        except (KeyError, IndexError, StopIteration, ValueError) as e:
            last = f"unexpected response: {e}"
    raise TTSError(f"Gemini TTS failed: {last}")
