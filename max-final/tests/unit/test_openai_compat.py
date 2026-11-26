"""The OpenAI-style backend (company Qwen, other open models, Gemini's OpenAI door) against a fake server."""

import asyncio
import json

import httpx
import pytest

from max.llm import BackendError
from max.llm.openai_compat import OpenAICompatBackend


def backend(handler, **kw):
    return OpenAICompatBackend("http://gpu-server:8000/v1/", api_key=kw.pop("api_key", "k-123"),
                               transport=httpx.MockTransport(handler), **kw)


def ok_body(text="Hello", usage=None):
    return {"choices": [{"message": {"role": "assistant", "content": text}}],
            "usage": usage or {"prompt_tokens": 12, "completion_tokens": 8,   # 8 = 3 answer + 5 reasoning
                               "prompt_tokens_details": {"cached_tokens": 2},
                               "completion_tokens_details": {"reasoning_tokens": 5}}}


def test_answer_and_usage():
    seen = {}

    def handler(req: httpx.Request):
        seen["url"], seen["auth"], seen["body"] = str(req.url), req.headers.get("authorization"), json.loads(req.content)
        return httpx.Response(200, json=ok_body())

    r = asyncio.run(backend(handler, extra_body={"chat_template_kwargs": {"enable_thinking": False}}).generate(
        "qwen", "hi", "you are Max", 50, 10))
    assert r.text == "Hello"
    assert r.usage == {"in": 12, "out": 3, "think": 5, "cached": 2, "audio_in": 0}
    assert seen["url"] == "http://gpu-server:8000/v1/chat/completions"
    assert seen["auth"] == "Bearer k-123"
    b = seen["body"]
    assert b["model"] == "qwen" and b["max_tokens"] == 50
    assert b["messages"] == [{"role": "system", "content": "you are Max"}, {"role": "user", "content": "hi"}]
    assert b["chat_template_kwargs"] == {"enable_thinking": False}


def test_no_key_sends_no_auth_header_and_no_system_message():
    seen = {}

    def handler(req):
        seen["auth"], seen["body"] = req.headers.get("authorization"), json.loads(req.content)
        return httpx.Response(200, json=ok_body())

    asyncio.run(backend(handler, api_key=None).generate("qwen", "hi", None, None, 10))
    assert seen["auth"] is None
    assert seen["body"]["messages"] == [{"role": "user", "content": "hi"}] and "max_tokens" not in seen["body"]


@pytest.mark.parametrize("status,body,headers,kind,retry", [
    (429, {"error": {"message": "slow down"}}, {"retry-after": "7"}, "rate_limit", 7.0),
    (429, {"error": {"message": "slow down"}}, {}, "rate_limit", None),
    (401, {"error": {"message": "bad key"}}, {}, "auth", None),
    (403, {"error": {"message": "no"}}, {}, "auth", None),
    (400, [{"error": {"message": "API key not valid. Please pass a valid API key."}}], {}, "auth", None),
    (400, {"error": {"message": "max_tokens too large"}}, {}, "bad_request", None),
    (404, {"error": {"message": "model not found"}}, {}, "not_found", None),
    (500, {"error": {"message": "oops"}}, {}, "server", None),
    (503, "busy", {}, "server", None),
    (504, "gateway timeout", {}, "timeout", None),
])
def test_errors_become_the_same_kinds_as_gemini(status, body, headers, kind, retry):
    def handler(req):
        if isinstance(body, str):
            return httpx.Response(status, text=body, headers=headers)
        return httpx.Response(status, json=body, headers=headers)

    with pytest.raises(BackendError) as e:
        asyncio.run(backend(handler).generate("qwen", "hi", None, None, 10))
    assert e.value.kind == kind and e.value.status == status and e.value.retry_after == retry


