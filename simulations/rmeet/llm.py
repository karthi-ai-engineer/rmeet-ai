"""
Model clients for rmeet-ai.

- Qwen (company gateway, OpenAI-compatible): agents' dialogue, Max's answers, summary.
  Thinking is switched off (1.5-2s replies instead of 5-6s); each try is capped
  and retried because the gateway occasionally hangs.
- Gemini: only for hearing the user's microphone (speech -> text), because Qwen
  cannot take audio.

Keys are read from <project>/.env, then <project>/voice-chat/.env.
"""

import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env(PROJECT / ".env")
_load_env(PROJECT / "voice-chat" / ".env")

QWEN_KEY = os.environ.get("TW_API_KEY", "").strip()
QWEN_BASE = os.environ.get("TW_BASE_URL", "").strip().rstrip("/")
QWEN_MODEL = os.environ.get("TW_MODEL", "unsloth/Qwen3.8-27B-NVFP4").strip()

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
GEMINI_BASE = os.environ.get("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")

ATTEMPT_TIMEOUT = 20  # seconds per try
MAX_ATTEMPTS = 3


class LLMError(Exception):
    pass


def _post_json(url: str, body: dict, headers: dict, label: str, timeout: float = ATTEMPT_TIMEOUT) -> dict:
    data = json.dumps(body).encode("utf-8")
    last_err = "unknown error"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}"
            if e.code in (429, 500, 502, 503, 504) and attempt < MAX_ATTEMPTS:
                time.sleep(1.5 * attempt)
                continue
            raise LLMError(f"{label} {last_err}")
        except (TimeoutError, socket.timeout):
            last_err = f"no answer within {timeout}s"
        except urllib.error.URLError as e:
            if isinstance(e.reason, (TimeoutError, socket.timeout)):
                last_err = f"no answer within {timeout}s"
            else:
                raise LLMError(f"{label} unreachable: {e.reason}")
        print(f"[llm] {label} attempt {attempt} failed ({last_err}), retrying...")
    raise LLMError(f"{label} failed after {MAX_ATTEMPTS} tries: {last_err}")


def qwen_warmup() -> None:
    """Tiny request to wake the gateway; its first call after idle often hangs."""
    try:
        qwen_chat([{"role": "user", "content": "Say OK."}], max_tokens=5, temperature=0, timeout=12)
    except LLMError:
        pass


def qwen_chat(messages: list, max_tokens: int = 300, temperature: float = 0.7, timeout: float = 12) -> str:
    """Return the assistant text from Qwen (thinking disabled).

    timeout is per try: short for quick lines, longer for big prompts (Max reads ~10K tokens)."""
    if not (QWEN_KEY and QWEN_BASE):
        raise LLMError("Qwen is not configured: set TW_API_KEY and TW_BASE_URL in voice-chat/.env")
    body = {
        "model": QWEN_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    data = _post_json(f"{QWEN_BASE}/chat/completions", body,
                      {"Authorization": f"Bearer {QWEN_KEY}", "Content-Type": "application/json"}, "Qwen", timeout)
    try:
        text = data["choices"][0]["message"].get("content") or ""
    except (KeyError, IndexError):
        raise LLMError(f"Qwen returned an unexpected response: {str(data)[:200]}")
    # Safety: strip any leaked <think> block
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    return text.strip()


def parse_json(text: str) -> dict:
    """Parse a JSON object from model output, tolerating fences or extra text."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
    try:
        v = json.loads(t)
        return v if isinstance(v, dict) else {}
    except ValueError:
        s, e = t.find("{"), t.rfind("}")
        if s != -1 and e > s:
            try:
                v = json.loads(t[s:e + 1])
                return v if isinstance(v, dict) else {}
            except ValueError:
                return {}
    return {}


def gemini_transcribe(audio_b64: str, mime: str = "audio/wav") -> str:
    """Speech -> text with Gemini (used only for the user's microphone)."""
    if not GEMINI_KEY:
        raise LLMError("Gemini is not configured: set GEMINI_API_KEY in voice-chat/.env")
    body = {
        "contents": [{"role": "user", "parts": [
            {"inlineData": {"mimeType": mime, "data": audio_b64}},
            {"text": "Transcribe exactly what is said in this audio, in the spoken language. "
                     "Return only the transcript text, nothing else. If there is no speech, return an empty string."},
        ]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 400},
    }
    url = f"{GEMINI_BASE}/models/{urllib.parse.quote(GEMINI_MODEL)}:generateContent"
    data = _post_json(url, body, {"Content-Type": "application/json", "x-goog-api-key": GEMINI_KEY}, "Gemini")
    parts = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts if not p.get("thought")).strip().strip('"')
