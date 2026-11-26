"""Settings: provider-neutral names (old GEMINI_* still work), clear errors, defaults, secrets never shown."""

import logging

import pytest

from max.config import ConfigError, load_settings
from max.log import setup_logging

SECRET = "AIza-very-secret-test-value-0123456789"
NAMES = ("LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL", "LLM_FALLBACK_MODEL", "LLM_BASE_URL", "LLM_EXTRA_BODY",
         "GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_FALLBACK_MODEL")


@pytest.fixture(autouse=True)
def no_real_env(monkeypatch):
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)


def env_file(tmp_path, text):
    f = tmp_path / ".env"
    f.write_text(text, encoding="utf-8")
    return f


def test_missing_key_gives_clear_error():
    with pytest.raises(ConfigError) as e:
        load_settings(_env_file=None)
    msg = str(e.value)
    assert "LLM_API_KEY" in msg and "missing" in msg and ".env" in msg


def test_empty_key_is_rejected_without_showing_it(tmp_path):
    with pytest.raises(ConfigError) as e:
        load_settings(_env_file=env_file(tmp_path, "LLM_API_KEY=   \n"))
    assert "LLM_API_KEY" in str(e.value) and ("empty" in str(e.value) or "missing" in str(e.value))


def test_new_names_and_defaults(tmp_path):
    s = load_settings(_env_file=env_file(tmp_path, f"LLM_API_KEY={SECRET}\nLLM_FALLBACK_MODEL=\n"))
    assert s.llm_provider == "gemini"
    assert s.llm_api_key.get_secret_value() == SECRET
    assert s.llm_model == "gemini-3.1-flash-lite"
    assert s.llm_fallback_model == "gemini-3.5-flash-lite"      # empty line in .env -> default
    assert SECRET not in repr(s) and SECRET not in str(s) and SECRET not in s.model_dump_json()


def test_old_gemini_names_still_work(tmp_path):
    s = load_settings(_env_file=env_file(tmp_path, f"GEMINI_API_KEY={SECRET}\nGEMINI_MODEL=gemini-x\n"
                                                    "GEMINI_FALLBACK_MODEL=gemini-y\n"))
    assert s.llm_api_key.get_secret_value() == SECRET
    assert (s.llm_model, s.llm_fallback_model) == ("gemini-x", "gemini-y")


def test_new_name_wins_over_old(tmp_path):
    s = load_settings(_env_file=env_file(tmp_path, "GEMINI_MODEL=old-model\nLLM_MODEL=new-model\nLLM_API_KEY=k-123\n"))
    assert s.llm_model == "new-model"


def test_openai_compatible_needs_a_server_address_but_no_key(tmp_path):
    with pytest.raises(ConfigError) as e:
        load_settings(_env_file=env_file(tmp_path, "LLM_PROVIDER=openai_compatible\nLLM_MODEL=qwen\n"))
    assert "LLM_BASE_URL" in str(e.value)
    s = load_settings(_env_file=env_file(tmp_path, "LLM_PROVIDER=openai_compatible\nLLM_MODEL=qwen\n"
                                                    "LLM_BASE_URL=http://gpu-server:8000/v1/\n"))
    assert s.llm_api_key is None and s.llm_base_url == "http://gpu-server:8000/v1"


def test_openai_compatible_has_no_gemini_model_defaults(tmp_path):
    with pytest.raises(ConfigError) as e:
        load_settings(_env_file=env_file(tmp_path, "LLM_PROVIDER=openai_compatible\nLLM_BASE_URL=http://x/v1\n"))
    assert "LLM_MODEL" in str(e.value)


def test_extra_body_is_json(tmp_path):
    s = load_settings(_env_file=env_file(tmp_path, 'LLM_PROVIDER=openai_compatible\nLLM_BASE_URL=http://x/v1\n'
                                                    'LLM_MODEL=qwen\nLLM_EXTRA_BODY={"chat_template_kwargs": {"enable_thinking": false}}\n'))
    assert s.llm_extra_body == {"chat_template_kwargs": {"enable_thinking": False}}
    with pytest.raises(ConfigError) as e:
        load_settings(_env_file=env_file(tmp_path, f"LLM_API_KEY={SECRET}\nLLM_EXTRA_BODY=not json\n"))
    assert "LLM_EXTRA_BODY" in str(e.value) and SECRET not in str(e.value)


def test_unknown_provider_error_hides_the_key(tmp_path):
    with pytest.raises(ConfigError) as e:
        load_settings(_env_file=env_file(tmp_path, f"LLM_API_KEY={SECRET}\nLLM_PROVIDER=gpt\n"))
    assert "LLM_PROVIDER" in str(e.value) and SECRET not in str(e.value)


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


def test_log_level_any_case():
    s = load_settings(_env_file=None, llm_api_key="test-key-123", log_level="debug")
    assert s.log_level == "DEBUG"


# ---- review fixes (26 Nov 2026)
def test_gemini_key_is_never_used_for_another_provider(tmp_path):
    s = load_settings(_env_file=env_file(tmp_path, f"GEMINI_API_KEY={SECRET}\nLLM_PROVIDER=openai_compatible\n"
                                                    "LLM_BASE_URL=http://gpu:8000/v1\nLLM_MODEL=qwen\n"))
    assert s.llm_api_key is None and s.gemini_api_key is None
    from max.llm.backends import make_backend
    assert make_backend(s).api_key is None


def test_empty_new_lines_do_not_hide_old_values(tmp_path):
    s = load_settings(_env_file=env_file(tmp_path, f"GEMINI_API_KEY={SECRET}\nGEMINI_MODEL=gemini-x\n"
                                                    "LLM_MODEL=\nLLM_API_KEY=\n"))
    assert s.llm_model == "gemini-x" and s.llm_api_key.get_secret_value() == SECRET


def test_provider_name_any_case(tmp_path):
    s = load_settings(_env_file=env_file(tmp_path, "LLM_PROVIDER=Gemini\nLLM_API_KEY=k-1\n"))
    assert s.llm_provider == "gemini"


@pytest.mark.parametrize("url", ["gpu:8000/v1", "http://gpu:abc/v1", "ftp://gpu/v1"])
def test_bad_server_address_is_rejected(tmp_path, url):
    with pytest.raises(ConfigError) as e:
        load_settings(_env_file=env_file(tmp_path, f"LLM_PROVIDER=openai_compatible\nLLM_MODEL=q\nLLM_BASE_URL={url}\n"))
    assert "LLM_BASE_URL" in str(e.value)


def test_describe_hides_secrets_in_address_and_extra_fields(tmp_path):
    from limits import LimitsStore
    from max.config import describe
    s = load_settings(_env_file=env_file(tmp_path, "LLM_PROVIDER=openai_compatible\nLLM_MODEL=q\n"
                                                    "LLM_BASE_URL=http://user:tok3n@gpu:8000/v1\n"
                                                    'LLM_EXTRA_BODY={"api_token": "tok3n"}\n'))
    text = describe(s, LimitsStore(user_file=None))
    assert "tok3n" not in text and "gpu:8000" in text and "api_token" in text
