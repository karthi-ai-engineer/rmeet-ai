"""
Short replies posted as a NEW post ("@Max yes go ahead") instead of in the thread where Max asked its question.

In Teams a new post is a new thread, so Max would see only "yes go ahead" and have nothing to act on. If the new
post is a short answer and Max asked the same person a question in another thread a few minutes ago, the agent gets
that exchange as context, and can carry on with it (for example put the meeting it proposed on an approval card).
Nothing is done without the usual approval card.
"""

import json

MAX_WORDS = 10
WITHIN_S = 15 * 60


def is_short_reply(text: str) -> bool:
    """'yes go ahead', 'Prince and Daniel', 'make it 2 pm': short enough to be an answer to a question."""
    return 0 < len((text or "").split()) <= MAX_WORDS


def earlier_question(store, team_id: str, requester: str, thread_root: str, now_ts: float) -> str | None:
    """Context if Max is waiting on this person in ANOTHER thread (within 15 minutes): an approval card they asked
    for (approving is a click on the card, never a chat message), or a question Max asked them."""
    cards = [p for p in store.pendings(team_id, "pending") if p["requester"] == requester
             and p["thread_root"] != thread_root and now_ts - p["created_at"] <= WITHIN_S]
    if cards:
        p = cards[-1]
        prev = json.loads(p["preview"])
        facts = dict(prev.get("facts") or [])
        what = facts.get("Title") or facts.get("Subject") or prev.get("title") or p["tool"]
        mins = max(1, round((now_ts - p["created_at"]) / 60))
        return (f"EARLIER IN ANOTHER THREAD ({mins} min ago): you posted an approval card for {requester}: "
                f"{prev.get('kind') or 'action'} '{what}'" + (f", {facts['When']}" if facts.get("When") else "") +
                ". It is still waiting. If their new post below means yes / go ahead / approve, tell them to press "
                "Approve on that card (approving is always a click on the card, so a chat message can't do it; "
                "Change edits it). Don't create a second card for the same thing.")
    for r in store.runs(team_id, 30):
        if r["requester"] != requester or not str(r["trigger"]).startswith("mention"):
            continue
        if r["thread_id"] == thread_root:
            continue
        if now_ts - r["started_at"] > WITHIN_S:
            return None
        reply = (r["summary"] or "").strip()
        if not reply.rstrip("*_ ").endswith("?"):
            return None                     # Max's latest reply to them wasn't a question: nothing to continue
        asked = next((json.loads(a["detail"]).get("text", "") for a in store.audit_for(r["id"])
                      if a["kind"] == "question"), "")
        mins = max(1, round((now_ts - r["started_at"]) / 60))
        return (f"EARLIER IN ANOTHER THREAD ({mins} min ago): {requester} asked you: \"{asked}\"\n"
                f"and you replied: \"{reply}\"\n"
                f"If their new post below answers that question, carry on with that request here (the usual approval "
                f"card is still needed for anything you send or book); if it's about something else, just answer it.")
    return None
