"""
One-time setup = what you would do in the Azure portal + Teams admin center:

1. Create Max's app registration (app id + client secret) in the fake tenant.
2. Register the bot's messaging endpoint (http://localhost:3978/api/messages).
3. Build Max's Teams app package (manifest.json + icons) and "upload" it to the
   fake tenant's app catalog (simulations/teams/state/app_package/).
4. Write max/.env so Max can sign in to this fake tenant (and copy the model keys).

Run:  .venv\\Scripts\\python simulations\\teams\\register_app.py          (keeps an existing registration)
      .venv\\Scripts\\python simulations\\teams\\register_app.py --reset  (new app id + secret)
"""

import json
import secrets
import shutil
import struct
import sys
import uuid
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from store import TENANT_ID  # noqa: E402

PROJECT = HERE.parents[1]
STATE = HERE / "state"
REG_FILE = STATE / "registration.json"
CATALOG = STATE / "app_package"
MAX_DIR = PROJECT / "max"
SIM = "http://localhost:8100"

RSC = ["ChannelMessage.Read.Group", "TeamMember.Read.Group", "ChannelSettings.Read.Group",
       "TeamSettings.Read.Group", "File.Read.Group", "ChannelMeeting.ReadBasic.Group"]
APP_PERMISSIONS = ["Calendars.Read", "OnlineMeetings.Read.All", "OnlineMeetingTranscript.Read.All",
                   "Calls.JoinGroupCall.All", "Calls.AccessMedia.All",
                   # Phase 4 (teammate): directory lookup, Max's own mailbox + calendar (Exchange RBAC limits
                   # Mail.* / Calendars.ReadWrite to Max's mailbox), and writing files to the team's site only.
                   "User.ReadBasic.All", "Mail.ReadWrite", "Mail.Send", "Calendars.ReadWrite", "Sites.Selected"]


def png(size: int, rgba: tuple, transparent_bg: bool = False) -> bytes:
    """Tiny PNG encoder for the app icons (solid cloud-ish disc)."""
    rows = []
    c = (size - 1) / 2
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            inside = (x - c) ** 2 + (y - c) ** 2 <= (size * 0.42) ** 2
            if inside:
                row += bytes(rgba)
            else:
                row += bytes((0, 0, 0, 0)) if transparent_bg else bytes((255, 255, 255, 255))
        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows), 9)

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)) + \
        chunk(b"IDAT", raw) + chunk(b"IEND", b"")


def manifest(app_id: str) -> dict:
    return {
        "$schema": "https://developer.microsoft.com/en-us/json-schemas/teams/v1.29/MicrosoftTeams.schema.json",
        "manifestVersion": "1.29",
        "version": "0.1.0",
        "id": app_id,
        "developer": {"name": "Karthi Tech", "websiteUrl": "https://example.com",
                      "privacyUrl": "https://example.com/privacy", "termsOfUseUrl": "https://example.com/terms"},
        "name": {"short": "Max", "full": "Max: AI meeting assistant"},
        "description": {"short": "AI teammate for your channel and meetings.",
                        "full": "Max reads your team's channel, answers @Max questions with sources, "
                                "joins meetings, answers when asked and writes the notes."},
        "icons": {"color": "color.png", "outline": "outline.png"},
        "accentColor": "#FF6B00",
        "bots": [{
            "botId": app_id,
            "scopes": ["team", "groupChat", "personal"],
            "supportsFiles": False,
            "supportsCalling": True,
            "supportsVideo": False,
            "isNotificationOnly": False,
            "commandLists": [{"scopes": ["team"], "commands": [
                {"title": "summarize", "description": "Summarise this thread"},
                {"title": "what did we decide", "description": "Find a past decision and its source"},
                {"title": "help", "description": "What Max can do"}]}],
        }],
        "permissions": ["identity", "messageTeamMembers"],
        "validDomains": [],
        "webApplicationInfo": {"id": app_id, "resource": f"api://botid-{app_id}"},
        "authorization": {"permissions": {"resourceSpecific": [{"name": p, "type": "Application"} for p in RSC]}},
    }


