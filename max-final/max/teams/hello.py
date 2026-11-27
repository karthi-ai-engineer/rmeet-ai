"""
Step 2: Max's first words. No AI yet: Max proves the whole path works (Teams -> Max -> Teams).

Like a polite teammate, Max answers in its own 1:1 chat always, and in channels and group chats only when
someone @mentions it.
"""

from __future__ import annotations


def should_answer(conversation_type: str | None, mentioned: bool) -> bool:
    return conversation_type == "personal" or mentioned


def hello_text(sender_name: str | None) -> str:
    first = (sender_name or "").strip().split(" ")[0]
    return f"Hi {first}, I'm Max. I'm connected 👋" if first else "Hi, I'm Max. I'm connected 👋"
