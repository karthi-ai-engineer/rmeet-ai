"""
Max's voice and hearing (Gemini).
  speak  : text -> WAV (gemini-3.8-flash-lite-tts, voice MAX_VOICE, default 'Charon': male, informative)
  listen : 16 kHz PCM speech segment -> text (Gemini speech-to-text)
Each try is capped and retried: the free tier sometimes stalls on the first call.
"""

import base64
import json
import os
import socket
import time
import urllib.error
import urllib.request

import config  # noqa: F401  (loads max/.env)
from audio import pcm_to_wav

BASE = os.environ.get("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-3.8-flash-lite-tts")
STT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
VOICE = os.environ.get("MAX_VOICE", "Charon")
STYLE = "warm, clear and helpful, like a calm colleague"


class VoiceError(Exception):
    pass


def _post(url: str, body: dict, timeout: float) -> dict:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise VoiceError("GEMINI_API_KEY is not set in max/.env")
    data = json.dumps(body).encode()
    last = "unknown"
    for attempt in range(3):
        req = urllib.request.Request(url, data=data, method="POST",
                                     headers={"Content-Type": "application/json", "x-goog-api-key": key})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:160]}"
            if e.code not in (429, 500, 502, 503, 504):
                break
            time.sleep(2 * (attempt + 1))
        except (TimeoutError, socket.timeout, urllib.error.URLError) as e:
            last = f"timeout/network: {e}"
    raise VoiceError(last)


def speak(text: str) -> bytes:
    body = {"contents": [{"role": "user", "parts": [{"text": text, "speechMetadata": {"style": STYLE}}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}}}}
    data = _post(f"{BASE}/models/{TTS_MODEL}:generateContent", body, timeout=15)
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
    data = _post(f"{BASE}/models/{STT_MODEL}:generateContent", body, timeout=12)
    parts = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts).strip().strip('"')
