"""Offline test (no Gemini calls): a 429 'quota exceeded' pauses TTS/STT instantly instead of retrying."""
import io
import sys
import time
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ok_all = True


def check(name, cond, detail=""):
    global ok_all
    ok_all &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail != "" else ""))


QUOTA = b'{"error":{"code":429,"message":"You exceeded your current quota","status":"RESOURCE_EXHAUSTED",' \
        b'"details":[{"@type":"type.googleapis.com/google.rpc.RetryInfo","retryDelay":"37s"}]}}'
calls = {"n": 0}


def fake_urlopen(req, timeout=None):
    calls["n"] += 1
    raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, io.BytesIO(QUOTA))


# ---------- simulator voices ----------
sys.path[:0] = [str(ROOT / "simulations" / "rmeet"), str(ROOT / "simulations" / "teams")]
import os
os.environ.setdefault("GEMINI_API_KEY", "test")
import voices                                                         # noqa: E402
voices.urllib.request.urlopen = fake_urlopen
t = time.perf_counter()
try:
    voices.synthesize(f"quota test {time.time()}", "Puck")
    check("simulator TTS raises on quota", False)
except voices.TTSError as e:
    check("simulator TTS raises on quota, without retries", calls["n"] == 1 and "quota" in str(e), f"{calls['n']} call(s), {e}")
check("it fails fast (no back-off sleeps)", time.perf_counter() - t < 1, f"{time.perf_counter() - t:.2f}s")
check("cooldown follows Google's retryDelay (37 s)", 35 < voices.cooldown_left() <= 37, f"{voices.cooldown_left():.0f}s")
try:
    voices.synthesize(f"second line {time.time()}", "Achird")
except voices.TTSError:
    pass
check("next line during the cooldown makes no request", calls["n"] == 1, calls["n"])

# ---------- Max (separate program, own copy) ----------
for m in ("audio", "llm", "config"):
    sys.modules.pop(m, None)
sys.path.insert(0, str(ROOT / "max"))
import importlib                                                       # noqa: E402
max_voice = importlib.import_module("voice")
max_voice.urllib.request.urlopen = fake_urlopen
calls["n"] = 0
try:
    max_voice.speak("hello")
except max_voice.VoiceError as e:
    check("Max TTS pauses on quota (falls back to chat)", calls["n"] == 1 and "quota" in str(e), e)
try:
    max_voice.listen(b"\x00" * 3200)
except max_voice.VoiceError:
    pass
check("Max hearing (STT) has its own quota (still tried)", calls["n"] == 2, calls["n"])
try:
    max_voice.speak("again")
except max_voice.VoiceError:
    pass
check("Max TTS during cooldown makes no request", calls["n"] == 2, calls["n"])

print("\nQUOTA GUARD:", "ALL PASS" if ok_all else "SOME FAILED")
sys.exit(0 if ok_all else 1)
