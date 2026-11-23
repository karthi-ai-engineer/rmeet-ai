"""
Max doing things live in a meeting (Phase 5.2, docs/plans/phase5-meeting-actions.md).

  heard "Max, …" -> wants_action()? -- no  -> classic meeting answer (whole memory, one fast call)
                                      `- yes -> agent run, source "meeting" (same tools, policies and approval cards
                                                as in the channel); a paused run gets pause_line() in the call
  end of meeting -> done_section() lists what was approved, done, cancelled or still waiting

Pure helpers (no Teams or HTTP code) so they can be tested offline.
"""

import json
import os
import re

# hybrid (default): actions through the agent, questions through the fast classic answer
# agent: everything through the agent;  classic: no actions in meetings
MEETING_BRAIN = os.environ.get("MAX_MEETING_BRAIN", "hybrid").strip().lower()

# Words that ask Max to DO something (generous on purpose: the agent answers plain questions well too, but a
# missed action would get the classic "I can't do that here").
ACTION_RE = re.compile(
    r"\b(book|schedule|re-?schedule|set ?up|arrange|organi[sz]e|plan|invite|put .{0,30}(?:calendar|diary)|"
    r"cancel|call off|move|push|postpone|shift|"
    r"e-?mail|mail|send|forward|write to|message|"
    r"remind|reminder|follow[- ]?up|"
    r"add (?:a |an |the )?(?:task|action|to-?do)|create (?:a |an )?(?:task|action)|assign|"
    r"mark .{0,40}(?:done|complete|closed)|close (?:the |that )?task|update (?:the |that )?task|"
    r"change (?:the |that )?(?:deadline|due)|extend|"
    r"upload|save .{0,30}(?:file|notes|doc)|share .{0,20}(?:file|doc))\b", re.IGNORECASE)

QUESTION_START = re.compile(r"^\s*(?:max[\s,:]*)?(?:what|when|who|whom|whose|which|why|how|where|is|are|was|were|"
                            r"did|do|does|has|have|had|can you (?:tell|remind me what|explain|check what))\b",
                            re.IGNORECASE)

KIND_LABEL = {"meeting": "meeting invite", "email": "email", "upload": "file", "task": "deadline change"}


def label(kind: str | None, title: str | None = None) -> str:
    if kind == "meeting" and (title or "").lower().startswith("cancel"):
        return "meeting cancellation"
    return KIND_LABEL.get(kind or "", "request")


REMIND_QUESTION = re.compile(r"\bremind (?:me|us)\b[,:\s]+(?:what|when|who|whom|which|how|why|where|whether|if)\b",
                             re.IGNORECASE)


def addressed_part(text: str) -> str:
    """The words spoken to Max: from where Max is named to the end. ("I'll send the budget to Elena. Max, please
    post the summary." -> "Max, please post the summary."; "Solid plan, but Max, what's the risk?" -> "Max, what's
    the risk?")"""
    m = re.search(r"\bmax\b", text or "", re.IGNORECASE)
    return text[m.start():] if m else (text or "")


def wants_action(text: str, mode: str | None = None) -> bool:
    """Should this line (addressed to Max) go to the agent (tools + approvals)?"""
    mode = (mode or MEETING_BRAIN)
    if mode == "agent":
        return True
    if mode == "classic":
        return False
    text = addressed_part(text)
    if REMIND_QUESTION.search(text):                # "Max, remind me, what uplift did I estimate?" = a question
        return False
    if not ACTION_RE.search(text):
        return False
    # "When did we send the email to Elena?" is a question about the past, not a request
    if QUESTION_START.search(text) and not re.search(r"\b(?:can|could|would|will) you\b|\bplease\b", text, re.I):
        return bool(re.search(r"\b(?:should we|shall we|let'?s)\b", text, re.I))
    return True


def request_text(transcript: list[tuple[str, str]], speaker: str, said: str, last_n: int = 25) -> str:
    lines = "\n".join(f"{s}: {t}" for s, t in transcript[-last_n:])
    return (f"THE MEETING SO FAR (live transcript, oldest first):\n{lines}\n\n"
            f"{speaker} just said to you in the call: \"{said}\"")


def _names(approvers: list[dict]) -> str:
    names = [a["name"] for a in approvers if a.get("name")]
    if not names:
        return "the team owner"
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " or " + names[-1]


def pause_line(kind: str | None, approvers: list[dict], title: str | None = None) -> str:
    """What Max says in the call when an approval card went to the meeting chat (no model call)."""
    what = label(kind, title)
    return f"I've put the {what} in the meeting chat for {_names(approvers)} to approve."


STATUS_WORDS = {"done": "✅ Done", "failed": "⚠️ Not done", "cancelled": "✖ Cancelled", "expired": "⌛ Expired",
                "superseded": "✏️ Changed", "pending": "⏳ Waiting for approval", "approved": "⏳ Approved, in progress",
                "executing": "⏳ Approved, in progress"}


