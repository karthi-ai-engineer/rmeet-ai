"""Max's app setup: simulator mode can never use real credentials or be reached from outside this PC;
real-Teams mode always checks Microsoft's signature."""

import pytest
from fastapi.testclient import TestClient

from max.app import SIM_UNSAFE_ENV, build_app
from max.config import load_teams_settings

LOCAL = ("127.0.0.1", 50000)


@pytest.fixture
def clean_env(monkeypatch):
    for k in [*SIM_UNSAFE_ENV, "TEAMS_MODE", "BOT_PORT"]:
        monkeypatch.delenv(k, raising=False)
    return monkeypatch


def sim():
    return load_teams_settings(_env_file=None, teams_mode="sim", bot_port=3999)


def test_sim_mode_ignores_real_credentials_from_the_environment(clean_env):
    clean_env.setenv("CLIENT_ID", "11111111-2222-3333-4444-555555555555")
    clean_env.setenv("CLIENT_SECRET", "not-a-real-secret")
    clean_env.setenv("TENANT_ID", "tenant")
    app, _, server = build_app(sim())
    assert app.credentials is None                                   # no real token can ever be fetched
    assert app.options.dangerously_allow_unauthenticated_requests is True
    assert server.config.host == "127.0.0.1"


def test_real_mode_always_checks_signatures(clean_env):
    clean_env.setenv("DANGEROUSLY_ALLOW_UNAUTHENTICATED_REQUESTS", "true")   # a stray line in .env
    s = load_teams_settings(_env_file=None, teams_mode="teams", client_id="11111111-2222-3333-4444-555555555555",
                            client_secret="x" * 12, tenant_id="tenant")
    app, _, _ = build_app(s)
    assert app.options.dangerously_allow_unauthenticated_requests is False
    assert app.credentials is not None


def test_sim_mode_only_answers_this_pc(clean_env):
    _, web, _ = build_app(sim())
    local = TestClient(web, client=LOCAL)
    assert local.get("/health").status_code == 200
    assert TestClient(web, client=("192.168.1.20", 50000)).get("/health").status_code == 403
    assert local.get("/health", headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 403  # tunnels / proxies
    assert local.get("/health", headers={"Forwarded": "for=203.0.113.9"}).status_code == 403


def test_sim_mode_only_takes_json_posts(clean_env):
    _, web, _ = build_app(sim())
    r = TestClient(web, client=LOCAL).post("/api/messages", content="{}", headers={"content-type": "text/plain"})
    assert r.status_code == 415