def test_timeout_and_network_errors():
    def slow(req):
        raise httpx.ReadTimeout("slow", request=req)

    def down(req):
        raise httpx.ConnectError("refused", request=req)

    with pytest.raises(BackendError) as e:
        asyncio.run(backend(slow).generate("qwen", "hi", None, None, 10))
    assert e.value.kind == "timeout"
    with pytest.raises(BackendError) as e:
        asyncio.run(backend(down).generate("qwen", "hi", None, None, 10))
    assert e.value.kind == "network"


@pytest.mark.parametrize("resp", [
    httpx.Response(200, text="<html>not json</html>"),
    httpx.Response(200, json={"choices": []}),
    httpx.Response(200, json={"unexpected": True}),
])
def test_odd_answers_never_escape_as_is(resp):
    with pytest.raises(BackendError) as e:
        asyncio.run(backend(lambda req: resp).generate("qwen", "hi", None, None, 10))
    assert e.value.kind == "unexpected"


def test_empty_content_is_an_empty_answer_not_a_crash():
    r = asyncio.run(backend(lambda req: httpx.Response(200, json=ok_body(text=None))).generate("qwen", "hi", None, None, 10))
    assert r.text == ""


def test_model_listed():
    def handler(req):
        assert str(req.url) == "http://gpu-server:8000/v1/models"
        return httpx.Response(200, json={"data": [{"id": "qwen"}, {"id": "models/gemini-3.1-flash-lite"}]})

    b = backend(handler)
    assert asyncio.run(b.model_listed("qwen")) is True
    assert asyncio.run(b.model_listed("gemini-3.1-flash-lite")) is True     # Gemini's door lists "models/<id>"
    assert asyncio.run(b.model_listed("missing")) is False


def test_key_never_in_error_notes():
    def handler(req):
        return httpx.Response(401, json={"error": {"message": "invalid key k-123"}})

    with pytest.raises(BackendError) as e:
        asyncio.run(backend(handler).generate("qwen", "hi", None, None, 10))
    assert "k-123" not in str(e.value) and "k-123" not in e.value.note


# ---- review fixes (26 Nov 2026)
def test_reasoning_tokens_are_not_counted_twice():
    r = asyncio.run(backend(lambda req: httpx.Response(200, json=ok_body())).generate("qwen", "hi", None, None, 10))
    assert (r.usage["out"], r.usage["think"]) == (3, 5)


@pytest.mark.parametrize("body", [
    {"choices": [{"message": "hi"}]},                                   # message is not an object
    {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": "n/a"}},
])
def test_odd_shapes_never_crash(body):
    try:
        r = asyncio.run(backend(lambda req: httpx.Response(200, json=body)).generate("qwen", "hi", None, None, 10))
        assert isinstance(r.text, str)                                   # usage text is ignored, answer kept
    except BackendError as e:
        assert e.kind == "unexpected"


def test_content_as_a_list_of_parts_is_joined():
    body = {"choices": [{"message": {"content": [{"type": "text", "text": "Hel"}, {"type": "text", "text": "lo"}]}}]}
    r = asyncio.run(backend(lambda req: httpx.Response(200, json=body)).generate("qwen", "hi", None, None, 10))
    assert r.text == "Hello"


def test_bad_server_address_is_a_backend_error():
    b = OpenAICompatBackend("http://gpu:abc/v1", api_key=None)
    with pytest.raises(BackendError) as e:
        asyncio.run(b.generate("qwen", "hi", None, None, 2))
    assert e.value.kind in ("unexpected", "network")


def test_key_is_hidden_even_when_the_message_is_long():
    key = "sk-" + "Z" * 40
    msg = "x" * 195 + key + " is wrong"                                  # the 200-char cut lands inside the key

    def handler(req):
        return httpx.Response(401, json={"error": {"message": msg}})

    with pytest.raises(BackendError) as e:
        asyncio.run(OpenAICompatBackend("http://s/v1", api_key=key, transport=httpx.MockTransport(handler))
                    .generate("m", "hi", None, None, 5))
    assert "ZZZZZ" not in e.value.note and "sk-" not in e.value.note