def done_section(pendings: list) -> str:
    """'Done during the meeting' for the notes: every action asked for in this meeting and how it ended."""
    lines = []
    for p in pendings:
        if p["status"] == "superseded":            # replaced after "Change": only the final version counts
            continue
        prev = json.loads(p["preview"])
        facts = dict(prev.get("facts") or [])
        what = facts.get("Title") or facts.get("Subject") or facts.get("File") or facts.get("Task") or prev.get("title")
        kind = label(prev.get("kind"), prev.get("title"))
        detail = facts.get("When") or facts.get("To") or ""
        status = STATUS_WORDS.get(p["status"], p["status"])
        by = f" by {p['decided_by']}" if p["decided_by"] and p["status"] in ("done", "approved", "executing", "failed") else ""
        lines.append(f"- {status}{' (approved' + by + ')' if by else ''}: {kind} '{what}'"
                     + (f", {detail}" if detail else "") + (f" (asked by {p['requester']})" if p["requester"] else ""))
    return ("**Done during the meeting**\n" + "\n".join(lines)) if lines else ""


async def run_request(call, speaker: str, speaker_aad: str | None, said: str, *, graph, store, approvals,
                      runs: dict, locks: dict) -> dict:
    """'Max, book a follow-up…' heard in a call: an agent run with the meeting as context. Its approval card goes to
    the meeting chat (the meeting's thread) and Max says one line about it in the call (no model call)."""
    import asyncio

    from agent.graph import new_request, start_run
    root = call.conversation_id.split(";messageid=")[1] if ";messageid=" in call.conversation_id else None
    req = new_request(store, call.team_id, "meeting", speaker, speaker_aad, root,
                      meeting={"title": call.title, "people": call.people()})
    store.audit(req["runId"], call.team_id, "question", {"from": speaker, "text": said, "meeting": call.title})
    call.run_ids.append(req["runId"])
    runs[req["runId"]] = call
    async with locks.setdefault(root or req["runId"], asyncio.Lock()):
        result = await start_run(graph, req, request_text(call.session.transcript[:-1], speaker, said))
    paused = await announce_pause(call, result, store, approvals)
    return {"runId": req["runId"], "paused": paused}


async def announce_pause(call, result: dict, store, approvals, updated: bool = False) -> bool:
    """If the run is waiting for an approval, say so in the call (one line, no model call). True if waiting."""
    paused = (result or {}).get("__interrupt__")
    if not paused:
        return False
    p = store.pending(paused[0].value["pendingId"])
    prev = json.loads(p["preview"])
    line = pause_line(prev.get("kind"), approvals.approvers(p), prev.get("title"))
    await call.say(line.replace("I've put the ", "I've put the updated ", 1) if updated else line)
    return True


def make_deliver(runs: dict, post):
    """The agent's reply to a meeting request: said in the call while it lasts, else posted in the meeting thread
    (e.g. a card approved after the meeting ended, or after Max restarted)."""
    async def deliver(request: dict, reply: str) -> None:
        call = runs.get(request.get("runId"))
        if call is not None and not call.finished:
            await call.say(reply)
        else:
            await post(request["teamId"], reply, [], request.get("threadRoot"))
    return deliver


# ------------------------------------------------------------------ end-of-meeting check (Phase 5.3)
# Anyone closing the meeting ("let's wrap up") -> Max reads back the draft once; asking Max for a recap -> any time.
WRAP_UP_RE = re.compile(
    r"\bwrap(?:ping)? (?:it |this |things |everything )?up\b|\bto (?:wrap|sum) (?:it |things )?up\b|"
    r"\blet'?s (?:close|finish|end|stop) (?:it |things )?(?:here|there|now|for today|the meeting|this meeting|up)\b|"
    r"\b(?:that'?s|that is) (?:all|it|everything) for (?:today|now)\b|"
    r"\bbefore we (?:finish|end|close|wrap|go|leave|hang up|drop)\b|\bany other business\b|\bend (?:the|this) meeting\b",
    re.IGNORECASE)
RECAP_RE = re.compile(
    r"\b(?:recap|summari[sz]e|sum (?:it |things |everything )?up|read (?:it |them |that |everything )?back|"
    r"go (?:over|through) (?:the |our )?(?:decisions|action items|actions|notes|next steps)|"
    r"what (?:did|have) we (?:decide|agree)d?|what (?:are|were) (?:the|our) (?:decisions|action items|next steps))\b",
    re.IGNORECASE)
MIN_LINES_FOR_RECAP = 6         # an automatic recap needs a real meeting behind it


def wants_recap(text: str, addressed: bool, recaps_done: int = 0, lines: int = 99) -> bool:
    """Read back the draft notes now?  Asked ("Max, recap please") -> yes, any time.
    Someone closes the meeting ("OK, let's wrap up") -> yes, once, if the meeting had some substance."""
    if addressed and (RECAP_RE.search(addressed_part(text)) or WRAP_UP_RE.search(addressed_part(text))):
        return True
    return bool(WRAP_UP_RE.search(text or "")) and recaps_done == 0 and lines >= MIN_LINES_FOR_RECAP
