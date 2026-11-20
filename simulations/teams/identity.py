"""
Fake Microsoft identity:
- Entra ID token endpoint (client credentials)        -> POST /login/{tenant}/oauth2/v2.0/token
- Bot Framework OpenID metadata + signing keys (JWKS) -> GET  /botframework/v1/.well-known/...
- Signs inbound Bot Connector tokens (Connector -> bot) and verifies tokens the bot sends us.

Real equivalents: https://login.microsoftonline.com/... and https://login.botframework.com/v1/.well-known/...
"""

import base64
import hashlib
import json
import secrets
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qs

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from httpx_types import Req, Resp, Router

STATE_DIR = Path(__file__).resolve().parent / "state"
KEY_FILE = STATE_DIR / "signing_key.pem"
REG_FILE = STATE_DIR / "registration.json"

BOT_ISSUER = "https://api.botframework.com"          # issuer of Connector -> bot tokens
BOT_AUDIENCE = "https://api.botframework.com"        # audience of bot -> Connector tokens
GRAPH_AUDIENCE = "https://graph.microsoft.com"


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class Identity:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        if not KEY_FILE.exists():
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            KEY_FILE.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                                   serialization.PrivateFormat.PKCS8,
                                                   serialization.NoEncryption()))
        self.private_key = serialization.load_pem_private_key(KEY_FILE.read_bytes(), password=None)
        self.public_key = self.private_key.public_key()
        der = self.public_key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        self.kid = _b64u(hashlib.sha1(der).digest())
        self.registration = self._load_registration()
        self.roles_provider = lambda: []     # admin-consented application permissions (set by the server)

    # ------------------------------------------------------------- registration
    @staticmethod
    def _load_registration() -> dict:
        """The 'Azure portal' side: the bot's app registration (created by register_app.py)."""
        if REG_FILE.exists():
            return json.loads(REG_FILE.read_text(encoding="utf-8"))
        return {}

    def reload(self) -> None:
        self.registration = self._load_registration()

    @property
    def app_id(self) -> str:
        return self.registration.get("appId", "")

    # ------------------------------------------------------------------- tokens
    def sign(self, claims: dict) -> str:
        return jwt.encode(claims, self.private_key, algorithm="RS256", headers={"kid": self.kid, "x5t": self.kid})

    def connector_token_for_bot(self, service_url: str) -> str:
        """Token the Connector attaches when POSTing an activity to the bot."""
        now = int(time.time())
        return self.sign({"iss": BOT_ISSUER, "aud": self.app_id, "serviceurl": service_url,
                          "nbf": now - 5, "iat": now - 5, "exp": now + 3600})

    def verify_app_token(self, token: str | None, audience: str) -> dict | None:
        """Verify a token the bot obtained from our token endpoint. Returns claims or None."""
        if not token:
            return None
        try:
            claims = jwt.decode(token, self.public_key, algorithms=["RS256"], audience=audience,
                                options={"require": ["exp", "aud", "iss"]})
        except jwt.PyJWTError:
            return None
        return claims if claims.get("appid") == self.app_id else None

    # ------------------------------------------------------------------- routes
    def routes(self, r: Router) -> None:
        r.add("POST", r"/login/([^/]+)/oauth2/v2\.0/token", self._token)
        r.add("GET", r"/botframework/v1/\.well-known/openidconfiguration", self._openid)
        r.add("GET", r"/botframework/v1/\.well-known/keys", self._jwks)

    def _token(self, req: Req, tenant: str) -> Resp:
        form = {k: v[0] for k, v in parse_qs(req.body.decode("utf-8")).items()}
        if form.get("grant_type") != "client_credentials":
            return Resp.json(400, {"error": "unsupported_grant_type",
                                   "error_description": "AADSTS70003: The app requested an unsupported grant type."})
        reg = self.registration
        if not reg or form.get("client_id") != reg.get("appId") or \
                not secrets.compare_digest(form.get("client_secret", ""), reg.get("clientSecret", "")):
            return Resp.json(401, {"error": "invalid_client",
                                   "error_description": "AADSTS7000215: Invalid client secret provided."})
        if tenant not in (reg.get("tenantId"), "botframework.com"):
            return Resp.json(400, {"error": "invalid_request",
                                   "error_description": f"AADSTS90002: Tenant '{tenant}' not found."})
        scope = form.get("scope", "")
        if scope.startswith(BOT_AUDIENCE):
            aud = BOT_AUDIENCE
        elif scope.startswith(GRAPH_AUDIENCE):
            aud = GRAPH_AUDIENCE
        else:
            return Resp.json(400, {"error": "invalid_scope",
                                   "error_description": f"AADSTS70011: The provided value for scope '{scope}' is not valid."})
        now = int(time.time())
        claims = {"aud": aud, "iss": f"https://sts.windows.net/{reg['tenantId']}/", "iat": now, "nbf": now,
                  "exp": now + 3600, "appid": reg["appId"], "azp": reg["appId"],
                  "tid": reg["tenantId"], "oid": str(uuid.uuid5(uuid.NAMESPACE_URL, reg["appId"])),
                  "idtyp": "app", "ver": "1.0"}
        if aud == GRAPH_AUDIENCE:
            roles = list(self.roles_provider())
            if roles:
                claims["roles"] = roles      # like real app-only tokens: only admin-consented permissions
        token = self.sign(claims)
        return Resp.json(200, {"token_type": "Bearer", "expires_in": 3599, "ext_expires_in": 3599,
                               "access_token": token})

    def _openid(self, req: Req) -> Resp:
        return Resp.json(200, {
            "issuer": BOT_ISSUER,
            "authorization_endpoint": "https://invalid.botframework.com",
            "jwks_uri": f"{self.base_url}/botframework/v1/.well-known/keys",
            "id_token_signing_alg_values_supported": ["RS256"],
            "token_endpoint_auth_methods_supported": ["private_key_jwt"],
        })

    def _jwks(self, req: Req) -> Resp:
        nums = self.public_key.public_numbers()
        n = _b64u(nums.n.to_bytes((nums.n.bit_length() + 7) // 8, "big"))
        e = _b64u(nums.e.to_bytes((nums.e.bit_length() + 7) // 8, "big"))
        return Resp.json(200, {"keys": [{"kty": "RSA", "use": "sig", "kid": self.kid, "x5t": self.kid,
                                         "n": n, "e": e, "endorsements": ["msteams"]}]})
