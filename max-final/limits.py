"""
Every limit in one place: limits.toml (starting values, in git) + data/limits.toml (own edits, per machine).

  store = LimitsStore()            one per program
  lim = store.get()                current values; re-reads the files when they change (no restart)
  lim.ai.daily_budget_usd          typed values, checked on load
  store.problem                    a clear message if the own file is wrong (then the last good values stay in use)
  store.update({"ai": {...}})      write changes to the own file (used by the dashboard / setup page)

Rule (Karthi, 26 Nov 2026): every price, budget and limit is a setting, never fixed in code.
This module imports nothing from max/ or ai_usage/: both use it.
"""

from __future__ import annotations

import math
import os
import threading
import time
import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

ROOT = Path(__file__).resolve().parent
DEFAULTS_FILE = ROOT / "limits.toml"
DEFAULT_USER_FILE = ROOT / "data" / "limits.toml"


def default_user_file() -> Path:
    """data/limits.toml, or LIMITS_FILE if set (one place for every program: Max, dashboard, settings)."""
    return Path(os.environ.get("LIMITS_FILE") or DEFAULT_USER_FILE)


class LimitsSaveError(OSError):
    """The own limits file could not be saved (e.g. locked by another program). The message is safe to show."""


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class AI(_Section):
    daily_budget_usd: float = Field(ge=0)
    daily_requests: int = Field(ge=0)
    test_budget_usd_per_week: float = Field(ge=0)
    model_timeout_s: float = Field(gt=0)
    answer_deadline_s: float = Field(ge=1)
    rate_limit_max_wait_s: float = Field(ge=0)


class Messages(_Section):
    private_per_person_per_day: int = Field(ge=0)
    chases_per_task_per_day: int = Field(ge=0)
    follow_up_window_min: float = Field(ge=0)


class Jobs(_Section):
    active_per_person: int = Field(ge=1)
    min_repeat_min: float = Field(ge=1)


class Approvals(_Section):
    expire_after_h: float = Field(gt=0)


class Search(_Section):
    max_searches_per_question: int = Field(ge=1)


class Knowledge(_Section):
    history_window_days: int = Field(ge=1)


class World(_Section):
    generation_budget_usd: float = Field(ge=0)


class Limits(_Section):
    ai: AI
    messages: Messages
    jobs: Jobs
    approvals: Approvals
    search: Search
    knowledge: Knowledge
    world: World


def _merge(base: dict, extra: dict) -> dict:
    out = {k: dict(v) if isinstance(v, dict) else v for k, v in base.items()}
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


def _describe(e: ValidationError) -> str:
    parts = []
    for err in e.errors():
        name = ".".join(str(p) for p in err["loc"])
        if err["type"] == "extra_forbidden":
            parts.append(f"{name} is not a known limit")
        else:
            parts.append(f"{name}: {err['msg'].lower()}")
    return "; ".join(parts)


def _to_toml(data: dict) -> str:
    lines = ["# Own limits for this machine (only the lines that differ from limits.toml).", ""]
    for section, values in data.items():
        lines.append(f"[{section}]")
        for k, v in values.items():
            lines.append(f"{k} = {v!r}" if isinstance(v, (int, float)) else f'{k} = "{v}"')
        lines.append("")
    return "\n".join(lines)


class LimitsStore:
    def __init__(self, user_file: Path | str | None | bool = True, defaults_file: Path | str = DEFAULTS_FILE):
        """user_file: True = the usual own file (data/limits.toml or LIMITS_FILE), None = defaults only."""
        self.defaults_file = Path(defaults_file)
        if user_file is True:
            user_file = default_user_file()
        self.user_file = Path(user_file) if user_file else None
        self.problem: str | None = None
        self._lock = threading.Lock()
        self._stamp: tuple | None = None
        self._defaults_raw = tomllib.loads(self.defaults_file.read_text(encoding="utf-8"))
        self._defaults = Limits.model_validate(self._defaults_raw)   # a broken defaults file is a bug: fail loudly
        self._current = self._defaults

    def _file_stamp(self) -> tuple:
        try:
            st = self.user_file.stat() if self.user_file else None
        except OSError:
            st = None
        return (st.st_mtime_ns, st.st_size) if st else (None, None)

    def _user_raw(self) -> dict:
        if not self.user_file or not self.user_file.exists():
            return {}
        return tomllib.loads(self.user_file.read_text(encoding="utf-8"))

    def get(self) -> Limits:
        stamp = self._file_stamp()
        if stamp == self._stamp:
            return self._current
        with self._lock:
            if stamp == self._stamp:
                return self._current
            name = self.user_file.name if self.user_file else "limits"
            try:
                self._current = Limits.model_validate(_merge(self._defaults_raw, self._user_raw()))
                self.problem = None
            except tomllib.TOMLDecodeError as e:
                self.problem = f"{name} is not valid TOML ({e}); using the last good values"
            except UnicodeDecodeError:
                self.problem = f"{name} is not saved as UTF-8 (save it as UTF-8); using the last good values"
            except ValidationError as e:
                self.problem = f"{name}: {_describe(e)}; using the last good values"
            except OSError as e:
                # often a short lock (antivirus, another program saving): try again on the next call
                self.problem = f"{name} could not be read ({e.__class__.__name__}); using the last good values"
                return self._current
            self._stamp = stamp
            return self._current

    def update(self, changes: dict) -> Limits:
        """Apply changes (section -> {name: value}), check them, then save the own file."""
        if not self.user_file:
            raise ValueError("no own limits file configured")
        try:
            own = self._user_raw()
        except (tomllib.TOMLDecodeError, UnicodeDecodeError):
            # never overwrite someone's own edits: they must fix the file first
            raise ValueError(f"{self.user_file.name} has an error; fix it first, then save again") from None
        except OSError as e:
            raise LimitsSaveError(f"{self.user_file.name} could not be read ({e.__class__.__name__})") from None
        for section, values in changes.items():
            for k, v in (values or {}).items():
                if isinstance(v, float) and not math.isfinite(v):
                    raise ValueError(f"{section}.{k}: must be a finite number")
        own = _merge(own, changes)
        try:
            new = Limits.model_validate(_merge(self._defaults_raw, own))
        except ValidationError as e:
            raise ValueError(_describe(e)) from None
        self.user_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.user_file.with_suffix(".tmp")
        tmp.write_text(_to_toml(own), encoding="utf-8")
        for attempt in range(6):                 # Windows: the file may be open for a moment elsewhere
            try:
                os.replace(tmp, self.user_file)
                break
            except PermissionError:
                if attempt == 5:
                    tmp.unlink(missing_ok=True)
                    raise LimitsSaveError(f"{self.user_file.name} is in use by another program; "
                                          "close it and save again") from None
                time.sleep(0.1)
        with self._lock:
            self._current, self.problem, self._stamp = new, None, self._file_stamp()
        return new
