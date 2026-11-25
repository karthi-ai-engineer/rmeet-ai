"""
One command to run the whole demo:  `run`  (Windows)  or  `python3 run.py`  (macOS / Linux)

  1. creates .venv and installs requirements.txt (only when it changed)
  2. checks voice-chat/.env has the keys (never prints them)
  3. refreshes Max's settings (simulations/teams/register_app.py -> max/.env)
  4. starts rmeet-ai (http://localhost:8100) and Max (port 3978), waits until both answer
  5. opens the browser; Ctrl+C stops both

Options:  --no-browser   don't open the browser
          --stop         stop a running demo (started by this script) and exit
Logs: logs/rmeet.log and logs/max.log (full); the console shows the important lines.
Uses only the Python standard library, so it works before anything is installed.
"""

import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WIN = os.name == "nt"
VENV = ROOT / ".venv"
PY = VENV / ("Scripts/python.exe" if WIN else "bin/python")
ENV_FILE = ROOT / "voice-chat" / ".env"
LOGS = ROOT / "logs"
PIDS = LOGS / "pids.json"
RMEET_PORT = int(os.environ.get("RMEET_PORT", "8100"))

# Console filter: keep what a presenter cares about, drop per-request noise (it stays in the log files).
NOISE = re.compile(r'"(GET|POST|PUT|PATCH|DELETE) [^"]*" (2\d\d|304)|HTTP Request: |INFO: +127\.0\.0\.1|'
                   r'Uvicorn running|Waiting for application|Application startup complete|Started server process|'
                   r'ExperimentalWarning|DEFAULT_SECURITY_POLICY|HtmlWidgetSecurityPolicy|warnings\.warn|'
                   r'DeprecationWarning|on_event is deprecated|Read more about it|Lifespan Events|@web\.on_event|^\s*$')


def say(msg: str) -> None:
    print(f"[run] {msg}", flush=True)


def fail(msg: str) -> None:
    say("✗ " + msg)
    sys.exit(1)


# ------------------------------------------------------------------ setup
def ensure_venv() -> None:
    if sys.version_info < (3, 12):
        fail(f"Python 3.12 or newer is needed (this is {sys.version.split()[0]}). Install it from python.org.")
    if not PY.exists():
        say("Creating the Python environment (.venv) …")
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
    req = (ROOT / "requirements.txt").read_bytes()
    stamp = VENV / ".requirements.sha1"
    digest = hashlib.sha1(req).hexdigest()
    if not stamp.exists() or stamp.read_text().strip() != digest:
        say("Installing libraries (first time or requirements changed, takes a few minutes) …")
        r = subprocess.run([str(PY), "-m", "pip", "install", "-q", "--disable-pip-version-check",
                            "-r", str(ROOT / "requirements.txt")])
        if r.returncode:
            fail("Installing libraries failed (see the messages above).")
        stamp.write_text(digest)


def read_env(path: Path) -> dict:
    out = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def check_keys() -> dict:
    if not ENV_FILE.exists():
        example = ENV_FILE.with_name(".env.example")
        ENV_FILE.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        fail(f"Created {ENV_FILE.relative_to(ROOT)} from the example. Paste your keys into it, then run again.")
    env = read_env(ENV_FILE)
    real = lambda k: bool(env.get(k)) and not env[k].startswith("paste-")
    brain = env.get("BRAIN_PROVIDER", "qwen").lower()                 # the simulated colleagues
    max_brain = env.get("MAX_BRAIN_PROVIDER", brain).lower()           # Max (MAX_ overrides apply to Max only)
    name = lambda b, model: f"Gemini ({model})" if b == "gemini" else "company Qwen"
    missing = []
    if not real("GEMINI_API_KEY"):                                     # Max's hearing is always Gemini
        missing.append("GEMINI_API_KEY")
    if "qwen" in (brain, max_brain):
        missing += [k for k in ("TW_API_KEY", "TW_BASE_URL") if not real(k)]
    if missing:
        fail(f"Missing in voice-chat/.env: {', '.join(missing)}")
    gem = env.get("GEMINI_BRAIN_MODEL", "gemini-3.1-flash-lite")
    say(f"Keys found · Max: {name(max_brain, env.get('MAX_GEMINI_BRAIN_MODEL', gem))} · "
        f"colleagues: {name(brain, gem)} · voices: {env.get('TTS_PROVIDER', 'gemini')}")
    return env


