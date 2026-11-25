"""Settings: clear errors, defaults, and secrets never shown."""

import logging

import pytest

from max.config import ConfigError, load_settings
from max.log import setup_logging

SECRET = "AIza-very-secret-test-value-0123456789"


@pytest.fixture(autouse=True)
def no_real_env(monkeypatch):
    for name in ("GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_FALLBACK_MODEL"):
        monkeypatch.delenv(name, raising=False)


def test_missing_key_gives_clear_error():
    with pytest.raises(ConfigError) as e:
        load_settings(_env_file=None)
    assert "GEMINI_API_KEY is missing" in str(e.value) and ".env" in str(e.value)


def test_empty_key_is_rejected_without_showing_it(tmp_path):
    env = tmp_path / ".env"
    env.write_text("GEMINI_API_KEY=   \n", encoding="utf-8")
    with pytest.raises(ConfigError) as e:
        load_settings(_env_file=env)
    assert "GEMINI_API_KEY is invalid" in str(e.value)


def test_reads_env_file_and_hides_key(tmp_path):
    env = tmp_path / ".env"
    env.write_text(f"GEMINI_API_KEY={SECRET}\nGEMINI_FALLBACK_MODEL=\n", encoding="utf-8")
    s = load_settings(_env_file=env)
    assert s.gemini_api_key.get_secret_value() == SECRET
    assert s.gemini_model == "gemini-3.1-flash-lite"
    assert s.gemini_fallback_model == "gemini-3.5-flash-lite"   # empty line in .env -> default
    assert SECRET not in repr(s) and SECRET not in str(s) and SECRET not in s.model_dump_json()


def test_invalid_number_error_hides_value(tmp_path):
    env = tmp_path / ".env"
    env.write_text(f"GEMINI_API_KEY={SECRET}\nLLM_TIMEOUT_S={SECRET}\n", encoding="utf-8")
    with pytest.raises(ConfigError) as e:
        load_settings(_env_file=env)
    assert "LLM_TIMEOUT_S is invalid" in str(e.value) and SECRET not in str(e.value)


def test_logs_redact_the_key(tmp_path):
    log = setup_logging("unit", tmp_path, secrets=[SECRET], console_level="CRITICAL")
    log.warning("calling with key %s", SECRET)
    try:
        raise RuntimeError(f"boom {SECRET}")
    except RuntimeError:
        log.exception("failed")
    for h in logging.getLogger().handlers:
        h.flush()
    text = (tmp_path / "logs" / "unit.log").read_text(encoding="utf-8")
    assert "calling with key ***" in text and "boom ***" in text and SECRET not in text


def test_setup_logging_twice_does_not_duplicate(tmp_path):
    setup_logging("dup", tmp_path, console_level="CRITICAL")
    log = setup_logging("dup", tmp_path, console_level="CRITICAL")
    log.warning("once")
    for h in logging.getLogger().handlers:
        h.flush()
    assert (tmp_path / "logs" / "dup.log").read_text(encoding="utf-8").count("once") == 1


def test_log_level_any_case_and_positive_timeouts(tmp_path):
    s = load_settings(_env_file=None, gemini_api_key="test-key-123", log_level="debug")
    assert s.log_level == "DEBUG"
    with pytest.raises(ConfigError) as e:
        load_settings(_env_file=None, gemini_api_key="test-key-123", llm_timeout_s=0)
    assert "LLM_TIMEOUT_S is invalid" in str(e.value)
