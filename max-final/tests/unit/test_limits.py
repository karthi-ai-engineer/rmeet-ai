"""The one limits file: defaults from limits.toml, own edits in data/limits.toml, re-read on change, never crash."""

import os
import time

import pytest

from limits import DEFAULTS_FILE, Limits, LimitsStore


def write(path, text):
    path.write_text(text, encoding="utf-8")
    # make sure the change is seen even on file systems with coarse timestamps
    st = path.stat()
    os.utime(path, (st.st_atime, st.st_mtime + 2))


def test_defaults_file_has_every_agreed_limit():
    lim = LimitsStore(user_file=None).get()
    assert lim.ai.daily_budget_usd == 1.0
    assert lim.ai.test_budget_usd_per_week == 5.0
    assert lim.messages.private_per_person_per_day == 3
    assert lim.messages.chases_per_task_per_day == 1
    assert lim.messages.follow_up_window_min == 10
    assert lim.jobs.active_per_person == 40
    assert lim.approvals.expire_after_h == 24
    assert lim.search.max_searches_per_question == 3
    assert lim.knowledge.history_window_days == 30
    assert lim.ai.model_timeout_s == 20 and lim.ai.answer_deadline_s == 60


def test_own_file_changes_only_the_lines_given(tmp_path):
    user = tmp_path / "limits.toml"
    write(user, "[ai]\ndaily_budget_usd = 2.5\n")
    store = LimitsStore(user_file=user)
    lim = store.get()
    assert lim.ai.daily_budget_usd == 2.5
    assert lim.jobs.active_per_person == 40          # untouched lines keep the default
    assert store.problem is None


def test_edit_applies_without_restart(tmp_path):
    user = tmp_path / "limits.toml"
    store = LimitsStore(user_file=user)
    assert store.get().jobs.active_per_person == 40
    write(user, "[jobs]\nactive_per_person = 55\n")
    assert store.get().jobs.active_per_person == 55


@pytest.mark.parametrize("text", [
    "[ai]\ndaily_budget_usd = -1\n",            # negative
    "[ai]\ndaily_budget_usd = \"lots\"\n",      # not a number
    "[ai\nbroken",                              # not TOML
    "[jobs]\nactive_per_person = 0\n",          # must be at least 1
])
def test_bad_own_file_gives_clear_message_and_keeps_working(tmp_path, text):
    user = tmp_path / "limits.toml"
    write(user, text)
    store = LimitsStore(user_file=user)
    lim = store.get()                                # never raises
    assert isinstance(lim, Limits)
    assert lim.ai.daily_budget_usd == 1.0            # defaults (or the last good values) stay in use
    assert store.problem and str(user.name) in store.problem


def test_bad_edit_keeps_the_last_good_values(tmp_path):
    user = tmp_path / "limits.toml"
    write(user, "[ai]\ndaily_budget_usd = 3\n")
    store = LimitsStore(user_file=user)
    assert store.get().ai.daily_budget_usd == 3
    write(user, "[ai]\ndaily_budget_usd = -5\n")
    assert store.get().ai.daily_budget_usd == 3
    assert "daily_budget_usd" in store.problem


def test_unknown_names_are_reported_not_ignored(tmp_path):
    user = tmp_path / "limits.toml"
    write(user, "[ai]\ndaily_budjet_usd = 2\n")      # typo
    store = LimitsStore(user_file=user)
    store.get()
    assert store.problem and "daily_budjet_usd" in store.problem


def test_update_writes_own_file_and_keeps_comments_out_of_git(tmp_path):
    user = tmp_path / "sub" / "limits.toml"
    store = LimitsStore(user_file=user)
    store.update({"ai": {"daily_budget_usd": 4.0}, "messages": {"follow_up_window_min": 15}})
    assert user.exists()
    again = LimitsStore(user_file=user).get()
    assert again.ai.daily_budget_usd == 4.0 and again.messages.follow_up_window_min == 15
    assert DEFAULTS_FILE.read_text(encoding="utf-8").count("daily_budget_usd = 1.0") == 1  # defaults untouched


