"""
App-only tokens for Max (OAuth 2.0 client credentials).

The Teams SDK's default (MSAL) only accepts https:// sign-in authorities, which a local
simulator can't offer. This provider speaks the same standard protocol to whatever
login endpoint is configured, so it works against real Entra ID
(https://login.microsoftonline.com) and against rmeet-ai alike. It is plugged into the
SDK through its official `token=` hook and shared with Max's Graph client.
"""

import asyncio
import time

import httpx

from config import CONFIG


class ClientCredentialsProvider:
    def __init__(self, cfg=CONFIG):
        self.cfg = cfg
        self._cache: dict[str, tuple[str, float]] = {}
        self._lock = asyncio.Lock()
        self._http = httpx.AsyncClient(timeout=20)

    async def __call__(self, scope, tenant_id=None) -> str:
        """Teams SDK token hook: (scope, tenant_id) -> access token."""
        scope = scope[0] if isinstance(scope, list) else scope
        return await self.get(scope, tenant_id)

    def invalidate(self, scope: str, tenant_id: str | None = None) -> None:
        """Drop a cached token, e.g. after an admin granted new permissions (roles are fixed at issue time)."""
        self._cache.pop(f"{tenant_id or self.cfg.tenant_id}|{scope}", None)

    async def get(self, scope: str, tenant_id: str | None = None) -> str:
        tenant = tenant_id or self.cfg.tenant_id
        key = f"{tenant}|{scope}"
        async with self._lock:
            tok = self._cache.get(key)
            if tok and time.time() < tok[1] - 120:
                return tok[0]
            r = await self._http.post(f"{self.cfg.login_endpoint}/{tenant}/oauth2/v2.0/token", data={
                "grant_type": "client_credentials", "client_id": self.cfg.client_id,
                "client_secret": self.cfg.client_secret, "scope": scope})
            if r.status_code != 200:
                raise RuntimeError(f"Token request failed ({r.status_code}): {r.text[:200]}")
            data = r.json()
            self._cache[key] = (data["access_token"], time.time() + int(data.get("expires_in", 3600)))
            return data["access_token"]


TOKENS = ClientCredentialsProvider()
