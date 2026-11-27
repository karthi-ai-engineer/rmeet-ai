"""Max, first version: says hello when spoken to, stays quiet otherwise. Teams settings."""

import pytest

from max.config import ConfigError, load_teams_settings
from max.teams.hello import hello_text, should_answer


def test_answers_in_its_own_chat_always():
    assert should_answer("personal", mentioned=False)


def test_answers_in_channels_and_group_chats_only_when_mentioned():
    assert should_answer("channel", mentioned=True) and not should_answer("channel", mentioned=False)
    assert should_answer("groupChat", mentioned=True) and not should_answer("groupChat", mentioned=False)


def test_hello_uses_the_first_name():
    assert hello_text("Prince") == "Hi Prince, I'm Max. I'm connected 👋"
    assert hello_text("Rachitaa Sharma") == "Hi Rachitaa, I'm Max. I'm connected 👋"
    assert hello_text("") == "Hi, I'm Max. I'm connected 👋"
    assert hello_text(None) == "Hi, I'm Max. I'm connected 👋"


def test_teams_settings_default_to_the_simulator(monkeypatch):
    for k in ("TEAMS_MODE", "BOT_PORT", "CLIENT_ID", "CLIENT_SECRET", "TENANT_ID"):
        monkeypatch.delenv(k, raising=False)
    s = load_teams_settings(_env_file=None)
    assert s.teams_mode == "sim" and s.bot_port == 3978
    assert s.bot_host == "127.0.0.1"                                 # the simulator setup is never open to the network


def test_real_teams_needs_the_app_registration(monkeypatch):
    for k in ("CLIENT_ID", "CLIENT_SECRET", "TENANT_ID"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(ConfigError) as e:
        load_teams_settings(_env_file=None, teams_mode="teams")
    assert "CLIENT_ID" in str(e.value)
