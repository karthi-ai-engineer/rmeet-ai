"""
AI model prices, USD per 1 million tokens. Edit here when a provider changes them or a new model is used.
Gemini: paid tier (Standard), checked 25 Nov 2026 (aistudio.google.com/docs/pricing).
Company-server and local models cost $0 per token (still counted: calls, tokens, time).
Models not listed are counted at the highest known price, so a budget is never under-counted.
"""

PRICES = {
    #  model                    text in  audio in  cached in  output (incl. thinking)
    "gemini-3.1-flash-lite": {"in": 0.25, "audio_in": 0.50, "cached": 0.025, "out": 1.50},
    "gemini-3.5-flash-lite": {"in": 0.30, "audio_in": 0.30, "cached": 0.03, "out": 2.50},
    "gemini-2.5-flash-lite": {"in": 0.10, "audio_in": 0.30, "cached": 0.01, "out": 0.40},
    # company servers / local models: free per token
    "unsloth/Qwen3.8-27B-NVFP4": {"in": 0.0, "audio_in": 0.0, "cached": 0.0, "out": 0.0},
}

# For models not listed above: the highest known price of each kind, so spend is never under-counted.
WORST_CASE = {k: max(p[k] for p in PRICES.values()) for k in ("in", "audio_in", "cached", "out")}


def price_for(model: str | None) -> dict | None:
    """Exact model id, else the longest known prefix (e.g. 'gemini-3.1-flash-lite-preview')."""
    if not model:
        return None
    if model in PRICES:
        return PRICES[model]
    hits = [k for k in PRICES if model.startswith(k)]
    return PRICES[max(hits, key=len)] if hits else None


def cost_usd(event: dict, worst_case: bool = False) -> float | None:
    """Cost of one logged call (keys: model, in, out, think, cached, audio_in).
    Unknown model: None, or the worst-case estimate if worst_case=True. Failed calls (status != 200) cost 0."""
    if event.get("status", 200) != 200:
        return 0.0
    p = price_for(event.get("model")) or (WORST_CASE if worst_case else None)
    if not p:
        return None
    audio = event.get("audio_in", 0) or 0
    cached = event.get("cached", 0) or 0
    text_in = max(0, (event.get("in", 0) or 0) - audio - cached)
    out = (event.get("out", 0) or 0) + (event.get("think", 0) or 0)
    return (text_in * p["in"] + audio * p["audio_in"] + cached * p["cached"] + out * p["out"]) / 1_000_000
