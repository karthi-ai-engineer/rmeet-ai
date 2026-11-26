"""
OpenAI-style backend: any server that speaks the OpenAI chat-completions format.
Used for the company Qwen gateway (vLLM), other open models on our own servers, and Gemini's OpenAI door.
Plain httpx (no provider SDK); errors become the same BackendError kinds as the Gemini backend.
"""

from __future__ import annotations

import httpx

from .backend import BackendError, Result


def _message(resp: httpx.Response) -> str:
    """The error text a server sent (Gemini's door wraps it in a list). Never contains our key."""
    try:
        body = resp.json()
    except ValueError:
        return resp.text
    if isinstance(body, list) and body:
        body = body[0]
    if isinstance(body, dict):
        err = body.get("error", body)
        if isinstance(err, dict):
            return str(err.get("message") or err.get("status") or "")
        return str(err)
    return ""


def _retry_after(resp: httpx.Response) -> float | None:
    value = resp.headers.get("retry-after")
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def convert(resp: httpx.Response, secret: str | None) -> BackendError:
    code = resp.status_code
    note = _message(resp)
    if secret:
        note = note.replace(secret, "***")    # hide the key first, then shorten (never cut a key in half)
    note = note[:200]
    if code == 429:
        return BackendError("rate_limit", code, _retry_after(resp), note)
    if code in (401, 403) or (code == 400 and "api key" in note.lower()):
        return BackendError("auth", code, note=note)
    if code == 404:
        return BackendError("not_found", code, note=note)
    if code in (408, 504):
        return BackendError("timeout", code, note=note)
    if code >= 500:
        return BackendError("server", code, note=note)
    return BackendError("bad_request", code, note=note)


def _count(d, key) -> int:
    try:
        return max(0, int((d or {}).get(key) or 0)) if isinstance(d, dict) else 0
    except (TypeError, ValueError):
        return 0


def usage_from(u: dict | None) -> dict:
    """Token counts in the meter's format. In the OpenAI format completion_tokens already INCLUDES reasoning
    tokens, so they are split out here (the meter adds out + think: counting them twice would over-bill)."""
    u = u if isinstance(u, dict) else {}
    think = _count(u.get("completion_tokens_details"), "reasoning_tokens")
    return {"in": _count(u, "prompt_tokens"), "out": max(0, _count(u, "completion_tokens") - think),
            "think": think, "cached": _count(u.get("prompt_tokens_details"), "cached_tokens"),
            "audio_in": _count(u.get("prompt_tokens_details"), "audio_tokens")}


def _text(content) -> str:
    """content is a string, or (allowed in the OpenAI format) a list of parts like {"type": "text", "text": ...}."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return str(content)


class OpenAICompatBackend:
    def __init__(self, base_url: str, api_key: str | None = None, extra_body: dict | None = None,
                 transport: httpx.AsyncBaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or None
        self.extra_body = dict(extra_body or {})
        self.transport = transport          # tests pass a fake server here

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    def _client(self, timeout_s: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=timeout_s, transport=self.transport, headers=self._headers())

    async def generate(self, model: str, prompt: str, system: str | None,
                       max_output_tokens: int | None, timeout_s: float) -> Result:
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        body = {"model": model, "messages": messages, **self.extra_body}
        if max_output_tokens:
            body["max_tokens"] = max_output_tokens
        try:
            async with self._client(timeout_s) as client:
                resp = await client.post(f"{self.base_url}/chat/completions", json=body)
        except httpx.TimeoutException:
            raise BackendError("timeout") from None
        except httpx.HTTPError as e:
            raise BackendError("network", note=type(e).__name__) from None
        except Exception as e:  # bad address, odd library errors: never escape as-is
            raise BackendError("unexpected", note=type(e).__name__) from None
        if resp.status_code != 200:
            raise convert(resp, self.api_key)
        try:
            data = resp.json()
            message = data["choices"][0]["message"]
            text = _text(message.get("content"))
        except Exception:
            raise BackendError("unexpected", 200, note="answer was not in the OpenAI chat format") from None
        return Result(text=text, usage=usage_from(data.get("usage")))

    async def model_listed(self, model: str) -> bool:
        """Does the server offer this model? (used by the live check)"""
        async with self._client(15) as client:
            resp = await client.get(f"{self.base_url}/models")
        if resp.status_code != 200:
            raise convert(resp, self.api_key)
        ids = {str(m.get("id", "")) for m in resp.json().get("data", [])}
        return model in ids or f"models/{model}" in ids
