"""
Microsoft Graph client for Max (app-only, client credentials).

Same calls work against real Graph and the rmeet-ai fake: only GRAPH_BASE_URL and
the login endpoint differ (config). Follows the Graph rules from
docs/research/teams/02-graph-knowledge-apis.md: paging via @odata.nextLink,
429 + Retry-After, file download via 302 to a pre-authenticated URL (no bearer).
"""

import asyncio

import httpx

from auth import TOKENS
from config import CONFIG


class GraphError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(f"Graph {status} {code}: {message}")
        self.status, self.code = status, code


class GraphClient:
    def __init__(self, cfg=CONFIG):
        self.cfg = cfg
        self.http = httpx.AsyncClient(timeout=30, follow_redirects=False)

    async def token(self) -> str:
        try:
            return await TOKENS.get(self.cfg.graph_scope)
        except RuntimeError as e:
            raise GraphError(401, "token_error", str(e))

    async def request(self, method: str, path_or_url: str, params: dict | None = None, json: dict | None = None,
                      raw: bool = False):
        url = path_or_url if path_or_url.startswith("http") else f"{self.cfg.graph_base_url}{path_or_url}"
        refreshed = False
        for attempt in range(4):
            r = await self.http.request(method, url, params=params, json=json,
                                        headers={"Authorization": f"Bearer {await self.token()}"})
            if r.status_code == 429 and attempt < 3:
                await asyncio.sleep(float(r.headers.get("Retry-After", "2")))
                continue
            if r.status_code == 403 and not refreshed:
                # App-only tokens carry the roles granted when they were issued. If an admin has
                # granted consent since, a fresh token picks it up: retry once with a new token.
                TOKENS.invalidate(self.cfg.graph_scope)
                refreshed = True
                continue
            if r.status_code >= 400:
                try:
                    body = r.json().get("error", {})
                except ValueError:
                    body = {}
                inner = (body.get("innerError") or {}).get("code")
                raise GraphError(r.status_code, inner or body.get("code", "error"), body.get("message", r.text[:200]))
            if raw:
                return r.text
            return r.json() if r.content else {}
        raise GraphError(429, "TooManyRequests", "Throttled")

    async def get(self, path_or_url: str, params: dict | None = None) -> dict:
        return await self.request("GET", path_or_url, params)

    async def get_text(self, path_or_url: str, params: dict | None = None) -> str:
        return await self.request("GET", path_or_url, params, raw=True)

    async def post(self, path: str, body: dict) -> dict:
        return await self.request("POST", path, json=body)

    async def patch(self, path: str, body: dict) -> dict:
        return await self.request("PATCH", path, json=body)

    async def delete(self, path: str) -> None:
        await self.request("DELETE", path)

    async def get_all(self, path: str, params: dict | None = None, limit: int = 2000) -> list:
        """Follow @odata.nextLink pages."""
        out, data = [], await self.get(path, params)
        out.extend(data.get("value", []))
        while data.get("@odata.nextLink") and len(out) < limit:
            data = await self.get(data["@odata.nextLink"])
            out.extend(data.get("value", []))
        return out

    async def download(self, drive_id: str, item_id: str) -> bytes:
        url = f"{self.cfg.graph_base_url}/drives/{drive_id}/items/{item_id}/content"
        r = await self.http.get(url, headers={"Authorization": f"Bearer {await self.token()}"})
        if r.status_code in (301, 302, 303, 307, 308):
            r = await self.http.get(r.headers["Location"])     # pre-authenticated: no bearer token
        if r.status_code != 200:
            raise GraphError(r.status_code, "downloadFailed", f"Could not download item {item_id}")
        return r.content

    # ---- convenience wrappers -------------------------------------------------
    @staticmethod
    def _q(s: str) -> str:
        return httpx.URL(f"http://x/{s}").raw_path.decode()[1:]   # percent-encode ids like 19:...@thread.tacv2

    async def team(self, team_id: str) -> dict:
        return await self.get(f"/teams/{team_id}")

    async def channel_messages(self, team_id: str, channel_id: str) -> list:
        return await self.get_all(f"/teams/{team_id}/channels/{self._q(channel_id)}/messages", {"$top": "50"})

    async def replies(self, team_id: str, channel_id: str, message_id: str) -> list:
        return await self.get_all(f"/teams/{team_id}/channels/{self._q(channel_id)}/messages/{message_id}/replies",
                                  {"$top": "50"})

    async def message(self, team_id: str, channel_id: str, message_id: str) -> dict:
        return await self.get(f"/teams/{team_id}/channels/{self._q(channel_id)}/messages/{message_id}")

    async def files_folder(self, team_id: str, channel_id: str) -> dict:
        return await self.get(f"/teams/{team_id}/channels/{self._q(channel_id)}/filesFolder")

    async def children(self, drive_id: str, item_id: str) -> list:
        return await self.get_all(f"/drives/{drive_id}/items/{item_id}/children")
