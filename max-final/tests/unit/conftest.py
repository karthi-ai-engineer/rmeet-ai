"""Shared test helpers: a fake model backend, a fake clock, a throwaway usage meter. No network, no cost."""

from __future__ import annotations

import pytest

from ai_usage import Meter
from max.llm import LLM, BackendError, Result


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds

    slept: list


class FakeBackend:
    """Plays a script per model. Each step: a str (answer), a BackendError (raised), or ('slow', seconds)."""

    def __init__(self, clock: FakeClock, script: dict[str, list]):
        self.clock, self.script = clock, {m: list(steps) for m, steps in script.items()}
        self.calls: list[str] = []

    async def generate(self, model, prompt, system, max_output_tokens, timeout_s):
        self.calls.append(model)
        steps = self.script.get(model) or [BackendError("not_found", 404)]
        step = steps.pop(0) if len(steps) > 1 else steps[0]
        if isinstance(step, tuple) and step[0] == "slow":
            import asyncio
            await asyncio.sleep(step[1])          # real (short) delay so asyncio.wait_for can time out
            return Result("late answer", {"in": 10, "out": 2})
        if isinstance(step, BackendError):
            self.clock.now += 0.2
            raise step
        self.clock.now += 0.5
        return Result(step, {"in": 100, "out": 20})


@pytest.fixture(autouse=True)
def own_limits_file(tmp_path, monkeypatch):
    """Tests never read or change the real data/limits.toml."""
    monkeypatch.setenv("LIMITS_FILE", str(tmp_path / "limits.toml"))
    monkeypatch.delenv("AI_USAGE_DIR", raising=False)


@pytest.fixture
def clock():
    c = FakeClock()
    c.slept = []
    return c


@pytest.fixture
def meter(tmp_path):
    return Meter(tmp_path / "ai_usage")


@pytest.fixture
def make_llm(clock, meter):
    def make(script: dict, models=("main", "backup"), **kw):
        backend = FakeBackend(clock, script)
        llm = LLM(backend, meter, list(models), sleep=clock.sleep, clock=clock, **kw)
        return llm, backend
    return make
