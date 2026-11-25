"""Turning Gemini SDK errors and usage into our own format (offline)."""

from types import SimpleNamespace

from google.genai import errors

from max.llm.gemini import convert, retry_after_from, usage_from


def api_error(code, details=None):
    body = {"error": {"code": code, "message": "msg", "status": "STATUS", "details": details or []}}
    return errors.APIError(code, body)


def test_rate_limit_with_retry_delay():
    e = convert(api_error(429, [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "31s"}]))
    assert (e.kind, e.status, e.retry_after) == ("rate_limit", 429, 31.0)


def test_rate_limit_without_delay():
    assert convert(api_error(429)).retry_after is None


def test_error_kinds():
    assert convert(api_error(403)).kind == "auth"
    assert convert(api_error(401)).kind == "auth"
    assert convert(api_error(404)).kind == "not_found"
    assert convert(api_error(400)).kind == "bad_request"
    assert convert(api_error(500)).kind == "server"
    assert convert(api_error(503)).kind == "server"
    assert convert(api_error(504)).kind == "timeout"


def test_retry_after_handles_junk():
    assert retry_after_from(None) is None
    assert retry_after_from({"error": {"details": [{"retryDelay": "soon"}]}}) is None
    assert retry_after_from({"error": {"details": [{"retryDelay": "1.5s"}]}}) == 1.5


def test_usage_counts_audio_and_thinking():
    meta = SimpleNamespace(prompt_token_count=120, candidates_token_count=30, thoughts_token_count=7,
                           cached_content_token_count=None,
                           prompt_tokens_details=[SimpleNamespace(modality="AUDIO", token_count=100),
                                                  SimpleNamespace(modality="TEXT", token_count=20)])
    assert usage_from(meta) == {"in": 120, "out": 30, "think": 7, "cached": 0, "audio_in": 100}
    assert usage_from(None) == {}


def test_invalid_key_is_auth_error():
    # what Gemini really sends for a wrong key (checked live 25 Nov 2026 with a fake key)
    details = [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "API_KEY_INVALID"}]
    body = {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.",
                      "status": "INVALID_ARGUMENT", "details": details}}
    assert convert(errors.APIError(400, body)).kind == "auth"


def test_unexpected_sdk_error_becomes_backend_error(monkeypatch):
    import asyncio

    import pytest

    from max.llm import BackendError
    from max.llm.gemini import GeminiBackend

    b = GeminiBackend("test-key-123456")

    async def boom(**kw):
        raise ValueError("odd response")
    monkeypatch.setattr(b.client.aio.models, "generate_content", boom)
    with pytest.raises(BackendError) as e:
        asyncio.run(b.generate("m", "hi", None, None, 5))
    assert e.value.kind == "unexpected" and e.value.note == "ValueError"
