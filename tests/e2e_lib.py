"""Shared helpers for the Phase 4 end-to-end tests (simulator on :8100, Max on :3978 with MAX_TEST_HOOKS=1)."""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SIM, MAX = "http://127.0.0.1:8100", "http://127.0.0.1:3978"
ROOT = Path(__file__).resolve().parents[1]
TEAM_ID = "63f889e6-d157-596a-a38f-ab4ca4e9efc5"
RESULTS = {"fails": 0}


def check(name: str, cond, detail="") -> bool:
    RESULTS["fails"] += not cond
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail != "" else ""), flush=True)
    return bool(cond)


def http(method: str, url: str, body=None, timeout: float = 60):
    data, h = None, {}
    if body is not None:
        data, h["Content-Type"] = json.dumps(body).encode(), "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            b = r.read()
            return r.status, (json.loads(b) if b and b[:1] in b"{[" else b)
    except urllib.error.HTTPError as e:
        b = e.read()
        return e.code, (json.loads(b) if b and b[:1] in b"{[" else b)


def wait_for(pred, timeout: float = 60, every: float = 1):
    t = time.time()
    while time.time() - t < timeout:
        r = pred()
        if r:
            return r, time.time() - t
        time.sleep(every)
    return None, timeout


def channel() -> dict:
    return http("GET", SIM + "/api/channel")[1]


def all_messages() -> list[dict]:
    out = []
    for p in channel()["posts"]:
        out.append(p)
        out.extend(p.get("replies", []))
    return out


def max_hook(method: str, path: str, body=None):
    return http(method, MAX + path, body)


def max_state() -> dict:
    return max_hook("GET", f"/test/state?teamId={TEAM_ID}")[1]


def wait_ready() -> None:
    for _ in range(60):
        try:
            if http("GET", MAX + "/health")[0] == 200 and http("GET", SIM + "/api/channel")[0] == 200:
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.5)
    s, _ = max_hook("GET", f"/test/state?teamId={TEAM_ID}")
    if s == 404:
        raise SystemExit("Max's test hooks are off: set MAX_TEST_HOOKS=1 in max/.env and restart Max")
    max_hook("POST", "/test/clock", {"reset": True})     # an earlier run may have stopped with Max's clock moved


def ensure_installed(fresh: bool = False) -> None:
    """Max installed in the channel (fresh=True: reset the channel and reinstall first)."""
    if fresh:
        http("POST", SIM + "/api/channel/reset", {})
        time.sleep(2)
    if not (channel().get("install") or {}).get("installed"):
        http("POST", SIM + "/api/channel/install", {"action": "add"})
        wait_for(lambda: next((p for p in channel()["posts"] if p["isBot"]), None), 120)
        time.sleep(1)


def post(text: str, root_id: str | None = None) -> dict:
    return http("POST", SIM + "/api/channel/post", {"text": text, "rootId": root_id})[1]


def gemini_requests() -> int:
    try:
        return sum(len(f.read_text(encoding="utf-8").splitlines())
                   for f in (ROOT / "gemini_usage" / "data").glob("usage-*.jsonl"))
    except OSError:
        return 0


def finish(name: str) -> None:
    print(f"\n{name}: ALL PASS" if not RESULTS["fails"] else f"\n{name}: {RESULTS['fails']} FAILED")
    raise SystemExit(1 if RESULTS["fails"] else 0)
