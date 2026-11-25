"""Gemini backend: the official google-genai SDK, with its errors turned into our BackendError."""

from __future__ import annotations

import re

import httpx
from google import genai
from google.genai import errors, types

from .backend import BackendError, Result

try:  # the SDK may use httpx or its fork httpx2, depending on what is installed
    import httpx2
    _HTTP_ERRORS: tuple = (httpx.HTTPError, httpx2.HTTPError)
    _TIMEOUTS: tuple = (httpx.TimeoutException, httpx2.TimeoutException)
except ImportError:
    _HTTP_ERRORS = (httpx.HTTPError,)
    _TIMEOUTS = (httpx.TimeoutException,)


def usage_from(meta) -> dict:
    """Token counts from Gemini's usage_metadata, in the meter's format."""
    if meta is None:
        return {}
    audio = sum((d.token_count or 0) for d in (meta.prompt_tokens_details or [])
                if str(getattr(d.modality, "value", d.modality)).upper() == "AUDIO")
    return {"in": meta.prompt_token_count or 0, "out": meta.candidates_token_count or 0,
            "think": meta.thoughts_token_count or 0, "cached": meta.cached_content_token_count or 0,
            "audio_in": audio}


def retry_after_from(details) -> float | None:
    """Google puts the wait time in error.details[].retryDelay, e.g. '31s' or '1.5s'."""
    try:
        err = details.get("error", details) if isinstance(details, dict) else {}
        for d in err.get("details", []) or []:
            delay = d.get("retryDelay") if isinstance(d, dict) else None
            if delay:
                m = re.fullmatch(r"\s*([\d.]+)s\s*", str(delay))
                if m:
                    return float(m.group(1))
    except (AttributeError, TypeError, ValueError):
        pass
    return None


def _bad_key(e: errors.APIError) -> bool:
    """Gemini answers a wrong key with 400 INVALID_ARGUMENT + reason API_KEY_INVALID (checked 25 Nov 2026)."""
    return "API_KEY_INVALID" in str(e.details) or "API key not valid" in (e.message or "")


def convert(e: errors.APIError) -> BackendError:
    code = e.code or 0
    note = (e.message or e.status or "")[:200]
    if code == 429:
        return BackendError("rate_limit", code, retry_after_from(e.details), note)
    if code in (401, 403) or (code == 400 and _bad_key(e)):
        return BackendError("auth", code, note=note)
    if code == 404:
        return BackendError("not_found", code, note=note)
    if code == 408 or code == 504:
        return BackendError("timeout", code, note=note)
    if code >= 500:
        return BackendError("server", code, note=note)
    return BackendError("bad_request", code, note=note)


class GeminiBackend:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    async def generate(self, model: str, prompt: str, system: str | None,
                       max_output_tokens: int | None, timeout_s: float) -> Result:
        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_output_tokens,
            http_options=types.HttpOptions(timeout=int(timeout_s * 1000)),
        )
        try:
            resp = await self.client.aio.models.generate_content(model=model, contents=prompt, config=config)
        except errors.APIError as e:
            raise convert(e) from None
        except _TIMEOUTS:
            raise BackendError("timeout") from None
        except _HTTP_ERRORS as e:
            raise BackendError("network", note=type(e).__name__) from None
        except Exception as e:  # anything else from the SDK (odd responses, bad URLs): never escape as-is
            raise BackendError("unexpected", note=type(e).__name__) from None
        return Result(text=resp.text or "", usage=usage_from(resp.usage_metadata))

    async def model_info(self, model: str) -> dict:
        """Input/output token limits of a model (used by the live check)."""
        m = await self.client.aio.models.get(model=model)
        return {"input_tokens": m.input_token_limit, "output_tokens": m.output_token_limit}