def read_env(path: Path) -> dict:
    out = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def main() -> None:
    reset = "--reset" in sys.argv
    STATE.mkdir(parents=True, exist_ok=True)

    if REG_FILE.exists() and not reset:
        reg = json.loads(REG_FILE.read_text(encoding="utf-8"))
        print(f"Keeping existing registration: appId {reg['appId']}")
    else:
        reg = {"appId": str(uuid.uuid4()), "clientSecret": secrets.token_urlsafe(32), "tenantId": TENANT_ID,
               "botName": "Max", "messagingEndpoint": "http://localhost:3978/api/messages",
               }
        print(f"Created app registration: appId {reg['appId']}")
    # API permissions (Entra 'requiredResourceAccess'): tenant-wide Graph application permissions that
    # need ADMIN CONSENT, on top of the team-level RSC permissions in the manifest.
    reg["applicationPermissions"] = APP_PERMISSIONS
    REG_FILE.write_text(json.dumps(reg, indent=2), encoding="utf-8")

    # App package (what the admin uploads to the org app catalog)
    pkg = MAX_DIR / "appPackage"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "manifest.json").write_text(json.dumps(manifest(reg["appId"]), indent=2), encoding="utf-8")
    (pkg / "color.png").write_bytes(png(192, (255, 107, 0, 255)))
    (pkg / "outline.png").write_bytes(png(32, (255, 255, 255, 255), transparent_bg=True))
    if CATALOG.exists():
        shutil.rmtree(CATALOG)
    shutil.copytree(pkg, CATALOG)
    print(f"App package built in {pkg} and uploaded to the fake tenant catalog")

    # Max's settings
    env_file = MAX_DIR / ".env"
    existing = read_env(env_file)
    keys = read_env(PROJECT / "voice-chat" / ".env")
    lines = [
        "# Written by simulations/teams/register_app.py — Max's Teams app identity (fake tenant)",
        f"CLIENT_ID={reg['appId']}",
        f"CLIENT_SECRET={reg['clientSecret']}",
        f"TENANT_ID={reg['tenantId']}",
        "PORT=3978",
        "",
        "# Where 'Microsoft' lives. Real Teams: remove these 3 lines to use the public cloud defaults.",
        f"TEAMS_LOGIN_ENDPOINT={SIM}/login",
        f"TEAMS_OPENID_METADATA_URL={SIM}/botframework/v1/.well-known/openidconfiguration",
        f"GRAPH_BASE_URL={SIM}/graph/v1.0",
        "",
        "# Where Microsoft can reach Max for Graph change notifications (real Teams: a public https URL)",
        "MAX_PUBLIC_URL=http://localhost:3978",
        "",
        "# Calling: Graph posts call notifications here; media connects to the media relay.",
        "# Real Teams: the relay is a thin Windows/.NET media worker speaking the same frame protocol.",
        f"MAX_CALLBACK_URL=http://localhost:3978/api/calling",
        f"MEDIA_RELAY_URL=ws://localhost:8100/media",
        "",
        "# Simulator only: test hooks (move Max's clock, run due jobs now, read Max's state). Never in real Teams.",
        "MAX_TEST_HOOKS=1",
        "",
        "# Max's own licensed account (mailbox + calendar), used app-only and limited to itself by Exchange RBAC",
        "MAX_MAILBOX=max@kestrelhomegoods.com",
        "",
        "# Max's voice (local Kokoro on the GPU by default, or Gemini TTS) and hearing (Gemini speech-to-text)",
        "GEMINI_TTS_MODEL=gemini-3.8-flash-lite-tts",
        "MAX_VOICE=Charon",
        "",
        "# Models (brain = Qwen or Gemini, hearing = Gemini, voices = local or Gemini)",
    ]
    switches = ("BRAIN_PROVIDER", "GEMINI_BRAIN_MODEL", "TTS_PROVIDER", "LOCAL_TTS_URL")
    for k in ("TW_API_KEY", "TW_BASE_URL", "TW_MODEL", "GEMINI_API_KEY", "GEMINI_MODEL") + switches:
        # voice-chat/.env is the source of truth; the switches only ever come from there
        v = keys.get(k) if k in switches else (keys.get(k) or existing.get(k))
        if v:
            lines.append(f"{k}={v}")
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {env_file} (model keys copied from voice-chat/.env)")


if __name__ == "__main__":
    main()
