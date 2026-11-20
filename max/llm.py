"""
Max's model clients.
- Qwen (company gateway, OpenAI-compatible): thinking, answers, notes. Thinking mode
  is off (1.5-2s replies); each try is capped and retried (the gateway sometimes hangs).
- Gemini: reserved for hearing/voice (speech-to-text, text-to-speech) in later phases.
"""

import json
import os
import socket
import time
import urllib.error
import urllib.request

import config  # noqa: F401  (loads max/.env)

QWEN_KEY = os.environ.get("TW_API_KEY", "").strip()
QWEN_BASE = os.environ.get("TW_BASE_URL", "").strip().rstrip("/")
QWEN_MODEL = os.environ.get("TW_MODEL", "unsloth/Qwen3.8-27B-NVFP4").strip()
MAX_ATTEMPTS = 3


class LLMError(Exception):
    pass


def qwen_chat(messages: list, max_tokens: int = 300, temperature: float = 0.5, timeout: float = 12) -> str:
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
