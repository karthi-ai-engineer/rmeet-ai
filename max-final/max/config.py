"""
Max's settings, read from the root .env file (and environment variables, which win).

  settings = load_settings()      raises ConfigError with a clear message if something is missing
  python -m max.config            prints the settings in use (keys hidden) and every limit (python run.py settings)

The AI provider is a setting (Karthi, 26 Nov 2026: the model must stay swappable):
  LLM_PROVIDER = gemini | openai_compatible      (openai_compatible = company Qwen on vLLM, other open models, ...)
  LLM_API_KEY, LLM_MODEL, LLM_FALLBACK_MODEL, LLM_BASE_URL, LLM_EXTRA_BODY
The Step 0 names GEMINI_API_KEY / GEMINI_MODEL / GEMINI_FALLBACK_MODEL still work (the new names win).
Limits (budgets, time limits, message limits...) are NOT here: they live in limits.toml (see limits.py).

Secrets are SecretStr: printing settings never shows them. Error messages name the setting, never its value.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from typing import Annotated, Literal

from pydantic import AliasChoices, Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from pydantic_settings.exceptions import SettingsError

ROOT = Path(__file__).resolve().parent.parent

GEMINI_DEFAULT_MODEL = "gemini-3.1-flash-lite"
GEMINI_DEFAULT_FALLBACK_MODEL = "gemini-3.5-flash-lite"
GEMINI_OPENAI_URL = "https://generativelanguage.googleapis.com/v1beta/openai"   # Gemini's OpenAI-style door

# field -> the name people write in .env (used in error messages)
ENV_NAME = {"llm_provider": "LLM_PROVIDER", "llm_api_key": "LLM_API_KEY", "llm_model": "LLM_MODEL",
            "llm_fallback_model": "LLM_FALLBACK_MODEL", "llm_base_url": "LLM_BASE_URL",
            "llm_extra_body": "LLM_EXTRA_BODY", "data_dir": "DATA_DIR", "log_level": "LOG_LEVEL",
            "gemini_api_key": "GEMINI_API_KEY", "gemini_model": "GEMINI_MODEL",
            "gemini_fallback_model": "GEMINI_FALLBACK_MODEL"}


class ConfigError(Exception):
    """A setting is missing or invalid. The message is safe to show (no secret values)."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore",
                                      populate_by_name=True, env_ignore_empty=True)

    llm_provider: Literal["gemini", "openai_compatible"] = "gemini"
    llm_api_key: SecretStr | None = Field(None, validation_alias=AliasChoices("LLM_API_KEY"))
    llm_model: str = Field("", validation_alias=AliasChoices("LLM_MODEL"))
    llm_fallback_model: str = Field("", validation_alias=AliasChoices("LLM_FALLBACK_MODEL"))
    # Step 0 names: used ONLY when the provider is gemini (a Gemini key must never go to another server)
    gemini_api_key: SecretStr | None = Field(None, validation_alias=AliasChoices("GEMINI_API_KEY"), exclude=True)
    gemini_model: str = Field("", validation_alias=AliasChoices("GEMINI_MODEL"), exclude=True)
    gemini_fallback_model: str = Field("", validation_alias=AliasChoices("GEMINI_FALLBACK_MODEL"), exclude=True)
    llm_base_url: str = ""          # openai_compatible only, e.g. http://gpu-server:8000/v1
    llm_extra_body: Annotated[dict, NoDecode] = Field(default_factory=dict)  # extra request fields, e.g. Qwen: thinking off

    data_dir: Path = ROOT / "data"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @field_validator("llm_provider", mode="before")
    @classmethod
    def _tidy(cls, v):
        return v.strip().lower() if isinstance(v, str) else v

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper(cls, v):
        return v.strip().upper() if isinstance(v, str) else v

    @field_validator("llm_api_key", "gemini_api_key", mode="before")
    @classmethod
    def _key(cls, v, info):
        if isinstance(v, str) and not v.strip():
            raise ValueError(f"{ENV_NAME.get(info.field_name, info.field_name.upper())} is empty")
        return v

    @field_validator("llm_model", "llm_fallback_model", "llm_base_url", "gemini_model", "gemini_fallback_model",
                     mode="before")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else ("" if v is None else v)

    @field_validator("llm_extra_body", mode="before")
    @classmethod
    def _json(cls, v):
        if isinstance(v, str):
            if not v.strip():
                return {}
            try:
                v = json.loads(v)
            except ValueError:
                raise ValueError("LLM_EXTRA_BODY must be JSON, e.g. {\"chat_template_kwargs\": {\"enable_thinking\": false}}") from None
        if not isinstance(v, dict):
            raise ValueError("LLM_EXTRA_BODY must be a JSON object")
        return v

    @model_validator(mode="after")
    def _per_provider(self) -> Settings:
        if self.llm_provider == "gemini":
            self.llm_api_key = self.llm_api_key or self.gemini_api_key
            if self.llm_api_key is None:
                raise ValueError("LLM_API_KEY is missing (the old name GEMINI_API_KEY also works)")
            self.llm_model = self.llm_model or self.gemini_model or GEMINI_DEFAULT_MODEL
            self.llm_fallback_model = (self.llm_fallback_model or self.gemini_fallback_model
                                       or GEMINI_DEFAULT_FALLBACK_MODEL)
        else:
            if not self.llm_base_url:
                raise ValueError("LLM_BASE_URL is missing (the server address, e.g. http://gpu-server:8000/v1)")
            if not urlsplit(self.llm_base_url).scheme in ("http", "https") or not urlsplit(self.llm_base_url).hostname:
                raise ValueError("LLM_BASE_URL must be an http(s) address, e.g. http://gpu-server:8000/v1")
            try:
                urlsplit(self.llm_base_url).port
            except ValueError:
                raise ValueError("LLM_BASE_URL has an invalid port") from None
            if not self.llm_model:
                raise ValueError("LLM_MODEL is missing (the model name the server uses)")
        self.gemini_api_key = None          # never kept around for another provider
        self.llm_base_url = self.llm_base_url.rstrip("/")
        return self

    @property
    def models(self) -> list[str]:
        return [m for m in (self.llm_model, self.llm_fallback_model) if m]


