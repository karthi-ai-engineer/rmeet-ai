"""The model client: retries, fallback, rate limits, time limits, spend cap. All offline with a fake backend."""

import asyncio

import pytest

from max.llm import FALLBACK_MESSAGE, LLM, BackendError, LLMError


def ask(llm, **kw):
    return asyncio.run(llm.ask("hello", **kw))


def test_main_model_answers(make_llm, meter):
    llm, backend = make_llm({"main": ["hi there"]})
    r = ask(llm)
    assert (r.text, r.model, r.used_fallback, r.attempts) == ("hi there", "main", False, 1)
    assert backend.calls == ["main"]
    ev = meter.read_events()
    assert len(ev) == 1 and ev[0]["status"] == 200 and ev[0]["in"] == 100 and ev[0]["source"] == "max"


def test_server_error_retries_once_then_succeeds(make_llm, clock):
    llm, backend = make_llm({"main": [BackendError("server", 503), "ok"]})
    r = ask(llm)
    assert r.text == "ok" and r.model == "main" and r.attempts == 2
    assert clock.slept == [1.0]


def test_two_failures_switch_to_backup(make_llm, meter):
    llm, backend = make_llm({"main": [BackendError("server", 500)], "backup": ["from backup"]})
    r = ask(llm)
    assert r.text == "from backup" and r.used_fallback and backend.calls == ["main", "main", "backup"]
    assert [e["status"] for e in meter.read_events()] == [500, 500, 200]


def test_not_found_skips_straight_to_backup(make_llm):
    llm, backend = make_llm({"main": [BackendError("not_found", 404)], "backup": ["ok"]})
    assert ask(llm).model == "backup"
    assert backend.calls == ["main", "backup"]


def test_short_rate_limit_waits_then_retries(make_llm, clock):
    llm, backend = make_llm({"main": [BackendError("rate_limit", 429, retry_after=2.0), "ok"]})
    r = ask(llm)
    assert r.model == "main" and clock.slept == [2.0]


def test_long_rate_limit_goes_to_backup_without_waiting(make_llm, clock):
    llm, backend = make_llm({"main": [BackendError("rate_limit", 429, retry_after=40.0)], "backup": ["ok"]})
    r = ask(llm)
    assert r.model == "backup" and clock.slept == []


def test_rate_limit_without_delay_goes_to_backup(make_llm, clock):
    llm, _ = make_llm({"main": [BackendError("rate_limit", 429)], "backup": ["ok"]})
    assert ask(llm).model == "backup" and clock.slept == []


def test_bad_key_stops_immediately(make_llm):
    llm, backend = make_llm({"main": [BackendError("auth", 403)], "backup": ["never"]})
    with pytest.raises(LLMError) as e:
        ask(llm)
    assert e.value.reason == "auth" and backend.calls == ["main"]


def test_empty_answer_counts_as_failure(make_llm, meter):
    llm, backend = make_llm({"main": ["   "], "backup": ["real answer"]})
    r = ask(llm)
    assert r.text == "real answer" and backend.calls == ["main", "backup"]
    first = meter.read_events()[0]
    assert first["status"] == 200 and first["in"] == 100 and "empty" in first["note"]  # billed, so logged


def test_everything_fails_gives_clear_error(make_llm):
    llm, backend = make_llm({"main": [BackendError("server", 500)], "backup": [BackendError("server", 502)]})
    with pytest.raises(LLMError) as e:
        ask(llm)
    assert e.value.reason == "unavailable" and "backup" in str(e.value)
    assert len(backend.calls) == 4
    assert "try again" in FALLBACK_MESSAGE  # what callers say instead of going silent


def test_slow_model_times_out_and_falls_back(clock, meter):
    from tests.unit.conftest import FakeBackend
    backend = FakeBackend(clock, {"main": [("slow", 1.0)], "backup": ["fast"]})
    llm = LLM(backend, meter, ["main", "backup"], timeout_s=0.05, sleep=clock.sleep, clock=clock)
    r = asyncio.run(llm.ask("hi"))
    assert r.model == "backup" and backend.calls == ["main", "main", "backup"]
    assert meter.read_events()[0]["note"].startswith("timeout")


