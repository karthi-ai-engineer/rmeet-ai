"""Quick check: colleague voice (TTS) -> 16 kHz frames -> Max hears it (STT) -> Max speaks (TTS). Needs a Gemini key."""
import sys, time
from pathlib import Path
ROOT = str(Path(__file__).resolve().parents[1])
sys.path[:0] = [f"{ROOT}/simulations/rmeet", f"{ROOT}/simulations/teams"]
import voices, audio as sim_audio
sys.path.insert(0, f"{ROOT}/max")
del sys.modules["audio"]          # Max has its own audio.py
import importlib
max_voice = importlib.import_module("voice")
max_calling_parse = importlib.import_module("calling").parse_join_url

text = "Honestly, the Riverside pilot with Vector Robotics would save about 105K in H1."
t = time.perf_counter(); wav = voices.synthesize(text, "Achird", "friendly"); print(f"TTS (Daniel/Achird): {time.perf_counter()-t:.1f}s, {len(wav)} bytes")
pcm = sim_audio.wav_to_pcm16k(wav); fr = sim_audio.frames(pcm)
print(f"16k PCM: {len(pcm)/32000:.2f}s audio, {len(fr)} frames of {len(fr[0])} bytes")
t = time.perf_counter(); heard = max_voice.listen(pcm, "Riverside, Vector Robotics"); print(f"Max STT: {time.perf_counter()-t:.1f}s -> {heard!r}")
ok = "riverside" in heard.lower() and "105" in heard
t = time.perf_counter(); mw = max_voice.speak("LiftLine's lead time was 14 weeks."); print(f"Max TTS (Charon): {time.perf_counter()-t:.1f}s, {len(mw)} bytes")
from urllib.parse import quote
url = "https://teams.microsoft.com/l/meetup-join/" + quote("19:meeting_abc@thread.v2", safe="") + "/0?context=" + quote('{"Tid":"t1","Oid":"o1"}')
p = max_calling_parse(url); print("join url ->", p)
print("PIPELINE:", "OK" if ok and p == {"threadId": "19:meeting_abc@thread.v2", "organizerId": "o1", "tenantId": "t1"} else "CHECK")
