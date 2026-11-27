"""
One command for everything (standard library only, so it works before anything is installed).

  python run.py setup       create .venv and install requirements.txt (only when it changed)
  python run.py test        all offline tests (free, no keys needed)
  python run.py check       live check with the real AI settings (costs a fraction of a cent)
  python run.py settings    show the AI provider, models and every limit in use (keys hidden)
  python run.py dashboard   AI usage dashboard on http://localhost:8600
  python run.py start       start the simulated Teams + Max in the background (builds the screens if needed)
  python run.py stop        stop them
  python run.py e2e         end-to-end tests (starts its own copies on free ports; slower)
"""

from __future__ import annotations

import hashlib
import os
import signal
import subprocess
import sys
import time
import urllib.request
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
REQS = ROOT / "requirements.txt"
STAMP = VENV / ".requirements.sha256"


def say(msg: str) -> None:
    print(f"[run] {msg}", flush=True)


def child_env() -> dict:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"   # Windows consoles otherwise choke on non-ASCII
    env["PYTHONUTF8"] = "1"
    return env


def setup() -> None:
    if sys.version_info < (3, 12):
        sys.exit(f"Python 3.12+ needed, this is {sys.version.split()[0]}")
    if not PY.exists():
        say("creating .venv ...")
        venv.create(VENV, with_pip=True)
    want = hashlib.sha256(REQS.read_bytes()).hexdigest()
    have = STAMP.read_text().strip() if STAMP.exists() else ""
    if want != have:
        say("installing requirements.txt ...")
        subprocess.run([str(PY), "-m", "pip", "install", "-q", "--disable-pip-version-check", "-r", str(REQS)],
                       check=True, cwd=ROOT)
        STAMP.write_text(want)
    else:
        say("libraries up to date")
    env_file = ROOT / ".env"
    if not env_file.exists():
        say("no .env yet: copy .env.example to .env and paste your AI key")


def run_py(*args: str) -> int:
    return subprocess.run([str(PY), *args], cwd=ROOT, env=child_env()).returncode


# ---------------------------------------------------------------- start / stop
SIM_PORT, BOT_PORT = 5100, 3978
WEB = ROOT / "teams_sim" / "web"


def is_up(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1) as r:
            return r.status < 500
    except Exception:
        return False


def build_screens() -> None:
    """Build the Teams screens when the source is newer than the last build."""
    dist = WEB / "dist" / "index.html"
    newest = max(p.stat().st_mtime for p in [*(WEB / "src").rglob("*"), WEB / "index.html", WEB / "package.json"])
    if dist.exists() and dist.stat().st_mtime >= newest:
        return
    npm = "npm.cmd" if os.name == "nt" else "npm"
    if not (WEB / "node_modules").exists():
        say("installing the screens' libraries (npm ci) ...")
        subprocess.run([npm, "ci", "--silent"], cwd=WEB, check=True)
    say("building the screens ...")
    subprocess.run([npm, "run", "build", "--silent"], cwd=WEB, check=True, stdout=subprocess.DEVNULL)


OUR_MODULES = ("teams_sim.server", "max.app")


def listeners(port: int) -> set[int]:
    """Process ids listening on this local TCP port (IPv4 and IPv6; works in any Windows language)."""
    if os.name == "nt":
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, errors="replace").stdout
        found = set()
        for p in (line.split() for line in out.splitlines()):
            # TCP  <local>  <remote>  <state>  <pid>; a listening socket has no remote address ("...:0")
            if len(p) == 5 and p[0] == "TCP" and p[2].endswith(":0") and p[1].rsplit(":", 1)[-1] == str(port):
                found.add(int(p[4]))
        return found
    out = subprocess.run(["lsof", "-t", f"-iTCP:{port}", "-sTCP:LISTEN"], capture_output=True, text=True).stdout
    return {int(x) for x in out.split()}


def is_ours(pid: int) -> bool:
    """True only for our own two programs (python -m teams_sim.server / max.app), never another app on the port."""
    if os.name == "nt":
        cmd = ["powershell", "-NoProfile", "-Command",
               f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"]
    else:
        cmd = ["ps", "-p", str(pid), "-o", "args="]
    line = subprocess.run(cmd, capture_output=True, text=True, errors="replace").stdout
    return any(m in line for m in OUR_MODULES)


def start() -> int:
    sim_up = is_up(f"http://127.0.0.1:{SIM_PORT}/api/state?as=prince")
    max_up = is_up(f"http://127.0.0.1:{BOT_PORT}/health")
    if sim_up and max_up:
        say(f"already running: http://localhost:{SIM_PORT}")
        return 0
    busy = [port for port in (SIM_PORT, BOT_PORT) if listeners(port)]
    if busy:
        say(f"port {', '.join(map(str, busy))} is in use (half running, or another program). "
            "Run `python run.py stop` or free the port, then start again.")
        return 1
    build_screens()
    logs = ROOT / "data" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    env = {**child_env(), "TEAMS_SIM_PORT": str(SIM_PORT), "BOT_PORT": str(BOT_PORT),
           "MAX_BOT_URL": f"http://127.0.0.1:{BOT_PORT}/api/messages"}
    flags = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS) if os.name == "nt" else 0
    for name, module in (("teams_sim", "teams_sim.server"), ("max", "max.app")):
        out = open(logs / f"{name}.out", "a", encoding="utf-8")
        subprocess.Popen([str(PY), "-m", module], cwd=ROOT, env=env, stdout=out, stderr=subprocess.STDOUT,
                         creationflags=flags, start_new_session=os.name != "nt")
    for name, url in (("simulated Teams", f"http://127.0.0.1:{SIM_PORT}/api/state?as=prince"),
                      ("Max", f"http://127.0.0.1:{BOT_PORT}/health")):
        for _ in range(100):
            if is_up(url):
                break
            time.sleep(0.2)
        else:
            say(f"{name} did not start: see data/logs/ (teams_sim.out, max.out)")
            stop()
            return 1
    say(f"running. Open http://localhost:{SIM_PORT}   (stop: python run.py stop)")
    return 0


def stop() -> int:
    """Stops our two programs (found by their port, checked by their command line; never anything else)."""
    stopped = 0
    for name, port in (("simulated Teams", SIM_PORT), ("Max", BOT_PORT)):
        for pid in listeners(port):
            if not is_ours(pid):
                say(f"port {port} is used by another program (pid {pid}): left alone")
                continue
            try:
                os.kill(pid, signal.SIGTERM)
                stopped += 1
                say(f"stopped {name}")
            except OSError:
                pass
    if not stopped:
        say("nothing running")
    return 0


def e2e() -> int:
    build_screens()  # the browser tests must test the current screens
    return run_py("-m", "pytest", "tests/e2e")


COMMANDS = {
    "setup": lambda: 0,
    "test": lambda: run_py("-m", "pytest"),
    "check": lambda: run_py("-m", "max.llm.check"),
    "settings": lambda: run_py("-m", "max.config"),
    "dashboard": lambda: run_py("-m", "ai_usage.dashboard"),
    "start": start,
    "stop": stop,
    "e2e": e2e,
}


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd not in COMMANDS:
        print(__doc__)
        sys.exit(0 if cmd in ("help", "-h", "--help") else 2)
    setup()
    try:
        sys.exit(COMMANDS[cmd]())
    except KeyboardInterrupt:
        say("stopped")


if __name__ == "__main__":
    main()