def test_deadline_stops_retrying(make_llm):
    llm, backend = make_llm({"main": [BackendError("server", 500)], "backup": ["ok"]}, deadline_s=1.5)
    with pytest.raises(LLMError) as e:   # first try 0.2s + 1s backoff leaves < 1s: give up instead of overrunning
        ask(llm)
    assert e.value.reason == "unavailable" and "within" in str(e.value)


def test_daily_cap_blocks_calls(make_llm, meter):
    meter.set_limits(daily_requests=1)
    llm, backend = make_llm({"main": ["one", "two"]})
    assert ask(llm).text == "one"
    with pytest.raises(LLMError) as e:
        ask(llm)
    assert e.value.reason == "budget" and backend.calls == ["main"]


def test_pause_switch_blocks_calls(make_llm, meter):
    meter.set_paused(True)
    llm, backend = make_llm({"main": ["never"]})
    with pytest.raises(LLMError) as e:
        ask(llm)
    assert e.value.reason == "budget" and backend.calls == []


def test_models_are_deduplicated_and_required(clock, meter):
    from tests.unit.conftest import FakeBackend
    llm = LLM(FakeBackend(clock, {}), meter, ["a", "", "a", "b"])
    assert llm.models == ["a", "b"]
    with pytest.raises(ValueError):
        LLM(FakeBackend(clock, {}), meter, ["", ""])


def test_from_settings_uses_main_then_backup(tmp_path, meter, clock):
    from max.config import load_settings
    from tests.unit.conftest import FakeBackend
    s = load_settings(_env_file=None, llm_api_key="test-key-123", data_dir=tmp_path)
    llm = LLM.from_settings(s, meter=meter, backend=FakeBackend(clock, {}))
    assert llm.models == ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite"]


def test_unexpected_error_goes_to_backup(make_llm):
    llm, backend = make_llm({"main": [BackendError("unexpected", note="ValueError")], "backup": ["ok"]})
    assert ask(llm).model == "backup" and backend.calls == ["main", "backup"]


def test_rate_limit_wait_respects_deadline(make_llm, clock):
    # 4s wait is allowed (max_wait 5s) but only ~3s are left before the deadline: use the backup instead
    llm, backend = make_llm({"main": [BackendError("rate_limit", 429, retry_after=4.0)], "backup": ["ok"]},
                            deadline_s=3.2)
    assert ask(llm).model == "backup" and clock.slept == []


def test_cost_log_failure_never_loses_the_answer(make_llm, meter, monkeypatch):
    def broken(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(meter, "record", broken)
    llm, _ = make_llm({"main": ["still answered"]})
    assert ask(llm).text == "still answered"


def test_backend_follows_the_provider_setting(monkeypatch):
    from max.config import load_settings
    from max.llm.backends import make_backend
    from max.llm.gemini import GeminiBackend
    from max.llm.openai_compat import OpenAICompatBackend
    for n in ("LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL", "GEMINI_API_KEY", "GEMINI_MODEL"):
        monkeypatch.delenv(n, raising=False)
    s = load_settings(_env_file=None, llm_api_key="k-1")
    assert isinstance(make_backend(s), GeminiBackend)
    s2 = load_settings(_env_file=None, llm_provider="openai_compatible", llm_base_url="http://x/v1", llm_model="qwen")
    assert isinstance(make_backend(s2), OpenAICompatBackend)


def test_time_limits_come_from_the_limits_file_and_apply_live(tmp_path, meter, clock):
    from limits import LimitsStore
    from tests.unit.conftest import FakeBackend
    store = LimitsStore(user_file=tmp_path / "limits.toml")
    llm = LLM(FakeBackend(clock, {"main": ["ok"]}), meter, ["main"], limits=store, sleep=clock.sleep, clock=clock)
    assert llm.current_limits() == (20, 60, 5)
    store.update({"ai": {"model_timeout_s": 7, "answer_deadline_s": 30}})
    assert llm.current_limits() == (7, 30, 5)                       # no restart needed
    assert ask(llm).text == "ok"


def test_auth_message_names_the_provider_setting(make_llm):
    llm, _ = make_llm({"main": [BackendError("auth", 401)]})
    with pytest.raises(LLMError) as e:
        ask(llm)
    assert e.value.reason == "auth" and "LLM_API_KEY" in str(e.value)
