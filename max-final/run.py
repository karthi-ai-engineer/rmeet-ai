"""
One command for everything (standard library only, so it works before anything is installed).

  python run.py setup       create .venv and install requirements.txt (only when it changed)
  python run.py test        all offline tests (free, no keys needed)
  python run.py check       live check with the real AI settings (costs a fraction of a cent)
  python run.py settings    show the AI provider, models and every limit in use (keys hidden)
  python run.py dashboard   AI usage dashboard on http://localhost:8600

More commands (start, stop, e2e) arrive with later steps.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
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


COMMANDS = {
    "setup": lambda: 0,
    "test": lambda: run_py("-m", "pytest"),
    "check": lambda: run_py("-m", "max.llm.check"),
    "settings": lambda: run_py("-m", "max.config"),
    "dashboard": lambda: run_py("-m", "ai_usage.dashboard"),
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
