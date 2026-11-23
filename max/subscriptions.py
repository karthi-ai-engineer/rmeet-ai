"""
Max's Microsoft Graph change-notification subscriptions.

  channel messages   /teams/{team}/channels/{channel}/messages      created,updated,deleted
  channel files      /drives/{drive}/root                           updated  (then delta query)
  transcripts        users/{organizer}/onlineMeetings/getAllTranscripts   created

Each subscription has a secret clientState; notifications without it are ignored.
Subscriptions are renewed before they expire and recreated after 'subscriptionRemoved'.
"""

import asyncio
import json
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone

from config import CONFIG
from graph_client import GraphClient, GraphError

log = logging.getLogger("max")
LIFETIME_MIN = 4200           # just under the 4,320-minute Teams maximum
RENEW_WHEN_LEFT_MIN = 24 * 60


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.0000000Z")


def _ts(value: str) -> float:
    """Graph timestamps may have 7 fractional digits and a Z or offset."""
    import re
    m = re.match(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d+))?(Z|[+-]\d\d:\d\d)?$", value.strip())
    if not m:
        return time.time() + LIFETIME_MIN * 60
    base, frac, tz = m.groups()
    dt = datetime.fromisoformat(base + (f".{frac[:6]}" if frac else "") + ("+00:00" if tz in (None, "Z") else tz))
    return dt.timestamp()


class SubscriptionManager:
    def __init__(self, graph: GraphClient, store, cfg=CONFIG):
        self.graph, self.cfg, self.store = graph, cfg, store
        self._lock = asyncio.Lock()        # one ensure() at a time: install and recovery can race
        self.subs: dict[str, dict] = store.subscriptions()
        old = cfg.data_dir / "subscriptions.json"             # one-time move from the old JSON file
        if old.exists():
            if not self.subs:
                self.subs = json.loads(old.read_text("utf-8"))
                self._save()
            old.replace(old.with_suffix(".json.imported"))

    @property
    def notification_url(self) -> str:
        return f"{self.cfg.public_url}/graph/notifications"

    @property
    def lifecycle_url(self) -> str:
        return f"{self.cfg.public_url}/graph/lifecycle"

    def _save(self) -> None:
        self.store.save_subscriptions(self.subs)

    def get(self, sub_id: str, client_state: str | None) -> dict | None:
        s = self.subs.get(sub_id)
        return s if s and client_state and secrets.compare_digest(client_state, s["clientState"]) else None

    def for_team(self, team_id: str) -> list[dict]:
        return [s for s in self.subs.values() if s["teamId"] == team_id]

    def forget(self, sub_id: str) -> None:
        self.subs.pop(sub_id, None)
        self._save()

    def forget_team(self, team_id: str) -> None:
        for s in self.for_team(team_id):
            self.subs.pop(s["id"], None)
        self._save()

    async def ensure(self, team_id: str, kind: str, resource: str, change_type: str) -> str | None:
        """Create the subscription if we don't have a live one. Returns an error text or None."""
        async with self._lock:
            return await self._ensure(team_id, kind, resource, change_type)

    async def _ensure(self, team_id: str, kind: str, resource: str, change_type: str) -> str | None:
        now = datetime.now(timezone.utc)
        live = next((s for s in self.subs.values() if s["resource"] == resource and s["expires"] > now.timestamp()), None)
        if live:
            return None
        body = {"changeType": change_type, "notificationUrl": self.notification_url,
                "lifecycleNotificationUrl": self.lifecycle_url, "resource": resource,
                "expirationDateTime": _iso(now + timedelta(minutes=LIFETIME_MIN)),
                "clientState": secrets.token_urlsafe(32), "includeResourceData": False}
        try:
            try:
                r = await self.graph.post("/subscriptions", body)
            except GraphError as e:
                if e.status != 409:
                    raise
                # One subscription per app+resource: we lost track of it (e.g. data reset). Replace it.
                existing = await self.graph.get("/subscriptions")
                for s in existing.get("value", []):
                    if s.get("resource", "").lstrip("/") == resource.lstrip("/"):
                        await self.graph.delete(f"/subscriptions/{s['id']}")
                r = await self.graph.post("/subscriptions", body)
        except Exception as e:      # GraphError, network errors: report, never crash the caller
            log.warning("Subscription for %s failed: %s", resource, e)
            return str(e)
        for old_id in [i for i, s in self.subs.items() if s["resource"] == resource]:
            self.subs.pop(old_id)          # replaced on Graph (409 path) or expired: never keep a stale copy
        self.subs[r["id"]] = {"id": r["id"], "teamId": team_id, "kind": kind, "resource": resource,
                              "changeType": change_type, "clientState": body["clientState"],
                              "expires": _ts(r["expirationDateTime"])}
        self._save()
        log.info("Subscribed to %s changes: %s", kind, resource)
        return None

    async def renew_due(self) -> None:
        now = datetime.now(timezone.utc)
        for s in list(self.subs.values()):
            if s["expires"] - now.timestamp() > RENEW_WHEN_LEFT_MIN * 60:
                continue
            try:
                r = await self.graph.patch(f"/subscriptions/{s['id']}",
                                           {"expirationDateTime": _iso(now + timedelta(minutes=LIFETIME_MIN))})
                s["expires"] = _ts(r["expirationDateTime"])
                log.info("Renewed subscription %s", s["kind"])
            except GraphError as e:
                if e.status == 404:
                    self.subs.pop(s["id"], None)       # gone: the next ensure() recreates it
                log.warning("Renew failed for %s: %s", s["kind"], e)
        self._save()

    async def reauthorize(self, s: dict) -> None:
        try:
            await self.graph.post(f"/subscriptions/{s['id']}/reauthorize", {})
            s["expires"] = time.time()                 # force a renewal on the next pass
            await self.renew_due()
        except GraphError as e:
            log.warning("Reauthorize failed: %s", e)
