"""
Max's thinking (Qwen). Pure functions over text: no Teams or HTTP code here,
so the same brain serves the channel thread, meetings and (later) other platforms.
"""

import re
from datetime import datetime

from llm import BRAIN_PROVIDER, parse_json, qwen_chat

THREAD_RULES = """You are Max, an AI teammate installed in a Microsoft Teams team. People @mention you in channel
threads. Today is {today}.

How to reply in a thread:
- Be a helpful, precise colleague. Usually 1-4 short sentences. Use a short bullet list only when asked
  for a list or summary. Light Markdown is fine (bold, bullets); no headings.
- Use ONLY the channel knowledge below and the thread you are replying in. Quote exact numbers, names, dates.
- Say where it came from naturally (e.g. "per the weekly S&OP report (23 Nov)", "in the 17 Nov meeting").
- If the answer isn't in your knowledge, say so briefly and suggest who might know. Never invent facts.
- If a question needs meeting transcripts you can't access, say why (see the access notes) instead of guessing.
- "Who said X" questions: use the speaker label of the exact transcript line (the name before the colon), not
  who presented the topic or who is mentioned in the minutes.
- If asked to do something you can't do yet (send emails, edit files), say so politely.

CHANNEL KNOWLEDGE (channel posts, files, Teams meetings and official transcripts; read through Microsoft Graph
and kept up to date with change notifications):
"""

MEETING_RULES = """You are Max, an AI meeting assistant in the team's live meeting. You are shown as a friendly
orange cloud. Today is {today}.

How to answer when someone talks to you:
- Speak like a helpful colleague in a meeting: 1-3 short sentences, plain spoken English, no markdown, no lists.
- Use ONLY the channel knowledge below and the current meeting transcript. Quote exact numbers, names and dates.
- Mention where it came from in a natural way (e.g. "in the 17 November meeting", "the pricing file from 24 November").
- If the answer isn't in your knowledge, say so briefly. Never invent facts.
- Meeting notes are posted in the meeting thread automatically when the meeting ends: if asked for them, say so.
- If someone corrects the notes or your recap (a date, an owner, a missing item), confirm it in one short sentence
  ("Got it: that confirmation is due Friday 27 November."); the final notes will use the correction.
- Never say you have sent, booked, cancelled or changed anything (emails, meetings, tasks, files). If asked for
  such an action, say: "Ask me with the exact request, for example 'Max, book…' or 'Max, email…', and I'll put it
  in the chat for approval."

CHANNEL KNOWLEDGE (thread, documents, past meetings):
"""

SUMMARY_PROMPT = """The meeting has ended. Using ONLY the meeting transcript below, write the meeting notes.
Return ONLY a JSON object with these keys:
{
  "summary": "3-5 sentences: what was discussed and the outcome",
  "decisions": ["each decision actually made in the meeting, with ALL its numbers (amounts with units, quantities, %, dates)"],
  "action_items": [{"owner": "full name", "task": "what", "due": "YYYY-MM-DD or empty"}],
  "risks": ["risks or open concerns mentioned"],
  "final_number": "the main final figure the meeting agreed (e.g. a budget total or a forecast), with its unit, or null"
}
Use people's full names as they appear in the transcript. Today is {today_iso}, so convert dates like
"Tuesday the 24th" or "tomorrow" to the right YYYY-MM-DD.
Action items are work for PEOPLE: Max (the AI) is never an owner, and what Max already did during the meeting
(emails sent, meetings booked) is not an action item.
If Max read out a draft recap near the end, people's corrections after it are the truth: use them.

MEETING TRANSCRIPT:
"""

def today_text() -> str:
    """'Thursday 26 Nov 2026' (real date; meetings pass their own date)."""
    d = datetime.now()
    return f"{d:%A} {d.day} {d:%b %Y}"


def today_iso() -> str:
    return f"{datetime.now():%Y-%m-%d}"


def answer_in_thread(knowledge: str, thread: list[tuple[str, str]], asker: str, question: str) -> str:
    """thread: [(author, text)] oldest first, including the message that mentioned Max."""
    convo = "\n".join(f"{a}: {t}" for a, t in thread[-30:])
    reply = qwen_chat([
        {"role": "system", "content": THREAD_RULES.format(today=today_text()) + knowledge},
        {"role": "user", "content": f"THE THREAD YOU ARE REPLYING IN:\n{convo}\n\n"
                                    f"{asker} just asked you: \"{question}\"\nWrite your reply now (only the reply)."},
    ], max_tokens=450, temperature=0.3, timeout=40)
    return re.sub(r"^\s*max\s*(\(ai\))?\s*:\s*", "", reply, flags=re.IGNORECASE).strip()


def warm(knowledge: str, rules: str) -> None:
    """Send the big knowledge prompt once so the model server can cache it (faster answers later).
    Skipped on Gemini: it would spend a full-size request just to get "OK" back."""
    if BRAIN_PROVIDER == "gemini":
        return
    try:
        qwen_chat([{"role": "system", "content": rules.format(today=today_text()) + knowledge},
                   {"role": "user", "content": "Reply with OK."}], max_tokens=3, temperature=0, timeout=40)
    except Exception:
        pass


