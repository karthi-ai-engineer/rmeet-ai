"""
Max's thinking (Qwen). Pure functions over text: no Teams or HTTP code here,
so the same brain serves the channel thread, meetings and (later) other platforms.
"""

import re

from llm import parse_json, qwen_chat

THREAD_RULES = """You are Max, an AI teammate installed in a Microsoft Teams team. People @mention you in channel
threads. Today is {today}.

How to reply in a thread:
- Be a helpful, precise colleague. Usually 1-4 short sentences. Use a short bullet list only when asked
  for a list or summary. Light Markdown is fine (bold, bullets); no headings.
- Use ONLY the channel knowledge below and the thread you are replying in. Quote exact numbers, names, dates.
- Say where it came from naturally (e.g. "per Prince's budget draft v2 (12 Nov)", "in the 20 Oct meeting").
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
- Mention where it came from in a natural way (e.g. "in the 20 October meeting", "Daniel's post on 18 November").
- If the answer isn't in your knowledge, say so briefly. Never invent facts.
- If you're asked to do something (like post the summary), confirm briefly.

CHANNEL KNOWLEDGE (thread, documents, past meetings):
"""

SUMMARY_PROMPT = """The meeting has ended. Using ONLY the meeting transcript below, write the meeting notes.
Return ONLY a JSON object with these keys:
{
  "summary": "3-5 sentences: what was discussed and the outcome",
  "decisions": ["each decision actually made in the meeting, with the key numbers"],
  "action_items": [{"owner": "full name", "task": "what", "due": "YYYY-MM-DD or empty"}],
  "risks": ["risks or open concerns mentioned"],
  "final_total_k": number or null
}
Use full names (Karthi M, Prince Raj, Daniel Ito, Jacob Thomas). Today is {today_iso}, so convert dates like
"Tuesday the 24th" to the right YYYY-MM-DD.

MEETING TRANSCRIPT:
"""

TODAY = "Friday 20 Nov 2026"
TODAY_ISO = "2026-11-20"


def answer_in_thread(knowledge: str, thread: list[tuple[str, str]], asker: str, question: str) -> str:
    """thread: [(author, text)] oldest first, including the message that mentioned Max."""
    convo = "\n".join(f"{a}: {t}" for a, t in thread[-30:])
    reply = qwen_chat([
        {"role": "system", "content": THREAD_RULES.format(today=TODAY) + knowledge},
        {"role": "user", "content": f"THE THREAD YOU ARE REPLYING IN:\n{convo}\n\n"
                                    f"{asker} just asked you: \"{question}\"\nWrite your reply now (only the reply)."},
    ], max_tokens=450, temperature=0.3, timeout=40)
    return re.sub(r"^\s*max\s*(\(ai\))?\s*:\s*", "", reply, flags=re.IGNORECASE).strip()


def warm(knowledge: str, rules: str) -> None:
    """Send the big knowledge prompt once so the model server can cache it (faster answers later)."""
    try:
        qwen_chat([{"role": "system", "content": rules.format(today=TODAY) + knowledge},
                   {"role": "user", "content": "Reply with OK."}], max_tokens=3, temperature=0, timeout=40)
    except Exception:
        pass


class MeetingSession:
    """One live meeting: Max hears every line, answers when addressed, writes notes at the end."""

    ADDRESS_RE = re.compile(r"\bmax\b", re.IGNORECASE)

    def __init__(self, meeting_id: str, title: str, knowledge: str):
        self.meeting_id, self.title, self.knowledge = meeting_id, title, knowledge
        self.transcript: list[tuple[str, str]] = []

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
            {"role": "system", "content": MEETING_RULES.format(today=TODAY) + self.knowledge},
            {"role": "user", "content": "CURRENT MEETING TRANSCRIPT (so far):\n" + self._text(40) +
                                        f"\n\n{speaker} just spoke to you: \"{text}\"\nReply now as Max (only the words you say)."},
        ], max_tokens=220, temperature=0.3, timeout=30)
        reply = re.sub(r"^\s*max\s*(\(ai\))?\s*:\s*", "", reply, flags=re.IGNORECASE).strip()
        self.transcript.append(("Max", reply))
        return reply

    def summarize(self) -> dict:
        raw = qwen_chat([
            {"role": "system", "content": "You are Max, an accurate AI meeting note-taker. Output valid JSON only."},
            {"role": "user", "content": SUMMARY_PROMPT.replace("{today_iso}", TODAY_ISO) + self._text()},
        ], max_tokens=1400, temperature=0.2, timeout=60)
        data = parse_json(raw) or {"summary": raw}
        for k, v in (("decisions", []), ("action_items", []), ("risks", []), ("final_total_k", None)):
            data.setdefault(k, v)
        return data


def notes_markdown(title: str, notes: dict) -> str:
    """Meeting notes as a channel post."""
    lines = [f"**📝 Meeting notes: {title}**", "", notes.get("summary", "")]
    if notes.get("decisions"):
        lines += ["", "**Decisions**"] + [f"- {d}" for d in notes["decisions"]]
    if notes.get("action_items"):
        lines += ["", "**Action items**"]
        lines += [f"- {a.get('owner', '?')}: {a.get('task', '')}" + (f" (due {a['due']})" if a.get("due") else "")
                  for a in notes["action_items"]]
    if notes.get("risks"):
        lines += ["", "**Risks**"] + [f"- {r}" for r in notes["risks"]]
    return "\n".join(lines)
