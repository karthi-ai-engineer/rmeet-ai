"""
Per-team policies (RBAC, step 4.7). Every tool has an RBAC tag (agent/tools.py, agent/actions.py). For each tag a
team can set:
  who        everyone | owners | nobody         who may ask Max to use it (checked before the model sees the tool)
  approvers  requester_or_owner | owners        who may approve it on the card (external actions)
Defaults: everyone may ask; the requester or a team owner (the manager) approves.
Changes are made on Max's admin page and written to the audit log.
"""

from agent.tools import EXTERNAL, INTERNAL, ToolContext

LABELS = {
    "memory.read": "Answer from the team's memory (posts, files, meetings)",
    "files.read": "Read channel files",
    "meetings.read": "Read meetings, transcripts, free/busy and Max's calendar",
    "tasks.read": "List tasks",
    "tasks.write": "Create and change tasks",
    "mail.send": "Send emails from Max's mailbox",
    "meetings.create": "Book Teams meetings from Max's calendar",
    "meetings.cancel": "Cancel meetings Max booked",
    "files.upload": "Save new files in the channel",
}
RISK_ORDER = {"read": 0, INTERNAL: 1, EXTERNAL: 2}


def catalog(store, team_id: str, toolsets, clock, extra: dict) -> list[dict]:
    """One row per RBAC tag: tools, risk, Microsoft permission, current policy."""
    rows: dict[str, dict] = {}
    for s in toolsets(ToolContext(store, team_id, None, clock, extra)):
        r = rows.setdefault(s.rbac, {"tag": s.rbac, "label": LABELS.get(s.rbac, s.rbac), "tools": [], "risk": "read",
                                     "permission": s.permission})
        r["tools"].append(s.name)
        if RISK_ORDER.get(s.risk, 0) > RISK_ORDER.get(r["risk"], 0):
            r["risk"], r["permission"] = s.risk, s.permission
    for r in rows.values():
        r.update({k: v for k, v in store.policy(team_id, r["tag"]).items() if k in ("who", "approvers", "updatedBy")})
    return sorted(rows.values(), key=lambda r: (RISK_ORDER.get(r["risk"], 0), r["tag"]))


def make_filter(store):
    """Deps.policy: drop the tools this requester may not use; tell the model what was dropped."""
    def policy_filter(request: dict, specs: list) -> list:
        team = request["teamId"]
        owner = store.is_owner(team, request.get("requesterAad"))
        allowed, dropped = [], []
        for s in specs:
            who = store.policy(team, s.rbac)["who"]
            if who == "nobody" or (who == "owners" and not owner):
                dropped.append(LABELS.get(s.rbac, s.rbac))
            else:
                allowed.append(s)
        request["restricted"] = sorted(set(dropped))
        return allowed
    return policy_filter


def approver_ids(store, team_id: str, tag: str, requester_aad: str | None) -> tuple[set, list[dict]]:
    """(AAD ids allowed to approve, owner rows) for an action with this RBAC tag."""
    owners = [dict(r) for r in store.owners(team_id)]
    ids = {o["aad_id"] for o in owners if o["aad_id"]}
    if store.policy(team_id, tag)["approvers"] == "requester_or_owner" and requester_aad:
        ids.add(requester_aad)
    return ids, owners
