"""Phase 3 extra checks, text mode only (Qwen, no Gemini):
   live mode (you host and ask Max), ending the meeting early, Max remembering the meeting afterwards."""
import json, time, urllib.request, urllib.error

SIM, MAX = "http://127.0.0.1:8100", "http://127.0.0.1:3978"
ok_all = True


def check(name, cond, detail=""):
    global ok_all
    ok_all &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail != "" else ""), flush=True)


def http(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            b = r.read()
            return r.status, (json.loads(b) if b and b[:1] in b"{[" else b)
    except urllib.error.HTTPError as e:
        b = e.read()
        return e.code, (json.loads(b) if b and b[:1] in b"{[" else b)


def wait_for(pred, timeout=180, every=1.5):
    t = time.time()
    while time.time() - t < timeout:
        r = pred()
        if r:
            return r, time.time() - t
        time.sleep(every)
    return None, timeout


channel = lambda: http("GET", SIM + "/api/channel")[1]
events = lambda: http("GET", SIM + "/api/history")[1]["events"]
status = lambda: http("GET", SIM + "/api/meeting")[1]["status"]
meeting_post = lambda: next((p for p in reversed(channel()["posts"]) if p.get("meeting")), None)

for _ in range(60):
    try:
        if http("GET", MAX + "/health")[0] == 200 and http("GET", SIM + "/api/channel")[0] == 200:
            break
    except Exception:
        pass
    time.sleep(0.5)

# ---------- clean start: Max installed, all admin settings on ----------
http("POST", SIM + "/api/channel/reset", {})
time.sleep(2)
http("POST", SIM + "/api/admin", {"consent": True, "accessPolicy": True, "transcriptApiAccess": True})
http("POST", SIM + "/api/channel/install", {"action": "add"})
w, dt = wait_for(lambda: next((p for p in channel()["posts"] if p["isBot"]), None), 120)
check("Max installed", w is not None, f"{dt:.0f}s")

# ---------- live mode: you host ----------
s, b = http("POST", SIM + "/api/meeting/start", {"mode": "live", "media": "text"})
check("live meeting started (text mode)", s == 200, b if s != 200 else "")
j, dt = wait_for(lambda: any(e["type"] == "call" and e.get("state") == "established" for e in events()) or None, 60)
check("Max joined the call", j, f"{dt:.0f}s")


def my_turn(n):
    return wait_for(lambda: sum(1 for e in events() if e["type"] == "your_turn") >= n or None, 240)[0]


def max_answers():
    return [e for e in events() if e["type"] == "utterance" and e["speaker"] == "max"]


check("the meeting waits for the host's first turn", my_turn(1))
before = len(max_answers())
s, b = http("POST", SIM + "/api/meeting/say", {"text": "Morning all. Max, what H1 total did the CFO memo set as our target?"})
check("host line accepted", s == 200, b if s != 200 else "")
a, dt = wait_for(lambda: len(max_answers()) > before and max_answers()[-1], 90)
ans = (a or {}).get("text", "")
check("Max answers the host's question correctly (11,500K)", "11,500" in ans or "11.5" in ans, f"{dt:.0f}s | {ans[:160]}")

# A typed interjection outside your turn also reaches Max through the call.
time.sleep(3)
before = len(max_answers())
http("POST", SIM + "/api/meeting/say", {"text": "Max, quick one: how big is the gap in draft v2?"})
a, dt = wait_for(lambda: len(max_answers()) > before and max_answers()[-1], 120)
ans = (a or {}).get("text", "")
check("Max answers an interjection mid-meeting (220K gap)", "220" in ans, f"{dt:.0f}s | {ans[:160]}")

# ---------- end the meeting early (host clicks Leave) ----------
time.sleep(5)
http("POST", SIM + "/api/meeting/stop", {})
e, dt = wait_for(lambda: status() == "ended" or None, 240, 3)
check("meeting ended early", e, f"{dt:.0f}s")
mp = meeting_post()
check("the meeting post shows 'ended'", mp and mp["meeting"]["state"] == "ended")
notes = mp and next((r for r in mp["replies"] if r["isBot"] and "meeting notes" in r["text"].lower()[:80]), None)
check("Max still posted notes for the part that happened", notes is not None)
if notes:
    print("    " + notes["text"][:300].replace("\n", " | "))
term = [x for x in events() if x["type"] == "call" and x.get("state") == "terminated"]   # shown in the meeting view
check("the call was terminated cleanly (200/5001)", term and term[-1].get("subcode") == "5001",
      term[-1] if term else "")

# ---------- afterwards: Max remembers the meeting in the channel ----------
got, dt = wait_for(lambda: any("callTranscript created" in l["what"] for l in http("GET", SIM + "/api/admin")[1]["log"]) or None, 60)
check("official transcript published + notification sent to Max", got, f"{dt:.0f}s")
time.sleep(5)
s, m = http("POST", SIM + "/api/channel/post", {"text": "@Max in today's budget review, what did I ask you about the draft v2 gap?"})
rid = m["id"]
rep, dt = wait_for(lambda: next((r for p in channel()["posts"] if p["id"] == rid for r in p["replies"] if r["isBot"]), None), 150, 2)
ans = (rep or {}).get("text", "")
check("Max remembers today's meeting when asked in the channel",
      "gap" in ans.lower() and ("how big" in ans.lower() or "220" in ans), f"{dt:.0f}s | {ans[:200]}")

print("\nPHASE 3 LIVE + EDGES:", "ALL PASS" if ok_all else "SOME FAILED")
