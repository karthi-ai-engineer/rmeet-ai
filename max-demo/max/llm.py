"""
Max's model clients.
- Qwen (company gateway, OpenAI-compatible): thinking, answers, notes. Thinking mode
  is off (1.5-2s replies); each try is capped and retried (the gateway sometimes hangs).
- Gemini: hearing/voice (speech-to-text, text-to-speech, see voice.py).
- BRAIN_PROVIDER=gemini (temporary, per machine): qwen_chat() is answered by Gemini
  (GEMINI_BRAIN_MODEL). All Gemini calls go through gemini_usage/meter.py (log + budget guard).
"""

import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import config  # noqa: F401  (loads max/.env)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:  # optional, per machine: Gemini usage log + budget guard (gemini_usage/meter.py)
    from gemini_usage import meter  # noqa: E402
except ImportError:
    class meter:  # noqa: N801  (no meter installed: send Gemini calls directly)
        class Blocked(Exception):
            pass

        @staticmethod
        def post(url: str, body: bytes, key: str, model: str, kind: str, source: str, timeout: float) -> dict:
            req = urllib.request.Request(url, data=body, method="POST",
                                         headers={"Content-Type": "application/json", "x-goog-api-key": key})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)

QWEN_KEY = os.environ.get("TW_API_KEY", "").strip()
QWEN_BASE = os.environ.get("TW_BASE_URL", "").strip().rstrip("/")
QWEN_MODEL = os.environ.get("TW_MODEL", "unsloth/Qwen3.8-27B-NVFP4").strip()
MAX_ATTEMPTS = 3

BRAIN_PROVIDER = os.environ.get("BRAIN_PROVIDER", "qwen").strip().lower()
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_BASE = os.environ.get("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
# Cheapest current text model (see gemini_usage/prices.py); its free quota is separate from hearing's.
GEMINI_BRAIN_MODEL = os.environ.get("GEMINI_BRAIN_MODEL", "gemini-3.1-flash-lite").strip()
# Meeting notes are written once per meeting and must be precise: optionally a stronger model (same cost class).
GEMINI_NOTES_MODEL = os.environ.get("GEMINI_NOTES_MODEL", "").strip() or GEMINI_BRAIN_MODEL


class LLMError(Exception):
    pass


def qwen_chat(messages: list, max_tokens: int = 300, temperature: float = 0.5, timeout: float = 12,
              purpose: str = "brain") -> str:
    """purpose='notes' uses GEMINI_NOTES_MODEL on the Gemini brain (Qwen: same model for everything)."""
    if BRAIN_PROVIDER == "gemini":
        return gemini_chat(messages, max_tokens, temperature, timeout,
                           model=GEMINI_NOTES_MODEL if purpose == "notes" else GEMINI_BRAIN_MODEL)
    if not (QWEN_KEY and QWEN_BASE):
        raise LLMError("Qwen is not configured: set TW_API_KEY and TW_BASE_URL in max/.env")
    body = json.dumps({"model": QWEN_MODEL, "messages": messages, "max_tokens": max_tokens,
                       "temperature": temperature, "chat_template_kwargs": {"enable_thinking": False}}).encode()
    last = "unknown error"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        req = urllib.request.Request(f"{QWEN_BASE}/chat/completions", data=body, method="POST", headers={
            "Authorization": f"Bearer {QWEN_KEY}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.load(resp)
            text = data["choices"][0]["message"].get("content") or ""
            return (text.split("</think>", 1)[1] if "</think>" in text else text).strip()
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}"
            if e.code not in (429, 500, 502, 503, 504):
                raise LLMError(f"Qwen {last}")
            time.sleep(1.5 * attempt)
        except (TimeoutError, socket.timeout):
            last = f"no answer within {timeout}s"
        except urllib.error.URLError as e:
            if not isinstance(e.reason, (TimeoutError, socket.timeout)):
                raise LLMError(f"Qwen unreachable: {e.reason}")
            last = f"no answer within {timeout}s"
        except (KeyError, IndexError, ValueError):
            last = "unexpected response"
        print(f"[max/llm] Qwen attempt {attempt} failed ({last}), retrying...")
    raise LLMError(f"Qwen failed after {MAX_ATTEMPTS} tries: {last}")


_thinking_ok = True  # drop thinkingConfig once if the model rejects it


def gemini_chat(messages: list, max_tokens: int = 300, temperature: float = 0.5, timeout: float = 20,
                model: str | None = None) -> str:
    """OpenAI-style messages -> Gemini text. A 429 is never retried (it only burns quota)."""
    global _thinking_ok
    model = model or GEMINI_BRAIN_MODEL
    if not GEMINI_KEY:
        raise LLMError("Gemini brain is not configured: set GEMINI_API_KEY in max/.env")
    system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system")
    contents = [{"role": "model" if m.get("role") == "assistant" else "user", "parts": [{"text": m["content"]}]}
                for m in messages if m.get("role") != "system"]
    if not contents:
        contents, system = [{"role": "user", "parts": [{"text": system}]}], ""
    gen = {"maxOutputTokens": max_tokens + 1024, "temperature": temperature}
    url = f"{GEMINI_BASE}/models/{urllib.parse.quote(model)}:generateContent"
    last = "unknown error"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if _thinking_ok:
            gen["thinkingConfig"] = {"thinkingLevel": "minimal"}
        else:
            gen.pop("thinkingConfig", None)
        body = {"contents": contents, "generationConfig": gen}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        try:
            data = meter.post(url, json.dumps(body).encode(), GEMINI_KEY, model, "brain", "max",
                              max(timeout, 20))
            parts = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
            return "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
        except meter.Blocked as b:
            raise LLMError(f"Gemini brain not called: {b}")
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", "replace")
            last = f"HTTP {e.code}: {err[:200]}"
            if e.code == 400 and _thinking_ok and "thinking" in err.lower():
                _thinking_ok = False
                continue
            if e.code not in (500, 502, 503, 504):
                raise LLMError(f"Gemini brain {last}")
            time.sleep(1.5 * attempt)
        except (TimeoutError, socket.timeout, urllib.error.URLError) as e:
            last = f"timeout/network: {e}"
        print(f"[max/llm] Gemini attempt {attempt} failed ({last}), retrying...")
    raise LLMError(f"Gemini brain failed after {MAX_ATTEMPTS} tries: {last}")


def parse_json(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
    for candidate in (t, t[t.find("{"):t.rfind("}") + 1] if "{" in t else ""):
        try:
            v = json.loads(candidate)
            if isinstance(v, dict):
                return v
        except ValueError:
            continue
    return {}
