"""AI usage meter (any provider), prices, limits from the limits file, and the dashboard API."""

import pytest
from fastapi.testclient import TestClient

import json

from ai_usage import Blocked, Meter, prices
from ai_usage import meter as meter_mod
from ai_usage.dashboard import create_app, summary
from limits import LimitsStore


def test_cost_uses_model_prices():
    e = {"model": "gemini-3.1-flash-lite", "in": 1_000_000, "out": 1_000_000}
    assert prices.cost_usd(e) == pytest.approx(0.25 + 1.50)
    assert prices.cost_usd({"model": "gemini-2.5-flash-lite", "in": 1_000_000}) == pytest.approx(0.10)
    assert prices.cost_usd({"model": "gemini-3.1-flash-lite-preview", "in": 1_000_000}) == pytest.approx(0.25)
    assert prices.cost_usd({"model": "unknown-model", "in": 5}) is None
    assert prices.cost_usd({"model": "x", "status": 503, "in": 5}) == 0.0


def test_thinking_tokens_cost_like_output():
    e = {"model": "gemini-3.1-flash-lite", "out": 500_000, "think": 500_000}
    assert prices.cost_usd(e) == pytest.approx(1.50)


def test_record_and_read(tmp_path):
    m = Meter(tmp_path)
    m.record("gemini-3.1-flash-lite", "brain", "max", 200, 1200, {"in": 1000, "out": 100})
    m.record("gemini-3.1-flash-lite", "brain", "max", 503, 300, None, "server: busy")
    ev = m.read_events()
    assert [e["status"] for e in ev] == [200, 503]
    assert ev[0]["cost"] > 0 and ev[1]["cost"] == 0.0 and ev[1]["note"] == "server: busy"


def test_half_written_line_is_skipped(tmp_path):
    m = Meter(tmp_path)
    m.record("gemini-3.1-flash-lite", "brain", "max", 200, 1, {"in": 1})
    f = next(tmp_path.glob("usage-*.jsonl"))
    f.write_text(f.read_text(encoding="utf-8") + '{"broken', encoding="utf-8")
    assert len(m.read_events()) == 1


def test_daily_usd_limit(tmp_path):
    m = Meter(tmp_path)
    m.set_limits(daily_usd=0.000001)
    m.check("gemini-3.1-flash-lite", "max")          # nothing spent yet: allowed
    m.record("gemini-3.1-flash-lite", "brain", "max", 200, 1, {"in": 10_000})
    with pytest.raises(Blocked):
        m.check("gemini-3.1-flash-lite", "max")


def test_zero_means_no_limit(tmp_path):
    m = Meter(tmp_path)
    m.set_limits(daily_usd=0, daily_requests=0)
    for _ in range(3):
        m.record("gemini-3.1-flash-lite", "brain", "max", 200, 1, {"in": 1_000_000})
    m.check("gemini-3.1-flash-lite", "max")


def test_limits_come_from_the_limits_file(tmp_path):
    assert Meter(tmp_path).limits() == {"daily_usd": 1.0, "daily_requests": 1000.0}   # limits.toml defaults
    (tmp_path / "limits.toml").write_text("[ai]\ndaily_budget_usd = 3.5\n", encoding="utf-8")
    assert Meter(tmp_path).limits()["daily_usd"] == 3.5


def test_bad_limits_file_keeps_defaults_and_says_why(tmp_path):
    (tmp_path / "limits.toml").write_text("not toml [", encoding="utf-8")
    m = Meter(tmp_path)
    assert m.limits()["daily_usd"] == 1.0 and m.limits_store.problem


def test_company_models_cost_nothing_but_are_counted(tmp_path):
    m = Meter(tmp_path)
    e = m.record("unsloth/Qwen3.8-27B-NVFP4", "brain", "max", 200, 900, {"in": 50_000, "out": 2_000})
    assert e["cost"] == 0.0 and "price_estimated" not in e and m.today_totals()["requests"] == 1


def test_old_gemini_cost_folder_is_moved_once(tmp_path, monkeypatch):
    old, new, user = tmp_path / "gemini_cost", tmp_path / "ai_usage", tmp_path / "limits.toml"
    old.mkdir()
    (old / "usage-2026-11-25-p1.jsonl").write_text('{"ts": 1, "model": "m", "status": 200, "cost": 0.01}\n',
                                                   encoding="utf-8")
    (old / "limits.json").write_text(json.dumps({"daily_usd": 2.0, "daily_requests": 500}), encoding="utf-8")
    meter_mod._move_old_folder(old, new, user)
    assert not old.exists() and (new / "usage-2026-11-25-p1.jsonl").exists()
    lim = LimitsStore(user_file=user).get().ai
    assert lim.daily_budget_usd == 2.0 and lim.daily_requests == 500
    meter_mod._move_old_folder(old, new, user)        # second time: nothing happens


def test_pause_switch(tmp_path):
    m = Meter(tmp_path)
    m.set_paused(True)
    with pytest.raises(Blocked):
        m.check("x", "max")
    m.set_paused(False)
    m.check("x", "max")


def test_summary_groups_today(tmp_path):
    m = Meter(tmp_path)
    m.record("gemini-3.1-flash-lite", "brain", "max", 200, 1000, {"in": 100, "out": 10})
    m.record("gemini-2.5-flash-lite", "brain", "max", 200, 3000, {"in": 100, "out": 10})
    s = summary(m)
    assert s["today"]["requests"] == 2 and len(s["byFeature"]) == 2 and len(s["minutes"]) == 60


def test_dashboard_api(tmp_path):
    m = Meter(tmp_path)
    client = TestClient(create_app(m))
    assert "AI usage" in client.get("/").text
    assert client.get("/api/usage").json()["paused"] is False
    # changes need the custom header
    assert client.post("/api/pause", json={"paused": True}).status_code == 403
    assert client.post("/api/pause", json={"paused": True}, headers={"X-Dashboard": "1"}).status_code == 200
    assert m.paused()
    r = client.post("/api/limits", json={"daily_usd": "2.5", "daily_requests": ""}, headers={"X-Dashboard": "1"})
    assert r.status_code == 200 and m.limits()["daily_usd"] == 2.5
    assert client.post("/api/limits", json={"daily_usd": "abc"}, headers={"X-Dashboard": "1"}).status_code == 400
    assert client.post("/api/limits", json={"daily_usd": -1}, headers={"X-Dashboard": "1"}).status_code == 400
    assert client.post("/api/limits", json={"daily_requests": "1e999"}, headers={"X-Dashboard": "1"}).status_code == 400
    assert (tmp_path / "limits.toml").exists()                       # saved in the one limits file


def test_unknown_model_still_counts_towards_the_cap(tmp_path):
    m = Meter(tmp_path)
    m.set_limits(daily_usd=0.01)
    e = m.record("gemini-some-new-model", "brain", "max", 200, 1, {"in": 100_000})
    assert e["price_estimated"] is True and e["cost"] > 0
    with pytest.raises(Blocked):
        m.check("gemini-some-new-model", "max")


def test_several_programs_writing_at_once_lose_nothing(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    code = ("import sys; from ai_usage import Meter; m = Meter(sys.argv[1]);"
            "[m.record('gemini-3.1-flash-lite', 'brain', 'p', 200, 1, {'in': 10}) for _ in range(200)]")
    procs = [subprocess.Popen([sys.executable, "-c", code, str(tmp_path)], cwd=root) for _ in range(4)]
    assert all(p.wait(timeout=60) == 0 for p in procs)
    assert len(Meter(tmp_path).read_events()) == 800
