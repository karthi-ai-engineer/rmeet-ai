"""Phase 3 end-to-end: Max joins the Teams channel meeting through the calling contracts (text + voice)."""
import json, sys, time, urllib.parse, urllib.request, urllib.error
from pathlib import Path

SIM, MAX = "http://127.0.0.1:8100", "http://127.0.0.1:3978"
REG = json.loads((Path(__file__).resolve().parents[1] / "simulations" / "teams" / "state" / "registration.json").read_text())
ok_all = True
do_voice = "--voice" in sys.argv
only_voice = "--only-voice" in sys.argv

def check(name, cond, detail=""):
    global ok_all
    ok_all &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail != "" else ""), flush=True)

def http(method, url, body=None, headers=None, form=None):
    data, h = None, dict(headers or {})
    if form is not None:
        data = urllib.parse.urlencode(form).encode(); h["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode(); h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            b = r.read()
            return r.status, (json.loads(b) if b and b[:1] in b"{[" else b)
    except urllib.error.HTTPError as e:
        b = e.read()
        return e.code, (json.loads(b) if b and b[:1] in b"{[" else b)

for _ in range(60):
    try:
        if http("GET", MAX + "/health")[0] == 200 and http("GET", SIM + "/api/channel")[0] == 200: break
    except Exception: pass
    time.sleep(0.5)

def token():
    s, b = http("POST", f"{SIM}/login/{REG['tenantId']}/oauth2/v2.0/token", form={"grant_type": "client_credentials",
        "client_id": REG["appId"], "client_secret": REG["clientSecret"], "scope": "https://graph.microsoft.com/.default"})
    return b["access_token"]

def channel(): return http("GET", SIM + "/api/channel")[1]
def events(): return http("GET", SIM + "/api/history")[1]["events"]
def status(): return http("GET", SIM + "/api/meeting")[1]["status"]

def wait_for(pred, timeout=180, every=2):
    t = time.time()
    while time.time() - t < timeout:
        r = pred()
        if r: return r, time.time() - t
        time.sleep(every)
    return None, timeout

def stop_meeting():
    if status() in ("live", "summarizing"):
        http("POST", SIM + "/api/meeting/stop", {})
        wait_for(lambda: status() not in ("live", "summarizing") or None, 240)

def meeting_post():
    return next((p for p in reversed(channel()["posts"]) if p.get("meeting")), None)

def run_meeting(media, speed, timeout):
    stop_meeting()
    s, b = http("POST", SIM + "/api/meeting/start", {"mode": "autopilot", "speed": speed, "media": media})
    check(f"[{media}] autopilot meeting started", s == 200, b if s != 200 else "")
    joined, dt = wait_for(lambda: any(e["type"] == "call" and e.get("state") == "established" for e in events()) or None, 60, 1)
    check(f"[{media}] Max joined the call (meetingStart -> /v1/meetings -> POST /communications/calls -> media)", joined, f"{dt:.0f}s")
    rec, _ = wait_for(lambda: any(e["type"] == "recording" and e["status"] == "recording" for e in events()) or None, 30, 1)
    check(f"[{media}] Max set updateRecordingStatus = recording (banner shown)", rec)
    mp = meeting_post()
    check(f"[{media}] 'meeting started' post in the channel is live", mp and mp["meeting"]["state"] == "live")
    t0 = time.time()
    ended, dt = wait_for(lambda: status() == "ended" or None, timeout, 5)
    check(f"[{media}] meeting finished", ended, f"{dt:.0f}s")
    ev = events()
    return ev, meeting_post()

# ---------------- clean start + install (new RSC) ----------------
http("POST", SIM + "/api/channel/reset", {})
time.sleep(2)
http("POST", SIM + "/api/admin", {"consent": False, "accessPolicy": True, "transcriptApiAccess": True})
http("POST", MAX + "/test/tokens/reset", {})   # Max picks up the revoked consent with a new token (test hook)
http("POST", SIM + "/api/channel/install", {"action": "add"})
welcome, dt = wait_for(lambda: next((p for p in channel()["posts"] if p["isBot"]), None), 120)
check("Max installed and welcomed", welcome is not None, f"{dt:.0f}s")
inst = channel().get("install") or {}
check("install granted RSC ChannelMeeting.ReadBasic.Group", "ChannelMeeting.ReadBasic.Group" in json.dumps(inst), "")

# ---------------- security contracts ----------------
s, b = http("POST", SIM + "/graph/v1.0/communications/calls", {"callbackUri": "https://x"}, {"Authorization": f"Bearer {token()}"})
check("POST /communications/calls without admin consent -> 403", s == 403, s)
s, _ = http("POST", MAX + "/api/calling", {"value": []}, {"Authorization": "Bearer not-a-real-token"})
check("Max rejects a call notification with a forged token -> 401", s == 401, s)
s, _ = http("GET", SIM + "/media/whatever")
check("media relay refuses connections without a valid app token", s in (401, 404), s)

if not only_voice:
    # ---------------- no consent: Max tells the meeting why it can't join ----------------
    stop_meeting()
    http("POST", SIM + "/api/meeting/start", {"mode": "autopilot", "speed": 8, "media": "text"})
    got, dt = wait_for(lambda: (mp := meeting_post()) and any(r["isBot"] and "couldn't join" in r["text"] for r in mp["replies"]) or None, 60, 2)
    check("without consent Max explains in the meeting chat that an admin must grant calling permissions", got, f"{dt:.0f}s")
    stop_meeting()

http("POST", SIM + "/api/admin", {"consent": True})

if not only_voice:
    # ---------------- text mode (Work IQ-style transcript; answers in the meeting chat) ----------------
    ev, mp = run_meeting("text", 8, 900)
    chat_answers = [e for e in ev if e["type"] == "utterance" and e["speaker"] == "max"]
    check("[text] Max answered questions in the meeting chat", len(chat_answers) >= 3, len(chat_answers))
    for a in chat_answers[:6]:
        print("    Max:", a["text"][:150])
    check("[text] the meeting post shows 'ended'", mp and mp["meeting"]["state"] == "ended")
    notes = mp and next((r for r in mp["replies"] if r["isBot"] and r["text"].lstrip("* ").startswith("📝 Meeting notes")), None)
    check("[text] Max posted the meeting notes in the meeting thread", notes is not None)
    sc = next((e["result"] for e in ev if e["type"] == "score"), None)
    check("[text] notes scored against the answer key", sc is not None, f"{sc['score']}/{sc['out_of']} ({sc['percent']}%)" if sc else "")
    if sc:
        for it in sc["items"]:
            if it["points"] < it["max"]:
                print("    missed:", it["section"], "|", it["item"][:100], "| Max said:", (it.get("answer") or "")[:100])
    errs = [e["message"] for e in ev if e["type"] == "error"]
    check("[text] no errors during the meeting", not errs, errs[:3])
    gt, dt = wait_for(lambda: any("callTranscript created" in l["what"] for l in http("GET", SIM + "/api/admin")[1]["log"]) or None, 60)
    check("[text] official transcript published to Graph afterwards", gt)

if do_voice or only_voice:
    # ---------------- voice mode (real audio frames both ways) ----------------
    ev, mp = run_meeting("voice", 1, 2400)
    clips = [e for e in ev if e["type"] == "utterance" and e["speaker"] != "max" and e.get("audio")]
    people = [e for e in ev if e["type"] == "utterance" and e["speaker"] != "max"]
    check("[voice] people spoke with real voices (TTS)", len(clips) >= len(people) - 1 and clips, f"{len(clips)}/{len(people)}")
    spoken = [e for e in ev if e["type"] == "utterance" and e["speaker"] == "max" and e.get("played")]
    check("[voice] Max answered OUT LOUD through the call (audio uplink, captioned)", len(spoken) >= 3, len(spoken))
    for a in spoken[:6]:
        print("    Max (heard):", a["text"][:150])
    notes = mp and next((r for r in mp["replies"] if r["isBot"] and r["text"].lstrip("* ").startswith("📝 Meeting notes")), None)
    check("[voice] Max posted the meeting notes in the meeting thread", notes is not None)
    sc = next((e["result"] for e in ev if e["type"] == "score"), None)
    check("[voice] notes scored", sc is not None, f"{sc['score']}/{sc['out_of']} ({sc['percent']}%)" if sc else "")
    if sc:
        for it in sc["items"]:
            if it["points"] < it["max"]:
                print("    missed:", it["section"], "|", it["item"][:100], "| Max said:", (it.get("answer") or "")[:100])
    errs = [e["message"] for e in ev if e["type"] == "error"]
    print("    errors:", errs[:5])

print("\nPHASE 3:", "ALL PASS" if ok_all else "SOME FAILED")