class MeetingSession:
    """One live meeting: Max hears every line, answers when addressed, writes notes at the end."""

    ADDRESS_RE = re.compile(r"\bmax\b", re.IGNORECASE)

    def __init__(self, meeting_id: str, title: str, knowledge: str, today=None):
        """today: the meeting's date (a datetime in the team's time zone); default = the scenario's date."""
        self.meeting_id, self.title, self.knowledge = meeting_id, title, knowledge
        self.transcript: list[tuple[str, str]] = []
        self.today = f"{today:%A} {today.day} {today:%b %Y}" if today else today_text()
        self.today_iso = f"{today:%Y-%m-%d}" if today else today_iso()

    def hear(self, speaker: str, text: str) -> bool:
        """Store the line; return True if it was addressed to Max."""
        self.transcript.append((speaker, text))
        return speaker.lower() not in ("max", "max (ai)") and bool(self.ADDRESS_RE.search(text))

    def _text(self, last_n: int | None = None) -> str:
        lines = self.transcript if last_n is None else self.transcript[-last_n:]
        return "\n".join(f"{s}: {t}" for s, t in lines)

    def answer(self) -> str:
        speaker, text = self.transcript[-1]
        reply = qwen_chat([
            {"role": "system", "content": MEETING_RULES.format(today=self.today) + self.knowledge},
            {"role": "user", "content": "CURRENT MEETING TRANSCRIPT (so far):\n" + self._text(40) +
                                        f"\n\n{speaker} just spoke to you: \"{text}\"\nReply now as Max (only the words you say)."},
        ], max_tokens=220, temperature=0.3, timeout=30)
        reply = re.sub(r"^\s*max\s*(\(ai\))?\s*:\s*", "", reply, flags=re.IGNORECASE).strip()
        self.transcript.append(("Max", reply))
        return reply

    def summarize(self) -> dict:
        raw = qwen_chat([
            {"role": "system", "content": "You are Max, an accurate AI meeting note-taker. Output valid JSON only."},
            {"role": "user", "content": SUMMARY_PROMPT.replace("{today_iso}", self.today_iso) + self._text()},
        ], max_tokens=1400, temperature=0, timeout=60, purpose="notes")
        data = parse_json(raw) or {"summary": raw}
        for k, v in (("decisions", []), ("action_items", []), ("risks", []), ("final_number", None)):
            data.setdefault(k, v)
        data["action_items"] = [a for a in data["action_items"] if isinstance(a, dict) and not is_max(a.get("owner"))]
        return data


def is_max(name) -> bool:
    """Max (the AI) never owns an action item."""
    return bool(re.fullmatch(r"\s*max(?:\s*\(ai\))?\s*", str(name or ""), re.IGNORECASE))


def recap_text(notes: dict) -> tuple[str, str]:
    """The end-of-meeting check (no extra model call): (spoken recap, meeting-chat draft). Plain words for the call,
    formatted draft for the chat; both end by asking for corrections."""
    dec = [d for d in notes.get("decisions") or [] if isinstance(d, str) and d.strip()]
    acts = [a for a in notes.get("action_items") or [] if isinstance(a, dict) and (a.get("task") or "").strip()]

    def due(a, fmt="%a %d %b"):
        try:
            from datetime import date
            return f" by {date.fromisoformat(a['due']).strftime(fmt)}" if a.get("due") else ""
        except ValueError:
            return f" by {a['due']}"

    def said(task: str) -> str:                     # "Confirm the quote." -> "confirm the quote"
        task = task.strip().rstrip(".")
        return task[:1].lower() + task[1:] if task[:2] != task[:2].upper() else task

    def n(k, word):
        return f"{k} {word}{'' if k == 1 else 's'}"
    if not dec and not acts:
        spoken = ("Before we finish: I haven't noted any decisions or action items yet. "
                  "Is there anything I should add?")
    else:
        parts = [f"Before we finish, here's what I have: {n(len(dec), 'decision')} and {n(len(acts), 'action item')}."]
        if dec:
            parts.append("Decisions: " + "; ".join(d.rstrip(".") for d in dec) + ".")
        if acts:
            parts.append("Actions: " + "; ".join(f"{a.get('owner') or 'someone'}, {said(a['task'])}{due(a, '%A %d %B')}"
                                                 for a in acts) + ".")
        parts.append("Is anything missing or wrong?")
        spoken = " ".join(parts)
    lines = ["**📋 Before we finish: draft notes**"]
    lines += ["", "**Decisions**"] + ([f"- {d}" for d in dec] or ["- (none yet)"])
    lines += ["", "**Action items**"] + ([f"- {a.get('owner') or '?'}: {a['task']}{due(a)}" for a in acts]
                                          or ["- (none yet)"])
    lines += ["", "_Anything missing or wrong? Say it now (e.g. \"Max, that date is the 27th\") and the final "
                  "notes will include it._"]
    return spoken, "\n".join(lines)


def notes_markdown(title: str, notes: dict) -> str:
    """Meeting notes as a channel post."""
    lines = [f"**📝 Meeting notes: {title}**", "", notes.get("summary", "")]
    if notes.get("final_number"):
        lines += ["", f"**Final number:** {notes['final_number']}"]
    if notes.get("decisions"):
        lines += ["", "**Decisions**"] + [f"- {d}" for d in notes["decisions"]]
    if notes.get("action_items"):
        lines += ["", "**Action items**"]
        lines += [f"- {a.get('owner', '?')}: {a.get('task', '')}" + (f" (due {a['due']})" if a.get("due") else "")
                  for a in notes["action_items"]]
    if notes.get("risks"):
        lines += ["", "**Risks**"] + [f"- {r}" for r in notes["risks"]]
    return "\n".join(lines)
