"""
Max's settings, read from the root .env file (and environment variables, which win).

  settings = load_settings()      raises ConfigError with a clear message if something is missing

Secrets are SecretStr: printing settings never shows them. Error messages name the setting, never its value.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_MODEL = "gemini-3.1-flash-lite"
DEFAULT_FALLBACK_MODEL = "gemini-3.5-flash-lite"


class ConfigError(Exception):
    """A setting is missing or invalid. The message is safe to show (no secret values)."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: SecretStr
    gemini_model: str = DEFAULT_MODEL
    gemini_fallback_model: str = DEFAULT_FALLBACK_MODEL

    llm_timeout_s: float = Field(20.0, gt=0)    # one model call
    llm_deadline_s: float = Field(60.0, gt=0)   # everything ask() does, retries and backup included
    llm_max_wait_s: float = Field(5.0, ge=0)    # longest wait for a rate limit before switching to the backup

    data_dir: Path = ROOT / "data"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper(cls, v):
        return v.strip().upper() if isinstance(v, str) else v

    @field_validator("gemini_api_key")
    @classmethod
    def _key_not_empty(cls, v: SecretStr) -> SecretStr:
        if not v.get_secret_value().strip():
            raise ValueError("empty")
        return v

    @field_validator("gemini_model", mode="before")
    @classmethod
    def _model_default(cls, v):
        return v.strip() if isinstance(v, str) and v.strip() else DEFAULT_MODEL

    @field_validator("gemini_fallback_model", mode="before")
    @classmethod
    def _fallback_default(cls, v):
        return v.strip() if isinstance(v, str) and v.strip() else DEFAULT_FALLBACK_MODEL


def load_settings(**overrides) -> Settings:
    """Load settings. Overrides are for tests (e.g. _env_file=None)."""
    try:
        return Settings(**overrides)
    except ValidationError as e:
        problems = []
        for err in e.errors():
            name = ".".join(str(p) for p in err["loc"]).upper()
            if err["type"] == "missing":
                problems.append(f"{name} is missing")
            else:
                problems.append(f"{name} is invalid")
        raise ConfigError("Settings problem: " + "; ".join(problems)
                          + ". Check max-final/.env (copy .env.example if it doesn't exist).") from None
