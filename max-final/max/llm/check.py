"""
Live check with the real settings (python run.py check). Costs a fraction of a cent.

1. Settings and limits load (key present, never shown)
2. Main and backup model each answer; time taken; the provider still offers each model
3. Fallback drill: a broken main model must fall back to the backup automatically
4. Gemini only: the same main model through Gemini's OpenAI-style door, which proves the second backend for real
5. Today's AI usage so far
Exit code 0 = all good, 1 = something failed.
"""

from __future__ import annotations

import asyncio
import sys

from ai_usage import Meter

from ..config import GEMINI_OPENAI_URL, ConfigError, load_settings
from ..log import setup_logging
from .backends import make_backend
from .client import LLM, LLMError
from .openai_compat import OpenAICompatBackend

PROMPT = "Reply with exactly one word: OK"


def line(ok: bool | None, text: str) -> None:
    tag = {True: "PASS", False: "FAIL", None: "NOTE"}[ok]
    print(f"  {tag}  {text}", flush=True)


async def offered(backend, model: str) -> str:
    """Is the model still offered by the provider? (a note, not a failure)"""
    try:
        if hasattr(backend, "model_info"):
            info = await backend.model_info(model)
            return f"offered · takes up to {info['input_tokens']:,} tokens in, {info['output_tokens']:,} out"
        if hasattr(backend, "model_listed"):
            return "offered" if await backend.model_listed(model) else "NOT in the provider's model list"
    except Exception as e:  # nice to have; the answer is what counts
        return f"offer unknown ({type(e).__name__})"
    return "offer unknown"


async def run() -> int:
    print("Max live check\n")
    try:
        s = load_settings()
    except ConfigError as e:
        line(False, str(e))
        return 1
    key = s.llm_api_key.get_secret_value() if s.llm_api_key else None
    setup_logging("check", s.data_dir, s.log_level, secrets=[key] if key else [],
                  console_level="ERROR")  # details go to data/logs/check.log
    meter = Meter()  # the project-wide usage folder, same as the dashboard
    store = meter.limits_store
    line(True, f"settings loaded · provider={s.llm_provider} · key {'set (hidden)' if key else 'none'}"
               f" · main={s.llm_model} · backup={s.llm_fallback_model or '(none)'}")
    budget = store.get().ai.daily_budget_usd          # read first, so a problem in the file is known
    line(store.problem is None, f"limits file: {store.problem or 'OK'} (daily budget ${budget:.2f})")
    failures = 0 if store.problem is None else 1

    backend = make_backend(s)
    llm = LLM.from_settings(s, meter=meter, backend=backend, source="check")

    for role, model in (("main", s.llm_model), ("backup", s.llm_fallback_model)):
        if not model:
            continue
        note = await offered(backend, model)
        try:
            r = await llm.ask(PROMPT, kind="check", models=[model], max_output_tokens=200)
            line(True, f"{role} {model}: answered {r.text.strip()[:20]!r} in {r.ms / 1000:.1f}s · {note}")
        except LLMError as e:
            failures += 1
            line(False, f"{role} {model}: {e}")
        if "NOT" in note:
            line(None, f"{model} is no longer offered: time to pick another model (Karthi decides)")

    if s.llm_fallback_model:
        try:
            r = await llm.ask(PROMPT, kind="check", models=["model-that-does-not-exist", s.llm_fallback_model],
                              max_output_tokens=200)
            ok = r.used_fallback and r.model == s.llm_fallback_model
            failures += 0 if ok else 1
            line(ok, f"fallback drill: broken main model -> {r.model} answered in {r.ms / 1000:.1f}s"
                     f" (attempts: {r.attempts})")
        except LLMError as e:
            failures += 1
            line(False, f"fallback drill: {e}")

    if s.llm_provider == "gemini":
        door = OpenAICompatBackend(GEMINI_OPENAI_URL, key)
        llm2 = LLM(door, meter, [s.llm_model], limits=store, source="check")
        note = await offered(door, s.llm_model)
        try:
            r = await llm2.ask(PROMPT, kind="check", max_output_tokens=200)
            line(True, f"OpenAI-style backend (Gemini's door) {s.llm_model}: answered {r.text.strip()[:20]!r}"
                       f" in {r.ms / 1000:.1f}s · {note}")
        except LLMError as e:
            failures += 1
            line(False, f"OpenAI-style backend (Gemini's door): {e}")

    t = meter.today_totals()
    lim = meter.limits()
    print(f"\n  AI usage today: {t['requests']} calls, ${t['cost']:.5f} of ${lim['daily_usd']:.2f} daily budget"
          f"{' (PAUSED)' if meter.paused() else ''}")
    print(f"\n{'All checks passed.' if failures == 0 else f'{failures} check(s) failed.'}")
    return 0 if failures == 0 else 1


def main() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
