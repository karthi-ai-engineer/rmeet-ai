"""
Live check with the real key (python run.py check). Costs a fraction of a cent.

1. Settings load (key present, never shown)
2. Main and backup model each answer; time taken; how much text each can take at once
3. Fallback drill: a broken main model must fall back to the backup automatically
4. Today's Gemini cost so far
Exit code 0 = all good, 1 = something failed.
"""

from __future__ import annotations

import asyncio
import sys

from gemini_cost import Meter

from ..config import ConfigError, load_settings
from ..log import setup_logging
from .client import LLM, LLMError
from .gemini import GeminiBackend

PROMPT = "Reply with exactly one word: OK"


def line(ok: bool, text: str) -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {text}", flush=True)


async def run() -> int:
    print("Max live check\n")
    try:
        s = load_settings()
    except ConfigError as e:
        line(False, str(e))
        return 1
    setup_logging("check", s.data_dir, s.log_level, secrets=[s.gemini_api_key.get_secret_value()],
                  console_level="ERROR")  # details go to data/logs/check.log
    line(True, f"settings loaded (GEMINI_API_KEY set, hidden) · main={s.gemini_model} · backup={s.gemini_fallback_model}")

    backend = GeminiBackend(s.gemini_api_key.get_secret_value())
    meter = Meter()  # the project-wide cost folder, same as the dashboard
    llm = LLM.from_settings(s, meter=meter, backend=backend, source="check")
    failures = 0

    for role, model in (("main", s.gemini_model), ("backup", s.gemini_fallback_model)):
        try:
            info = await backend.model_info(model)
            size = f"takes up to {info['input_tokens']:,} tokens in, {info['output_tokens']:,} out"
        except Exception as e:  # info is nice to have; the answer below is what counts
            size = f"size unknown ({type(e).__name__})"
        try:
            r = await llm.ask(PROMPT, kind="check", models=[model], max_output_tokens=200)
            line(True, f"{role} {model}: answered {r.text.strip()[:20]!r} in {r.ms / 1000:.1f}s · {size}")
        except LLMError as e:
            failures += 1
            line(False, f"{role} {model}: {e}")

    try:
        r = await llm.ask(PROMPT, kind="check", models=["gemini-model-that-does-not-exist", s.gemini_fallback_model],
                          max_output_tokens=200)
        ok = r.used_fallback and r.model == s.gemini_fallback_model
        failures += 0 if ok else 1
        line(ok, f"fallback drill: broken main model -> {r.model} answered in {r.ms / 1000:.1f}s"
                 f" (attempts: {r.attempts})")
    except LLMError as e:
        failures += 1
        line(False, f"fallback drill: {e}")

    t = meter.today_totals()
    lim = meter.limits()
    print(f"\n  Gemini today: {t['requests']} calls, ${t['cost']:.5f} of ${lim['daily_usd']:.2f} daily cap"
          f"{' (PAUSED)' if meter.paused() else ''}")
    print(f"\n{'All checks passed.' if failures == 0 else f'{failures} check(s) failed.'}")
    return 0 if failures == 0 else 1


def main() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
