"""
Max's configuration, read from max/.env (written by simulations/teams/register_app.py).

The Microsoft endpoints are configuration, never code: pointing Max at real Teams
means deleting the TEAMS_* / GRAPH_BASE_URL overrides (public-cloud defaults apply)
and using a real app registration.
"""

import os
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env(HERE / ".env")


@dataclass(frozen=True)
class Config:
    client_id: str = os.environ.get("CLIENT_ID", "")
    client_secret: str = os.environ.get("CLIENT_SECRET", "")
    tenant_id: str = os.environ.get("TENANT_ID", "")
    port: int = int(os.environ.get("PORT", "3978"))

    login_endpoint: str = os.environ.get("TEAMS_LOGIN_ENDPOINT", "https://login.microsoftonline.com").rstrip("/")
    openid_metadata_url: str = os.environ.get(
        "TEAMS_OPENID_METADATA_URL", "https://login.botframework.com/v1/.well-known/openidconfiguration")
    graph_base_url: str = os.environ.get("GRAPH_BASE_URL", "https://graph.microsoft.com/v1.0").rstrip("/")
    graph_scope: str = "https://graph.microsoft.com/.default"

    # Public base URL where Microsoft Graph can POST change notifications to Max.
    public_url: str = os.environ.get("MAX_PUBLIC_URL", "http://localhost:3978").rstrip("/")

    # Calling: where Graph posts call notifications, and the media relay Max connects to.
    callback_url: str = os.environ.get("MAX_CALLBACK_URL", "http://localhost:3978/api/calling")
    media_relay_url: str = os.environ.get("MEDIA_RELAY_URL", "ws://localhost:8100/media").rstrip("/")
    data_dir: Path = HERE / "data"

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.tenant_id)


CONFIG = Config()

# The Teams SDK auto-reads CLIENT_SECRET from the environment and then insists on MSAL,
# which only accepts https:// authorities. Max passes its own token provider instead
# (auth.py), so keep the secret only in CONFIG.
os.environ.pop("CLIENT_SECRET", None)