def refresh_max_settings() -> None:
    say("Refreshing Max's app registration and settings (max/.env) …")
    r = subprocess.run([str(PY), str(ROOT / "simulations" / "teams" / "register_app.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        print(r.stdout + r.stderr)
        fail("register_app.py failed.")


# ------------------------------------------------------------------ processes
def http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def port_busy(port: int) -> bool:
    import socket
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def kill(pid: int) -> None:
    try:
        if WIN:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        pass


def is_python(pid: int) -> bool:
    """Only stop processes that are still Python: a saved id may belong to another program by now."""
    try:
        if WIN:
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                                 capture_output=True, text=True).stdout.lower()
            return "python" in out
        return "python" in Path(f"/proc/{pid}/cmdline").read_text().lower() if Path("/proc").exists() else True
    except OSError:
        return False


def stop_previous() -> bool:
    if not PIDS.exists():
        return False
    for pid in json.loads(PIDS.read_text()).values():
        if is_python(pid):
            kill(pid)
    PIDS.unlink(missing_ok=True)
    time.sleep(1)
    return True


def start(name: str, script: Path | list, cwd: Path, python: Path = PY) -> subprocess.Popen:
    LOGS.mkdir(exist_ok=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    args = [str(python)] + ([str(script)] if isinstance(script, Path) else list(script))
    proc = subprocess.Popen(args, cwd=str(cwd), env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if WIN else 0)

    def pump():
        with open(LOGS / f"{name}.log", "a", encoding="utf-8") as log:
            log.write(f"\n===== started {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
            for line in proc.stdout:
                log.write(line)
                log.flush()
                if not NOISE.search(line):
                    print(f"[{name}] {line.rstrip()}", flush=True)

    threading.Thread(target=pump, daemon=True).start()
    return proc


def wait_ready(name: str, proc: subprocess.Popen, url: str, timeout: float = 90) -> None:
    t = time.time()
    while time.time() - t < timeout:
        if proc.poll() is not None:
            fail(f"{name} stopped while starting (see logs/{name}.log).")
        if http_ok(url):
            say(f"✓ {name} is ready ({time.time() - t:.0f}s)")
            return
        time.sleep(0.5)
    fail(f"{name} did not become ready in {timeout:.0f}s (see logs/{name}.log).")


def main() -> None:
    os.chdir(ROOT)
    if "--stop" in sys.argv:
        say("Stopped the running demo." if stop_previous() else "Nothing to stop.")
        return
    ensure_venv()
    env = check_keys()
    if stop_previous():
        say("Closed the demo that was still running from before.")
    refresh_max_settings()
    max_port = int(read_env(ROOT / "max" / ".env").get("PORT", "3978"))
    for port, what in ((RMEET_PORT, "rmeet-ai"), (max_port, "Max")):
        if port_busy(port):
            fail(f"Port {port} ({what}) is already in use by another program. Close it, or run `run --stop`.")

    procs: dict[str, subprocess.Popen] = {}

    def launch(name, script, url, cwd=ROOT, python=PY, timeout=90):
        procs[name] = start(name, script, cwd, python)
        PIDS.write_text(json.dumps({n: p.pid for n, p in procs.items()}))
        wait_ready(name, procs[name], url, timeout)

    # Optional, per machine (not in git): Gemini usage dashboard, local voice server.
    dash = ROOT / "gemini_usage" / "dashboard.py"
    if dash.exists() and not port_busy(8600):
        launch("usage", ["-m", "gemini_usage.dashboard"], "http://127.0.0.1:8600/api/usage")
    if env.get("TTS_PROVIDER", "gemini").lower() == "local":
        tts_url = env.get("LOCAL_TTS_URL", "http://127.0.0.1:8400").rstrip("/")
        tts_py = ROOT / "local_tts" / ".venv" / ("Scripts/python.exe" if WIN else "bin/python")
        if http_ok(tts_url + "/health"):
            say("✓ local voice server already running")
        elif tts_py.exists():
            launch("voices", ROOT / "local_tts" / "server.py", tts_url + "/health", ROOT / "local_tts", tts_py, 180)
        else:
            say(f"! TTS_PROVIDER=local but no voice server at {tts_url} (local_tts/ not set up): "
                "people will use the browser's backup voice")

    launch("rmeet", ROOT / "simulations" / "rmeet" / "server.py", f"http://127.0.0.1:{RMEET_PORT}/api/channel")
    launch("max", ROOT / "max" / "app.py", f"http://127.0.0.1:{max_port}/health")

    url = f"http://localhost:{RMEET_PORT}"
    print("\n" + "=" * 60)
    say(f"Demo is running →  {url}")
    say(f"Max admin page   →  http://localhost:{max_port}/admin")
    if "usage" in procs:
        say("Gemini usage     →  http://localhost:8600")
    say("Press Ctrl+C to stop everything.")
    print("=" * 60 + "\n", flush=True)
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
        if "usage" in procs:
            webbrowser.open("http://localhost:8600")

    try:
        while True:
            for name, p in procs.items():
                if p.poll() is not None:
                    if not PIDS.exists():
                        say("Stopped from another window (run --stop).")
                    else:
                        say(f"✗ {name} stopped unexpectedly (exit {p.returncode}); see logs/{name}.log. "
                            "Stopping the demo.")
                    raise KeyboardInterrupt
            time.sleep(1)
    except KeyboardInterrupt:
        say("Stopping …")
        for p in reversed(list(procs.values())):
            kill(p.pid)
        PIDS.unlink(missing_ok=True)
        say("Stopped.")


if __name__ == "__main__":
    main()
