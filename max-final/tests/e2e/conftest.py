"""End-to-end runs: the simulated Teams and Max as two real programs talking over HTTP (free ports, own database).

Their output goes to log files (never to an unread pipe: a full pipe freezes the program, found 27 Nov 2026).
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_until_up(url: str, proc: subprocess.Popen, log: Path, seconds: float = 30) -> None:
    end = time.time() + seconds
    while time.time() < end:
        if proc.poll() is not None:
            raise RuntimeError(f"{url} exited early:\n{log.read_text(encoding='utf-8', errors='replace')[-3000:]}")
        try:
            if httpx.get(url, timeout=1).status_code < 500:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    raise RuntimeError(f"{url} did not start in {seconds} s")


@pytest.fixture(scope="session")
def running(tmp_path_factory):
    """Starts both programs once for the whole e2e run. Yields the simulator's base URL."""
    import run

    run.build_screens()  # always test the current screens, never an old build
    folder = tmp_path_factory.mktemp("run")
    sim_port, bot_port = free_port(), free_port()
    env = {**os.environ, "PYTHONUTF8": "1", "TEAMS_SIM_PORT": str(sim_port), "BOT_PORT": str(bot_port),
           "TEAMS_MODE": "sim", "MAX_BOT_URL": f"http://127.0.0.1:{bot_port}/api/messages",
           "TEAMS_SIM_DB": str(folder / "teams_sim.db")}
    procs, logs = [], []
    for name, module in (("teams_sim", "teams_sim.server"), ("max", "max.app")):
        log = folder / f"{name}.log"
        out = open(log, "w", encoding="utf-8")
        procs.append(subprocess.Popen([sys.executable, "-m", module], cwd=ROOT, env=env, stdout=out,
                                      stderr=subprocess.STDOUT))
        logs.append((log, out))
    try:
        wait_until_up(f"http://127.0.0.1:{sim_port}/api/state?as=prince", procs[0], logs[0][0])
        wait_until_up(f"http://127.0.0.1:{bot_port}/health", procs[1], logs[1][0])
        yield f"http://127.0.0.1:{sim_port}"
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(10)
            except subprocess.TimeoutExpired:
                p.kill()
        for _, out in logs:
            out.close()


@pytest.fixture
def sim(running):
    """A fresh start set for each test."""
    httpx.post(f"{running}/api/reset", json={}, timeout=10).raise_for_status()
    return running
