"""Pick the backend from the settings. The only place that knows which providers exist."""

from __future__ import annotations

from .backend import Backend


def make_backend(settings) -> Backend:
    key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
    if settings.llm_provider == "gemini":
        from .gemini import GeminiBackend
        return GeminiBackend(key)
    if settings.llm_provider == "openai_compatible":
        from .openai_compat import OpenAICompatBackend
        return OpenAICompatBackend(settings.llm_base_url, key, settings.llm_extra_body)
    raise ValueError(f"unknown AI provider: {settings.llm_provider}")
