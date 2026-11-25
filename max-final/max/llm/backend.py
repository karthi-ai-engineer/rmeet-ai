"""
What every model provider must offer, so the rest of Max doesn't care which one is used.
Gemini is the only one now (gemini.py). Tests use a fake one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Result:
    text: str
    usage: dict = field(default_factory=dict)  # token counts: in, out, think, cached, audio_in


class BackendError(Exception):
    """A model call failed.

    kind: timeout | network | rate_limit | server | bad_request | auth | not_found
    status: HTTP status (0 when there was no answer)
    retry_after: seconds the provider asked us to wait (rate limits), if it said
    """

    def __init__(self, kind: str, status: int = 0, retry_after: float | None = None, note: str = ""):
        super().__init__(f"{kind} ({status}) {note}".strip())
        self.kind, self.status, self.retry_after, self.note = kind, status, retry_after, note


class Backend(Protocol):
    async def generate(self, model: str, prompt: str, system: str | None,
                       max_output_tokens: int | None, timeout_s: float) -> Result: ...
