"""
The one model adapter for the agent: `ChatHandle.ainvoke(messages, tools)` -> AIMessage (text or tool calls).

Which model runs is configuration (max/.env, copied from voice-chat/.env), as everywhere else in Max:
  BRAIN_PROVIDER=gemini -> langchain-google-genai, GEMINI_BRAIN_MODEL, thinking "minimal"
  otherwise             -> the company Qwen gateway (OpenAI-compatible), thinking off

Every Gemini call goes through the usage meter when it is installed on this machine (gemini_usage/):
check before (may refuse: BudgetBlocked), record after (status, time, tokens). Library retries are off, so
every attempt is one logged request; a 429 is never retried.

Rule for callers: pass the model's AIMessage back into the history exactly as returned. Never rebuild or
trim it: Gemini 3 needs its thought signatures (kept in additional_kwargs) on the next call, or it fails.
"""

import re
import time
from dataclasses import dataclass
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage

import llm  # Max's model settings (provider, model ids, keys) and the optional Gemini meter


class BudgetBlocked(Exception):
    """The Gemini usage meter refused the call (paused, or a request / $ limit reached)."""


class ModelError(Exception):
    """The model call failed. `status` is the HTTP status when known (0 = network/timeout/unknown)."""

    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status}: {message}" if status else message)
        self.status = status


def usage_for_meter(msg: AIMessage) -> dict:
    """LangChain usage_metadata -> the Gemini usageMetadata field names the meter logs.
    langchain-google-genai counts thinking tokens inside output_tokens; the meter wants them apart."""
    u = getattr(msg, "usage_metadata", None) or {}
    reasoning = (u.get("output_token_details") or {}).get("reasoning", 0) or 0
    return {
        "promptTokenCount": u.get("input_tokens", 0) or 0,
        "candidatesTokenCount": max(0, (u.get("output_tokens", 0) or 0) - reasoning),
        "thoughtsTokenCount": reasoning,
        "cachedContentTokenCount": (u.get("input_token_details") or {}).get("cache_read", 0) or 0,
        "totalTokenCount": u.get("total_tokens", 0) or 0,
    }


def estimate_cost(model_id: str, msg: AIMessage) -> float:
    """Paid-tier $ of one reply (gemini_usage/prices.py when installed on this machine, else 0)."""
    try:
        from gemini_usage import prices
    except ImportError:
        return 0.0
    u = usage_for_meter(msg)
    return prices.cost_usd({"model": model_id, "in": u["promptTokenCount"], "out": u["candidatesTokenCount"],
                            "think": u["thoughtsTokenCount"], "cached": u["cachedContentTokenCount"]}) or 0.0


def _status(e: Exception) -> int:
    for attr in ("code", "status_code", "status"):
        v = getattr(e, attr, None)
        if isinstance(v, int) and 100 <= v < 600:
            return v
    resp = getattr(e, "response", None)
    if isinstance(getattr(resp, "status_code", None), int):
        return resp.status_code
    m = re.search(r"\b([45]\d\d)\b", str(e))
    return int(m.group(1)) if m else 0


@dataclass
class ChatHandle:
    model: BaseChatModel
    model_id: str
    provider: str
    meter: Any = None          # gemini_usage.meter, or None = not metered (Qwen, tests)
    source: str = "max"        # shown per program on the usage dashboard

    async def ainvoke(self, messages: list[BaseMessage], tools: list | None = None, kind: str = "agent") -> AIMessage:
        bound = self.model.bind_tools(tools) if tools else self.model
        if self.meter is not None:
            try:
                self.meter.check(self.model_id, self.source)
            except self.meter.Blocked as b:
                raise BudgetBlocked(str(b)) from None
        t0 = time.perf_counter()
        try:
            msg = await bound.ainvoke(messages)
        except Exception as e:
            status = _status(e)
            self._record(kind, status, t0, note=f"{type(e).__name__}: {e}")
            raise ModelError(status, f"{self.model_id}: {type(e).__name__}: {str(e)[:300]}") from e
        self._record(kind, 200, t0, usage_for_meter(msg))
        return msg

    def _record(self, kind: str, status: int, t0: float, usage: dict | None = None, note: str = "") -> None:
        if self.meter is not None:
            self.meter.record(self.model_id, kind, self.source, status, int((time.perf_counter() - t0) * 1000),
                              usage, note)


def make_chat_handle(provider: str | None = None, temperature: float = 0.3, source: str = "max",
                     timeout: float = 60) -> ChatHandle:
    """The configured brain model as a ChatHandle (Gemini on BRAIN_PROVIDER=gemini, else Qwen)."""
    provider = (provider or llm.BRAIN_PROVIDER or "qwen").lower()
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        if not llm.GEMINI_KEY:
            raise ModelError(0, "GEMINI_API_KEY is not set in max/.env")
        model = ChatGoogleGenerativeAI(model=llm.GEMINI_BRAIN_MODEL, api_key=llm.GEMINI_KEY, temperature=temperature,
                                       thinking_level="minimal", max_retries=0, timeout=timeout)
        meter = llm.meter if hasattr(llm.meter, "check") else None   # no meter installed: not metered
        return ChatHandle(model, llm.GEMINI_BRAIN_MODEL, "gemini", meter, source)
    from langchain_openai import ChatOpenAI
    if not (llm.QWEN_KEY and llm.QWEN_BASE):
        raise ModelError(0, "Qwen is not configured: set TW_API_KEY and TW_BASE_URL in max/.env")
    model = ChatOpenAI(model=llm.QWEN_MODEL, base_url=llm.QWEN_BASE, api_key=llm.QWEN_KEY, temperature=temperature,
                       max_retries=0, timeout=timeout,
                       extra_body={"chat_template_kwargs": {"enable_thinking": False}})
    return ChatHandle(model, llm.QWEN_MODEL, "qwen", None, source)
