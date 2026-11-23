"""
Approvals: every external step (email, meeting invite, file upload) waits for a person's click on a card.

Flow (design: docs/plans/max-agent-graph.html):
  prepare  (graph node prepare_approval)  run the action's rules + create the draft (actions.py), freeze the payload
           (+ hash), save a pending_actions row, post the card in the thread, schedule the 24 h expiry job.
  click    (Teams invoke adaptiveCard/action)  answer AT ONCE with the updated card; check the clicker is the
           requester or a team owner (manager); claim the row (one click wins); stale cards (old version) refused;
           then resume the paused LangGraph run in the background.
  execute  (graph node execute)  claim approved -> executing, check the payload hash, run the action once,
           record the Microsoft id, card -> "Sent / Created".
  expiry   (job)  still pending after 24 h -> expired, draft removed, run resumed with "expired".
  recover  (startup)  approved-but-not-run rows are resumed; rows stuck in 'executing' are marked failed
           (they may have been sent: never repeat).
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from typing import Any, Awaitable, Callable

from agent.actions import CLEANUP
from agent.tools import ToolContext
from policies import approver_ids

log = logging.getLogger("max")
EXPIRY_S = 24 * 3600
CARD = "application/vnd.microsoft.card.adaptive"
ICON = {"email": "✉", "meeting": "📅", "upload": "📤", "task": "🗓"}


def payload_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def card_for(p: dict, approvers: list[dict]) -> dict:
    """The Adaptive Card for a pending action in its current status (Action.Execute, Universal Actions).
    approvers: the people allowed to approve it ({name, aad_id}), by the team's policy."""
    prev = json.loads(p["preview"])
    st = p["status"]
    icon = ICON.get(prev.get("kind"), "⚙")
    names = " or ".join(dict.fromkeys(a["name"] for a in approvers)) or "a team owner"
    head = {"pending": f"{icon} {prev.get('title', 'Approval needed')}",
            "approved": f"{icon} Sending…", "executing": f"{icon} Sending…",
            "done": f"✅ Done · approved by {p['decided_by']}",
            "failed": f"⚠ Not done · approved by {p['decided_by']}",
            "cancelled": f"✖ Cancelled by {p['decided_by']}", "expired": "⌛ Expired (nobody approved within 24 h)",
            "superseded": f"↻ Changed by {p['decided_by']}: Max is preparing a new version"}.get(st, st)
    body = [{"type": "TextBlock", "text": head, "weight": "Bolder", "size": "Medium", "wrap": True},
            {"type": "FactSet", "facts": [{"title": k, "value": v} for k, v in prev.get("facts", [])]}]
    if prev.get("note") and st == "pending":       # e.g. why this time and not the one asked for (checked by Max)
        body.append({"type": "TextBlock", "text": f"💡 {prev['note']}", "wrap": True, "color": "Accent"})
    if prev.get("body"):
        body += [{"type": "TextBlock", "text": "Message", "weight": "Bolder", "spacing": "Medium"},
                 {"type": "TextBlock", "text": prev["body"], "wrap": True}]
    if p["read_outside"]:
        body.append({"type": "TextBlock", "wrap": True, "color": "Warning",
                     "text": "⚠ Max read files or emails from outside the chat while preparing this. "
                             "Check the recipients and the content before approving."})
    if st == "done" and p["result"]:
        body.append({"type": "TextBlock", "text": p["result"], "wrap": True, "color": "Good"})
    if st == "failed" and p["result"]:
        body.append({"type": "TextBlock", "text": p["result"], "wrap": True, "color": "Attention"})
    card = {"type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.5", "body": body}
    if st == "pending":
        exp = time.strftime("%d %b %H:%M", time.gmtime(p["expires_at"])) + " UTC"
        body.append({"type": "TextBlock", "isSubtle": True, "wrap": True, "size": "Small",
                     "text": f"Requested by {p['requester']} · can approve: {names} · expires {exp}"})
        body.append({"type": "Input.Text", "id": "edit", "placeholder": "What should change? (then press Change)",
                     "isMultiline": True})
        data = {"pendingId": p["id"], "version": p["version"]}
        card["actions"] = [
            {"type": "Action.Execute", "title": "Approve", "verb": "approve", "data": data, "style": "positive"},
            {"type": "Action.Execute", "title": "Change", "verb": "change", "data": data},
            {"type": "Action.Execute", "title": "Cancel", "verb": "cancel", "data": data, "style": "destructive"}]
        # Universal Actions user-specific view: only approvers get the live card with buttons.
        ids = [x for x in dict.fromkeys(a["aad_id"] for a in approvers) if x]
        card["refresh"] = {"action": {"type": "Action.Execute", "verb": "refresh", "data": data}, "userIds": ids[:60]}
    return card