def load_settings(**overrides) -> Settings:
    """Load settings. Overrides are for tests (e.g. _env_file=None, llm_api_key=...)."""
    try:
        return Settings(**overrides)
    except SettingsError as e:  # a value that could not even be read (names the field, never its value)
        field = str(e).split('"')[1] if '"' in str(e) else "a setting"
        raise ConfigError(f"Settings problem: {ENV_NAME.get(field, field.upper())} could not be read. "
                          "Check max-final/.env (copy .env.example if it doesn't exist).") from None
    except ValidationError as e:
        problems = []
        for err in e.errors():
            loc = [str(p) for p in err["loc"]]
            name = ENV_NAME.get(loc[0], loc[0].upper()) if loc else ""
            msg = str(err.get("msg", "")).removeprefix("Value error, ")
            if err["type"] == "missing":
                problems.append(f"{name} is missing")
            elif msg and (not name or name in msg):
                problems.append(msg)                     # our own messages already name the setting
            else:
                problems.append(f"{name} is invalid")
        raise ConfigError("Settings problem: " + "; ".join(problems)
                          + ". Check max-final/.env (copy .env.example if it doesn't exist).") from None


class TeamsSettings(BaseSettings):
    """How Max connects to Teams. Kept apart from the AI settings: Max can start without an AI key.

    TEAMS_MODE = sim     the simulated Teams on this PC (default). Max listens on 127.0.0.1 only and accepts
                         unsigned messages (the simulator can't sign like Microsoft does).
    TEAMS_MODE = teams   real Microsoft Teams. Needs the app registration: CLIENT_ID, CLIENT_SECRET, TENANT_ID.
    BOT_PORT             where Max listens (default 3978).
    """

    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore",
                                      populate_by_name=True, env_ignore_empty=True)

    teams_mode: Literal["sim", "teams"] = "sim"
    bot_port: int = Field(3978, ge=1, le=65535)
    client_id: str = ""
    client_secret: SecretStr | None = None
    tenant_id: str = ""

    @field_validator("teams_mode", mode="before")
    @classmethod
    def _tidy(cls, v):
        return v.strip().lower() if isinstance(v, str) else v

    @model_validator(mode="after")
    def _registration(self) -> TeamsSettings:
        if self.teams_mode == "teams":
            missing = [n for n, v in (("CLIENT_ID", self.client_id), ("CLIENT_SECRET", self.client_secret),
                                      ("TENANT_ID", self.tenant_id)) if not v]
            if missing:
                raise ValueError(f"{', '.join(missing)} missing (needed for TEAMS_MODE=teams)")
        return self

    @property
    def bot_host(self) -> str:
        return "127.0.0.1" if self.teams_mode == "sim" else "0.0.0.0"


def load_teams_settings(**overrides) -> TeamsSettings:
    try:
        return TeamsSettings(**overrides)
    except SettingsError:
        raise ConfigError("Teams settings problem: a Teams setting could not be read. Check max-final/.env.") from None
    except ValidationError as e:
        problems = []
        for err in e.errors():
            msg = str(err.get("msg", "")).removeprefix("Value error, ")
            name = str(err["loc"][0]).upper() if err["loc"] else ""
            problems.append(msg if not name else f"{name} is invalid")   # our own messages already name the setting
        raise ConfigError("Teams settings problem: " + "; ".join(problems) + ". Check max-final/.env.") from None


def safe_url(url: str) -> str:
    """The address without any user:password part (that would be a secret)."""
    parts = urlsplit(url)
    if parts.username or parts.password:
        host = parts.hostname or ""
        netloc = f"***@{host}" + (f":{parts.port}" if parts.port else "")
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    return url


def describe(settings: Settings, limits_store=None) -> str:
    """A readable summary of the settings and limits in use (keys hidden)."""
    from limits import LimitsStore

    store = limits_store or LimitsStore()
    lim = store.get()
    lines = ["AI provider", f"  provider        {settings.llm_provider}",
             f"  API key         {'set (hidden)' if settings.llm_api_key else 'none'}",
             f"  main model      {settings.llm_model}",
             f"  backup model    {settings.llm_fallback_model or '(none)'}"]
    if settings.llm_provider == "openai_compatible":
        lines.append(f"  server          {safe_url(settings.llm_base_url)}")
        if settings.llm_extra_body:
            lines.append(f"  extra fields    {', '.join(settings.llm_extra_body)} (values hidden)")
    lines += ["", f"Limits ({store.defaults_file.name} + {store.user_file})"]
    for section, values in lim.model_dump().items():
        lines.append(f"  [{section}]")
        lines += [f"    {k:<28} {v}" for k, v in values.items()]
    if store.problem:
        lines += ["", f"  PROBLEM: {store.problem}"]
    lines += ["", f"Data folder: {settings.data_dir}  ·  log level: {settings.log_level}"]
    return "\n".join(lines)


def main() -> None:
    import sys

    try:
        print(describe(load_settings()))
    except ConfigError as e:
        print(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
