"""Phase 1 end-to-end: fake Microsoft security, install + pre-read, @Max in threads, RSC live learning, Graph round trip."""
import json, time, urllib.parse, urllib.request, urllib.error
from pathlib import Path

SIM, MAX = "http://127.0.0.1:8100", "http://127.0.0.1:3978"
REG = json.loads((Path(__file__).resolve().parents[1] / "simulations" / "teams" / "state" / "registration.json").read_text())
ok_all = True

def check(name, cond, detail=""):
    global ok_all
    ok_all &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))

def http(method, url, body=None, headers=None, form=None):
    data = None
    h = dict(headers or {})
    if form is not None:
        data = urllib.parse.urlencode(form).encode(); h["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode(); h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read(); return r.status, (json.loads(raw) if raw and raw[:1] in b"{[" else raw)
    except urllib.error.HTTPError as e:
        raw = e.read(); return e.code, (json.loads(raw) if raw and raw[:1] in b"{[" else raw)

for _ in range(60):
    try:
        if http("GET", MAX + "/health")[0] == 200 and http("GET", SIM + "/api/channel")[0] == 200: break
    except Exception: pass
    time.sleep(0.5)

tenant = REG["tenantId"]
# ---------- security ----------
s, b = http("POST", f"{SIM}/login/{tenant}/oauth2/v2.0/token", form={"grant_type": "client_credentials", "client_id": REG["appId"], "client_secret": "wrong", "scope": "https://graph.microsoft.com/.default"})
check("token endpoint rejects wrong secret", s == 401 and b.get("error") == "invalid_client", s)
s, b = http("POST", f"{SIM}/login/{tenant}/oauth2/v2.0/token", form={"grant_type": "client_credentials", "client_id": REG["appId"], "client_secret": REG["clientSecret"], "scope": "https://graph.microsoft.com/.default"})
check("token endpoint issues Graph token", s == 200 and b.get("token_type") == "Bearer", s)
gtok = b["access_token"]
s, b = http("GET", f"{SIM}/botframework/v1/.well-known/keys")
check("JWKS served", s == 200 and b["keys"][0]["endorsements"] == ["msteams"])

http("POST", SIM + "/api/channel/reset", {})
ch = http("GET", SIM + "/api/channel")[1]
team, channel = ch["ids"]["team"], ch["ids"]["channel"]
qc = urllib.parse.quote(channel, safe="")
s, b = http("GET", f"{SIM}/graph/v1.0/teams/{team}/channels/{qc}/messages")
check("Graph without token -> 401", s == 401, s)
s, b = http("GET", f"{SIM}/graph/v1.0/teams/{team}/channels/{qc}/messages", headers={"Authorization": f"Bearer {gtok}"})
check("Graph before install -> 403 (no RSC)", s == 403, s)
s, b = http("POST", f"{SIM}/teams/v3/conversations/{qc}/activities", {"type": "message", "text": "hi"})
check("Connector without token -> 401", s == 401, s)
check("seeded channel has 15 posts", len(ch["posts"]) == 15, len(ch["posts"]))

def wait_for(pred, timeout=120):
    t = time.time()
    while time.time() - t < timeout:
        ch = http("GET", SIM + "/api/channel")[1]
        r = pred(ch)
        if r: return r, time.time() - t
        time.sleep(1)
    return None, timeout

# ---------- install + pre-read ----------
s, b = http("POST", SIM + "/api/channel/install", {"action": "add"})
check("install accepted", s == 200 and b["install"]["installed"], s)
welcome, dt = wait_for(lambda c: next((p for p in c["posts"] if p["isBot"]), None))
check("Max pre-read the channel via Graph and posted a welcome", welcome is not None, f"{dt:.1f}s")
if welcome: print("   Max:", welcome["text"][:220].replace("\n", " "))

# ---------- @Max new thread ----------
s, root = http("POST", SIM + "/api/channel/post", {"text": "@Max quick check before the review: what is the gap in budget draft v2, and which options did Prince recommend?"})
check("Karthi posted a new thread with @Max", s == 200 and root["mentions"] == ["Max"], s)
rid = root["id"]
reply, dt = wait_for(lambda c: next((r for p in c["posts"] if p["id"] == rid for r in p["replies"] if r["isBot"]), None))
check("Max replied IN the thread", reply is not None, f"{dt:.1f}s")
if reply:
    print("   Max:", reply["text"].replace("\n", " ")[:400])
    check("answer has the right facts (220, A, B, C)", "220" in reply["text"] and all(x in reply["text"] for x in ["A", "B", "C"]))

# ---------- @Max reply in an existing seeded thread (Daniel's Nov 18 post) ----------
seed = next(p for p in ch["posts"] if p["author"] == "daniel" and "1-site" in p["text"])
s, msg = http("POST", SIM + "/api/channel/post", {"text": "@Max does the 1-site pilot still need funding under the CFO rule, and could options D and E cover it?", "rootId": seed["id"]})
reply2, dt = wait_for(lambda c: next((r for p in c["posts"] if p["id"] == seed["id"] for r in p["replies"] if r["isBot"]), None))
check("Max replied inside an existing thread", reply2 is not None, f"{dt:.1f}s")
if reply2:
    print("   Max:", reply2["text"].replace("\n", " ")[:400])
    check("thread answer mentions 95", "95" in reply2["text"])

# ---------- RSC: message without @mention is delivered, Max learns but stays quiet ----------
s, fyi = http("POST", SIM + "/api/channel/post", {"text": "Heads-up from Elena's office: the final budget deadline moved from 28 Nov to 27 Nov."})
time.sleep(6)
ch2 = http("GET", SIM + "/api/channel")[1]
quiet = not any(r["isBot"] for p in ch2["posts"] if p["id"] == fyi["id"] for r in p["replies"])
check("Max stayed quiet on a post without @mention", quiet)
s, q3 = http("POST", SIM + "/api/channel/post", {"text": "@Max when is the final budget due to Elena now?"})
reply3, dt = wait_for(lambda c: next((r for p in c["posts"] if p["id"] == q3["id"] for r in p["replies"] if r["isBot"]), None))
check("Max learned the new deadline live (RSC delivery)", reply3 is not None and "27" in reply3["text"], (reply3 or {}).get("text", "")[:200])

# ---------- Graph round trip: Max's reply visible through Graph ----------
s, b = http("GET", f"{SIM}/graph/v1.0/teams/{team}/channels/{qc}/messages/{rid}/replies", headers={"Authorization": f"Bearer {gtok}"})
bot_replies = [m for m in b.get("value", []) if (m["from"] or {}).get("application")]
check("Max's reply is readable through Graph as from.application (bot)", s == 200 and bot_replies and bot_replies[0]["from"]["application"]["applicationIdentityType"] == "bot")

print("\nPHASE 1:", "ALL PASS" if ok_all else "SOME FAILED")
