"""Phase 2 end-to-end: Graph change notifications, files + delta, meetings/transcripts with admin gates, lifecycle recovery, live transcript."""
import base64, json, re, sys, time, urllib.parse, urllib.request, urllib.error
from pathlib import Path

SIM, MAX = "http://127.0.0.1:8100", "http://127.0.0.1:3978"
REG = json.loads((Path(__file__).resolve().parents[1] / "simulations" / "teams" / "state" / "registration.json").read_text())
# Subscription expiry times relative to now (a fixed date goes stale): > 1 hour and < 1 hour ahead
import datetime as _dt
EXP_LONG = (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
EXP_SHORT = (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(minutes=50)).strftime("%Y-%m-%dT%H:%M:%SZ")
ok_all = True
skip_meeting = "--no-meeting" in sys.argv

def check(name, cond, detail=""):
    global ok_all
    ok_all &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)

def http(method, url, body=None, headers=None, form=None, raw=False):
    data, h = None, dict(headers or {})
    if form is not None:
        data = urllib.parse.urlencode(form).encode(); h["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode(); h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            b = r.read()
            return r.status, (b.decode() if raw else (json.loads(b) if b and b[:1] in b"{[" else b))
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

def G(method, path, body=None, raw=False):
    return http(method, SIM + "/graph/v1.0" + path, body, {"Authorization": f"Bearer {token()}"}, raw=raw)

def channel(): return http("GET", SIM + "/api/channel")[1]

def wait_for(pred, timeout=180, every=2):
    t = time.time()
    while time.time() - t < timeout:
        r = pred()
        if r: return r, time.time() - t
        time.sleep(every)
    return None, timeout

def ask(text, root=None, timeout=150):
    s, m = http("POST", SIM + "/api/channel/post", {"text": text, "rootId": root})
    rid = root or m["id"]
    rep, dt = wait_for(lambda: next((r for p in channel()["posts"] if p["id"] == rid for r in p["replies"]
                                     if r["isBot"] and r["time"] >= m["time"]), None), timeout)
    return (rep or {}).get("text", ""), dt

# ---------------- clean start ----------------
http("POST", SIM + "/api/channel/reset", {})
time.sleep(2)
ch = channel()
team, chan = ch["ids"]["team"], ch["ids"]["channel"]
karthi_oid = None
check("transcript files are no longer channel files (only minutes)",
      not any("Transcript" in f["name"] for f in ch["files"]) and any("Minutes" in f["name"] for f in ch["files"]))

# ---------------- install: pre-read + subscriptions ----------------
http("POST", SIM + "/api/channel/install", {"action": "add"})
welcome, dt = wait_for(lambda: next((p for p in channel()["posts"] if p["isBot"]), None), 120)
check("Max installed, pre-read and welcomed", welcome is not None, f"{dt:.0f}s")
if welcome:
    print("   ", welcome["text"].replace("\n", " ")[:330])
    check("welcome tells the admin what is missing (calendar consent)", "admin" in welcome["text"].lower())
adm = http("GET", SIM + "/api/admin")[1]
kinds = sorted(s["resource"].split("/")[1] for s in adm["subscriptions"])
check("Max subscribed to channel messages + files (validation handshake passed)", len(adm["subscriptions"]) == 2, kinds)

# ---------------- Graph security / rules ----------------
s, b = G("GET", f"/teams/{team}/members"); karthi_oid = next(m["userId"] for m in b["value"] if m["displayName"] == "Karthi M")
s, b = G("GET", f"/users/{karthi_oid}/calendarView?startDateTime=2026-10-01T00:00:00Z&endDateTime=2026-12-01T00:00:00Z")
check("calendarView without admin consent -> 403", s == 403, s)
s, b = G("POST", "/subscriptions", {"changeType": "created", "notificationUrl": "http://127.0.0.1:9/nowhere", "resource": f"/teams/{team}/channels/{chan}/messages", "expirationDateTime": EXP_LONG})
check("subscription > 1 hour without lifecycleNotificationUrl -> 400", s == 400 and "lifecycleNotificationUrl" in json.dumps(b), s)
s, b = G("POST", "/subscriptions", {"changeType": "created", "notificationUrl": "http://127.0.0.1:9/nowhere", "lifecycleNotificationUrl": "http://127.0.0.1:9/lc", "resource": f"/teams/{team}/channels/{chan}/messages", "expirationDateTime": EXP_LONG})
check("duplicate subscription -> 409", s == 409, s)
s, b = G("POST", "/subscriptions", {"changeType": "created", "notificationUrl": "http://127.0.0.1:9/nowhere", "lifecycleNotificationUrl": "http://127.0.0.1:9/lc", "resource": f"/drives/x/root", "expirationDateTime": EXP_LONG})
check("subscription with unreachable / wrong resource rejected", s in (400, 404), s)
s, b = G("POST", "/subscriptions", {"changeType": "created", "notificationUrl": "http://127.0.0.1:9/nowhere", "resource": "/me/messages", "expirationDateTime": EXP_SHORT})
check("unsupported resource -> 400", s == 400, s)

http("POST", SIM + "/api/admin", {"consent": True})
s, b = G("GET", f"/users/{karthi_oid}/calendarView?startDateTime=2026-10-01T00:00:00Z&endDateTime=2026-12-01T00:00:00Z")
teams_meetings = [e for e in b.get("value", []) if e.get("isOnlineMeeting")] if isinstance(b, dict) else []
check("calendarView after admin consent -> 4 Teams meetings (plus everyday busy blocks)", s == 200 and len(teams_meetings) == 4, (s, len(teams_meetings)))
join = b["value"][1]["onlineMeeting"]["joinUrl"] if s == 200 else ""
s, b = G("GET", f"/users/{karthi_oid}/onlineMeetings?$filter=" + urllib.parse.quote(f"JoinWebUrl eq '{join}'"))
check("onlineMeetings without access policy -> 403 'No application access policy'", s == 403 and "access policy" in json.dumps(b), s)
http("POST", SIM + "/api/admin", {"accessPolicy": True})
s, b = G("GET", f"/users/{karthi_oid}/onlineMeetings?$filter=" + urllib.parse.quote(f"JoinWebUrl eq '{join}'"))
mid = b["value"][0]["id"] if s == 200 and b["value"] else None
check("onlineMeeting found by JoinWebUrl", mid is not None, s)
s, b = G("GET", f"/users/{karthi_oid}/onlineMeetings/{mid}/transcripts")
check("transcripts with tenant switch OFF -> 403 GraphAccessToTranscriptsDisabled", s == 403 and b["error"]["innerError"]["code"] == "GraphAccessToTranscriptsDisabled", s)

# ---------------- admin turns transcripts on: Max notices by itself ----------------
http("POST", SIM + "/api/admin", {"transcriptApiAccess": True})
s, b = G("GET", f"/users/{karthi_oid}/onlineMeetings/{mid}/transcripts")
tid = b["value"][0]["id"] if s == 200 and b.get("value") else None
s, vtt = G("GET", f"/users/{karthi_oid}/onlineMeetings/{mid}/transcripts/{tid}/content?$format=text/vtt", raw=True)
check("transcript content is WebVTT with speaker tags", s == 200 and vtt.startswith("WEBVTT") and "<v Prince Alex>" in vtt)
thanks, dt = wait_for(lambda: next((p for p in channel()["posts"] if p["isBot"] and "meeting access is working" in p["text"]), None), 200, 5)
check("Max noticed the admin fix and announced it (re-check job)", thanks is not None, f"{dt:.0f}s")
if thanks: print("   ", thanks["text"])
subs, _ = wait_for(lambda: len(http("GET", SIM + "/api/admin")[1]["subscriptions"]) >= 3 or None, 60)
check("Max added a transcript subscription (getAllTranscripts)", subs is not None)

# ---------------- transcript knowledge ----------------
ans, dt = ask("@Max in the 4 Nov meeting transcript, who asked whether Friday the thirteenth is a good date for a sale?")
check("answer uses the official transcript (speaker attribution)", "prince" in ans.lower() and "access" not in ans.lower(), f"{dt:.0f}s | {ans[:200]}")
ans, dt = ask("@Max according to the 20 Oct meeting transcript, who said 'Somebody will queue from the thirty-first with a sleeping bag' about the lucky bags?")
rest = ans.lower().split(",", 1)[-1]
check("second attribution question (Karthi said it)", ("karthi" in rest or "you" in rest) and not re.search(r"\bren\b", rest), f"{dt:.0f}s | {ans[:200]}")

# ---------------- file upload -> drive notification -> delta -> Max reads it ----------------
note = "# Second-supplier DRAM offer (19 Nov 2026)\n\nMika Sarah reports the second supplier confirmed a **monthly DDR5 contract** for Jan–Mar 2027: **12,500 × 16GB DIMMs per month** at **+17.5%** vs our Q4 price. Offer valid until 30 Nov 2026.\n"
s, b = http("POST", SIM + "/api/channel/upload", {"name": "14_Second_Supplier_DRAM_Offer.md", "data": base64.b64encode(note.encode()).decode()})
check("file uploaded to the channel library", s == 200 and b["change"] == "created", s)
time.sleep(6)
ans, dt = ask("@Max what monthly volume and price did the second supplier confirm in the new DRAM offer file?")
check("Max learned the new file via notification + delta", "17.5" in ans and ("12,500" in ans or "12500" in ans), f"{dt:.0f}s | {ans[:200]}")

note2 = note.replace("valid until 30 Nov 2026", "valid until 5 Dec 2026 (extended)")
http("POST", SIM + "/api/channel/upload", {"name": "14_Second_Supplier_DRAM_Offer.md", "data": base64.b64encode(note2.encode()).decode()})
time.sleep(6)
ans, dt = ask("@Max until when is the second supplier's DRAM offer valid now?")
check("Max picked up the updated file version", "5 dec" in ans.lower() or "december 5" in ans.lower(), f"{dt:.0f}s | {ans[:160]}")

# ---------------- lifecycle: subscriptions removed -> Max resubscribes + resyncs ----------------
http("POST", SIM + "/api/admin/remove-subscriptions", {})
back, dt = wait_for(lambda: len(http("GET", SIM + "/api/admin")[1]["subscriptions"]) >= 3 or None, 90)
check("after 'subscriptionRemoved' Max resubscribed", back is not None, f"{dt:.0f}s")
log = http("GET", SIM + "/api/admin")[1]["log"]
check("lifecycle notifications were delivered and acknowledged", any("subscriptionRemoved" in l["what"] and l["status"].startswith("2") for l in log))

# ---------------- live meeting -> official transcript -> Max learns it ----------------
if not skip_meeting:
    if http("GET", SIM + "/api/meeting")[1]["status"] in ("live", "summarizing"):
        http("POST", SIM + "/api/meeting/stop", {})
        wait_for(lambda: http("GET", SIM + "/api/meeting")[1]["status"] not in ("live", "summarizing") or None, 120)
    s, b = http("POST", SIM + "/api/meeting/start", {"mode": "autopilot", "speed": 8})
    check("autopilot meeting started", s == 200, b)
    ended, dt = wait_for(lambda: http("GET", SIM + "/api/meeting")[1]["status"] == "ended" or None, 600, 5)
    check("autopilot meeting finished", ended is not None, f"{dt:.0f}s")
    got, dt = wait_for(lambda: any("callTranscript created" in l["what"] and l["status"].startswith("2")
                                   for l in http("GET", SIM + "/api/admin")[1]["log"]) or None, 60)
    check("transcript notification delivered to Max after the meeting", got is not None, f"{dt:.0f}s")
    time.sleep(4)
    ans, dt = ask("@Max according to today's H2 Supply & Pricing Decisions transcript, who will send the 70% memory commitment to Sarah for signature, and by when?")
    a = ans.lower()
    check("Max answers from today's official transcript", "daniel" in a and any(x in a for x in ("1 dec", "december 1", "1st of december", "2026-12-01")), f"{dt:.0f}s | {ans[:200]}")

h = http("GET", MAX + "/health")[1]
print("\nMax health:", json.dumps(h["teams"]))
print("\nPHASE 2:", "ALL PASS" if ok_all else "SOME FAILED")