def test_update_rejects_bad_values(tmp_path):
    store = LimitsStore(user_file=tmp_path / "limits.toml")
    with pytest.raises(ValueError) as e:
        store.update({"ai": {"daily_budget_usd": -2}})
    assert "daily_budget_usd" in str(e.value)
    assert store.get().ai.daily_budget_usd == 1.0


def test_reading_is_cheap(tmp_path):
    store = LimitsStore(user_file=tmp_path / "limits.toml")
    store.get()
    t0 = time.perf_counter()
    for _ in range(2000):
        store.get()
    assert time.perf_counter() - t0 < 1.0             # called before every AI call: must stay fast


# ---- review fixes (26 Nov 2026)
@pytest.mark.parametrize("data", ["# caf\xe9\n[ai]\ndaily_budget_usd = 2\n".encode("cp1252"),
                                  "[ai]\ndaily_budget_usd = 2\n".encode("utf-16")])
def test_file_not_saved_as_utf8_never_crashes(tmp_path, data):
    user = tmp_path / "limits.toml"
    user.write_bytes(data)
    store = LimitsStore(user_file=user)
    assert store.get().ai.daily_budget_usd == 1.0 and "UTF-8" in store.problem


def test_a_short_lock_is_not_remembered(tmp_path, monkeypatch):
    user = tmp_path / "limits.toml"
    write(user, "[ai]\ndaily_budget_usd = 2\n")
    store = LimitsStore(user_file=user)
    real = LimitsStore._user_raw
    calls = {"n": 0}

    def flaky(self):
        calls["n"] += 1
        if calls["n"] == 1:
            raise PermissionError("locked")
        return real(self)

    monkeypatch.setattr(LimitsStore, "_user_raw", flaky)
    assert store.get().ai.daily_budget_usd == 1.0 and store.problem     # locked: last good values
    assert store.get().ai.daily_budget_usd == 2.0 and store.problem is None   # next call reads it


def test_save_never_wipes_a_broken_own_file(tmp_path):
    user = tmp_path / "limits.toml"
    text = "[jobs]\nactive_per_person = 80\n[ai\nbroken"
    write(user, text)
    store = LimitsStore(user_file=user)
    with pytest.raises(ValueError):
        store.update({"ai": {"daily_budget_usd": 3.0}})
    assert user.read_text(encoding="utf-8") == text


def test_save_retries_while_the_file_is_locked(tmp_path, monkeypatch):
    import limits as limits_mod
    real = os.replace
    calls = {"n": 0}

    def locked_twice(a, b):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise PermissionError("in use")
        return real(a, b)

    monkeypatch.setattr(limits_mod.os, "replace", locked_twice)
    monkeypatch.setattr(limits_mod.time, "sleep", lambda s: None)
    store = LimitsStore(user_file=tmp_path / "limits.toml")
    assert store.update({"ai": {"daily_budget_usd": 2.0}}).ai.daily_budget_usd == 2.0


def test_save_gives_up_clearly_when_always_locked(tmp_path, monkeypatch):
    import limits as limits_mod

    def always(a, b):
        raise PermissionError("in use")

    monkeypatch.setattr(limits_mod.os, "replace", always)
    monkeypatch.setattr(limits_mod.time, "sleep", lambda s: None)
    store = LimitsStore(user_file=tmp_path / "limits.toml")
    with pytest.raises(limits_mod.LimitsSaveError) as e:
        store.update({"ai": {"daily_budget_usd": 2.0}})
    assert "in use" in str(e.value) and not (tmp_path / "limits.tmp").exists()


@pytest.mark.parametrize("text", ["[ai]\ndaily_budget_usd = inf\n", "[ai]\nanswer_deadline_s = 0.5\n"])
def test_infinite_or_useless_values_are_rejected(tmp_path, text):
    user = tmp_path / "limits.toml"
    write(user, text)
    store = LimitsStore(user_file=user)
    store.get()
    assert store.problem


def test_one_limits_file_for_everyone(tmp_path, monkeypatch):
    from ai_usage import Meter
    monkeypatch.setenv("AI_USAGE_DIR", str(tmp_path / "usage"))
    monkeypatch.setenv("LIMITS_FILE", str(tmp_path / "one.toml"))
    m = Meter()
    m.set_limits(daily_usd=4)
    assert LimitsStore().get().ai.daily_budget_usd == 4.0            # what `run.py settings` reads
