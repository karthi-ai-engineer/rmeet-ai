"""
The one way Max talks to an AI model.

  llm = LLM.from_settings(settings)
  reply = await llm.ask("question", system="you are Max", kind="brain")

How it stays reliable (see docs/plans/step-0.md):
  main model -> timeout / server error: retry once -> rate limit: short wait or skip -> backup model
  -> all failed: LLMError (callers then say FALLBACK_MESSAGE, so Max never goes silent).
Every attempt goes through the Gemini cost meter (daily cap, pause switch, usage log).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from gemini_cost import Blocked, Meter

from .backend import Backend, BackendError

log = logging.getLogger("max.llm")

FALLBACK_MESSAGE = "Sorry, I can't reach my AI model right now. Please try again in a minute."

RETRY_SAME_MODEL = {"timeout", "network", "server"}   # worth one more try on the same model
SKIP_TO_NEXT = {"not_found", "bad_request", "empty"}  # try the backup straight away
STOP_NOW = {"auth"}                                    # the backup uses the same key: no point
BACKOFF_S = 1.0


@dataclass
class Reply:
    text: str
    model: str
    ms: int
    used_fallback: bool
    attempts: int


class LLMError(Exception):
    """No answer. reason: budget | auth | unavailable. The message is safe to log (no secrets, no prompt)."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


class LLM:
    def __init__(self, backend: Backend, meter: Meter, models: list[str], *, timeout_s: float = 20.0,
                 deadline_s: float = 60.0, max_wait_s: float = 5.0, source: str = "max",
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 clock: Callable[[], float] = time.monotonic):
        self.backend, self.meter = backend, meter
        self.models = list(dict.fromkeys(m for m in models if m))  # keep order, drop blanks/duplicates
        if not self.models:
            raise ValueError("LLM needs at least one model")
        self.timeout_s, self.deadline_s, self.max_wait_s = timeout_s, deadline_s, max_wait_s
        self.source, self.sleep, self.clock = source, sleep, clock

    @classmethod
    def from_settings(cls, settings, meter: Meter | None = None, backend: Backend | None = None,
                      source: str = "max") -> LLM:
        if backend is None:
            from .gemini import GeminiBackend
            backend = GeminiBackend(settings.gemini_api_key.get_secret_value())
        # Meter() = the one project-wide cost folder, the same one the dashboard controls
        return cls(backend, meter or Meter(),
                   [settings.gemini_model, settings.gemini_fallback_model],
                   timeout_s=settings.llm_timeout_s, deadline_s=settings.llm_deadline_s,
                   max_wait_s=settings.llm_max_wait_s, source=source)

    async def ask(self, prompt: str, *, system: str | None = None, kind: str = "brain",
                  max_output_tokens: int | None = None, models: list[str] | None = None) -> Reply:
        start = self.clock()
        attempts = 0
        last = "no attempt made"
        for i, model in enumerate(models or self.models):
            for try_no in (1, 2):
                remaining = self.deadline_s - (self.clock() - start)
                if remaining < 1.0:
                    raise LLMError("unavailable", f"no answer within {self.deadline_s:.0f}s (last: {last})")
                try:
                    self.meter.check(model, self.source)
                except Blocked as e:
                    raise LLMError("budget", str(e)) from None

                attempts += 1
                timeout = min(self.timeout_s, remaining)
                t0 = self.clock()
                try:
                    result = await asyncio.wait_for(
                        self.backend.generate(model, prompt, system, max_output_tokens, timeout), timeout)
                    error = None if result.text.strip() else BackendError("empty", 200, note="empty answer")
                except (asyncio.TimeoutError, TimeoutError):
                    result, error = None, BackendError("timeout", note=f"over {timeout:.0f}s")
                except BackendError as e:
                    result, error = None, e
                ms = int((self.clock() - t0) * 1000)

                if error is None:
                    self._record(model, kind, 200, ms, result.usage)
                    return Reply(result.text, model, ms, used_fallback=i > 0, attempts=attempts)

                # Failed: log it (an empty answer was still billed: status 200 keeps its cost)
                self._record(model, kind, 200 if error.kind == "empty" else error.status, ms,
                             result.usage if result else None, f"{error.kind}: {error.note}")
                last = f"{model}: {error.kind} {error.status or ''}".strip()
                log.warning("model call failed: %s (kind=%s, try %d, %d ms)", last, kind, try_no, ms)

                if error.kind in STOP_NOW:
                    raise LLMError("auth", f"Gemini refused the API key ({error.status}). Check GEMINI_API_KEY.")
                if try_no == 2 or error.kind in SKIP_TO_NEXT:
                    break
                if error.kind == "rate_limit":
                    wait = error.retry_after
                    time_left = self.deadline_s - (self.clock() - start)
                    if wait is None or wait > self.max_wait_s or wait > time_left - 2.0:
                        break                      # long wait (or no time for it): use the backup instead
                    await self.sleep(wait)
                elif error.kind in RETRY_SAME_MODEL:
                    await self.sleep(BACKOFF_S)
                else:
                    break
        raise LLMError("unavailable", f"no model answered (last: {last})")

    def _record(self, model: str, kind: str, status: int, ms: int, usage: dict | None, note: str = "") -> None:
        """Log to the cost meter. A logging problem (e.g. disk full) must never lose an answer."""
        try:
            self.meter.record(model, kind, self.source, status, ms, usage, note)
        except OSError as e:
            log.error("could not write the Gemini cost log: %s", e)