class Approvals:
    def __init__(self, store, clock, graph_client, toolsets: Callable[[ToolContext], list],
                 post_card: Callable[..., Awaitable[str]], update_card: Callable[..., Awaitable[None]]):
        self.store, self.clock, self.graph = store, clock, graph_client
        self.toolsets, self.post_card, self.update_card = toolsets, post_card, update_card
        self.resume: Callable[[str, dict, str | None], Awaitable[None]] | None = None   # set by app.py

    # ------------------------------------------------------------------ helpers
    def ctx(self, team_id: str, requester: str | None, extra: dict | None = None) -> ToolContext:
        return ToolContext(self.store, team_id, requester, self.clock, {"graph": self.graph, **(extra or {})})

    def spec(self, ctx: ToolContext, name: str):
        return next((s for s in self.toolsets(ctx) if s.name == name), None)

    def tag_of(self, p) -> str:
        spec = self.spec(self.ctx(p["team_id"], p["requester"]), p["tool"])
        return spec.rbac if spec else p["tool"]

    def approvers(self, p) -> list[dict]:
        """People allowed to approve this action (team policy): the requester and/or the team owners."""
        ids, owners = approver_ids(self.store, p["team_id"], self.tag_of(p), p["requester_aad"])
        people = [{"name": p["requester"], "aad_id": p["requester_aad"]}] if p["requester_aad"] in ids else []
        return people + [{"name": o["name"], "aad_id": o["aad_id"]} for o in owners
                         if o["aad_id"] != p["requester_aad"]]

    def card(self, pending_id: str) -> dict:
        p = dict(self.store.pending(pending_id))
        return card_for(p, self.approvers(p))

    async def refresh_card(self, pending_id: str) -> None:
        p = self.store.pending(pending_id)
        if p and p["card_message_id"]:
            try:
                await self.update_card(p["team_id"], p["thread_root"], p["card_message_id"], self.card(pending_id))
            except Exception as e:  # noqa: BLE001  the card is a view: never fail the action because of it
                log.warning("Could not update approval card %s: %s", pending_id, e)

    async def cleanup(self, p) -> None:
        fn = CLEANUP.get(p["tool"])
        if fn:
            await fn(self.ctx(p["team_id"], p["requester"]), json.loads(p["payload"]), p["graph_id"])

    # ------------------------------------------------------------------ called by the graph
    async def prepare(self, state: dict, spec, call: dict) -> dict:
        r = state["request"]
        ctx = self.ctx(r["teamId"], r.get("requester"), {"threadRoot": r.get("threadRoot"), "runId": r.get("runId")})
        if spec.prepare is None:
            return {"blocked": "this action isn't available"}
        try:
            res = await spec.prepare(ctx, call["args"])
        except Exception as e:  # noqa: BLE001  bad arguments or a Graph problem: tell the model
            return {"blocked": f"couldn't prepare it: {type(e).__name__}: {e}"}
        if res.get("blocked"):
            return res
        outside = any(json.loads(a["detail"]).get("outside") for a in self.store.audit_for(r.get("runId"))
                      if a["kind"] == "tool")
        now = self.clock.now().timestamp()
        pid = uuid.uuid4().hex
        row = {"id": pid, "team_id": r["teamId"], "run_id": r["runId"], "tool": call["name"], "call_id": call["id"],
               "payload": json.dumps(res["payload"], ensure_ascii=False), "payload_hash": payload_hash(res["payload"]),
               "preview": json.dumps({"kind": res.get("kind"), "title": res.get("title"), "facts": res["facts"],
                                      "body": res.get("body"), "note": res.get("note")}, ensure_ascii=False),
               "requester": r.get("requester"), "requester_aad": r.get("requesterAad"), "thread_root": r.get("threadRoot"),
               "graph_id": res.get("graph_id"), "read_outside": int(bool(outside)), "created_at": now,
               "expires_at": now + EXPIRY_S, "status": "pending", "version": 1}
        self.store.add_pending(row)
        try:
            msg_id = await self.post_card(r["teamId"], self.card(pid), r.get("threadRoot"))
            self.store.set_pending(pid, card_message_id=msg_id)
        except Exception as e:  # noqa: BLE001  no card = nobody can approve: undo and tell the model
            self.store.set_pending(pid, status="failed", result=f"card not posted: {e}")
            await self.cleanup(self.store.pending(pid))
            return {"blocked": f"I couldn't post the approval card ({e})"}
        self.store.add_job(r["teamId"], "expire_approval", row["expires_at"], {"pendingId": pid},
                           dedupe_key=f"pa:{pid}:expire")
        self.store.audit(r["runId"], r["teamId"], "approval-requested", {"pendingId": pid, "tool": call["name"],
                                                                          "hash": row["payload_hash"]})
        return {"pending": {"id": pid, "call": call}}

    async def execute(self, state: dict, pending: dict) -> str:
        pid = pending["id"]
        if not self.store.claim_pending(pid, "approved", "executing"):
            p = self.store.pending(pid)
            return f"not run: the approval is '{p['status'] if p else 'gone'}'"
        p = self.store.pending(pid)
        payload = json.loads(p["payload"])
        if payload_hash(payload) != p["payload_hash"]:
            self.store.set_pending(pid, status="failed", result="payload changed after approval: not sent")
            await self.refresh_card(pid)
            return "not run: what was approved doesn't match what would be sent"
        ctx = self.ctx(p["team_id"], p["requester"], {"threadRoot": p["thread_root"]})
        spec = self.spec(ctx, p["tool"])
        try:
            result = await spec.execute(ctx, payload, p["graph_id"])
        except Exception as e:  # noqa: BLE001
            result = f"not done: {type(e).__name__}: {e}"
        ok = not result.startswith("not ")
        self.store.set_pending(pid, status="done" if ok else "failed", result=result, done_at=time.time())
        self.store.cancel_jobs(f"pa:{pid}:")
        await self.refresh_card(pid)
        return result

    # ------------------------------------------------------------------ Teams card clicks
    async def on_click(self, verb: str, data: dict, user_aad: str | None, user_name: str | None) -> dict:
        """Returns {"card": card} or {"message": text}. Answers at once; the real work resumes in the background."""
        pid = (data or {}).get("pendingId")
        p = self.store.pending(pid) if pid else None
        if p is None:
            return {"message": "This approval request no longer exists."}
        if verb == "refresh" or p["status"] != "pending":
            return {"card": self.card(pid)}
        if int((data or {}).get("version") or 0) != p["version"]:
            return {"card": self.card(pid)}
        now = self.clock.now().timestamp()
        if now >= p["expires_at"]:
            await self.expire_one(pid, background=True)
            return {"card": self.card(pid)}
        approvers = self.approvers(p)
        if not user_aad or user_aad not in {a["aad_id"] for a in approvers}:
            self.store.audit(p["run_id"], p["team_id"], "approval-denied", {"pendingId": pid, "by": user_name,
                                                                             "verb": verb})
            names = " or ".join(dict.fromkeys(a["name"] for a in approvers)) or "a team owner"
            return {"message": f"Only {names} can approve this."}
        if verb == "approve":
            if not self.store.claim_pending(pid, "pending", "approved", by=user_name, now=now):
                return {"card": self.card(pid)}
            decision = {"action": "approve", "by": user_name}
        elif verb == "cancel":
            if not self.store.claim_pending(pid, "pending", "cancelled", by=user_name, now=now):
                return {"card": self.card(pid)}
            self.store.cancel_jobs(f"pa:{pid}:")
            await self.cleanup(self.store.pending(pid))
            decision = {"action": "cancel", "by": user_name}
        elif verb == "change":
            edit = ((data or {}).get("edit") or "").strip()
            if not edit:
                return {"message": "Type what should change in the box first, then press Change."}
            if not self.store.claim_pending(pid, "pending", "superseded", by=user_name, now=now):
                return {"card": self.card(pid)}
            self.store.cancel_jobs(f"pa:{pid}:")
            await self.cleanup(self.store.pending(pid))
            decision = {"action": "change", "by": user_name, "edit": edit}
        else:
            return {"message": "Unknown action."}
        self.store.audit(p["run_id"], p["team_id"], "approval-click", {"pendingId": pid, **decision})
        if self.resume:
            asyncio.get_running_loop().create_task(self.resume(p["run_id"], decision, p["thread_root"]))
        return {"card": self.card(pid)}

    # ------------------------------------------------------------------ expiry + recovery
    async def expire_one(self, pid: str, background: bool = False) -> bool:
        if not self.store.claim_pending(pid, "pending", "expired"):
            return False
        p = self.store.pending(pid)
        await self.cleanup(p)
        await self.refresh_card(pid)
        self.store.audit(p["run_id"], p["team_id"], "approval-expired", {"pendingId": pid})
        if self.resume:
            coro = self.resume(p["run_id"], {"action": "expired", "by": "nobody"}, p["thread_root"])
            if background:
                asyncio.get_running_loop().create_task(coro)
            else:
                await coro
        return True

    async def expire_job(self, job: dict) -> str | None:
        return None if await self.expire_one(job["payload"]["pendingId"]) else "skipped"

    async def recover(self) -> None:
        """After a restart: finish approved actions; never repeat ones that may have run."""
        for p in self.store.pendings(status="executing"):
            self.store.set_pending(p["id"], status="failed",
                                   result="Max restarted while doing this; it may have been done, so it is not repeated")
            await self.refresh_card(p["id"])
        for p in self.store.pendings(status="approved"):
            if self.resume:
                log.info("Resuming approved action %s after restart", p["id"])
                await self.resume(p["run_id"], {"action": "approve", "by": p["decided_by"]}, p["thread_root"])
