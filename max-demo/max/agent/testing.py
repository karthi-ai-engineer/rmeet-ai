"""
Test kit for the agent ($0: no model is called unless a test records on purpose).

  ScriptedChatModel  a fake chat model that returns pre-written replies (text or tool calls) in order
  ai_call / ai_text  build those replies
  CassetteHandle     records real model replies once and replays them; a prompt with no recording raises
                     CassetteMiss (it never calls the model by itself)
  tool_pair_problems the history rule: every tool call gets exactly one result before the next model call
"""

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any, Callable

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage, messages_from_dict, messages_to_dict
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import Field


# ----------------------------------------------------------------------------- scripted model
def ai_call(*calls: tuple[str, dict], text: str = "") -> AIMessage:
    """ai_call(("search_memory", {"query": "pilot"}), ("find_free_times", {...})) -> one AIMessage with tool calls."""
    return AIMessage(content=text, tool_calls=[
        {"name": name, "args": args, "id": f"call_{name}_{uuid.uuid4().hex[:8]}", "type": "tool_call"}
        for name, args in calls])


def ai_text(text: str) -> AIMessage:
    return AIMessage(content=text)


class ScriptedChatModel(BaseChatModel):
    """Returns `replies` in order. A reply may be a function(messages) -> AIMessage, to react to the history."""

    replies: list[Any] = Field(default_factory=list)
    calls: list[list[BaseMessage]] = Field(default_factory=list)       # the history the model saw, per call
    tool_names: list[list[str]] = Field(default_factory=list)          # tools offered, per bind

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: list, **kwargs) -> "ScriptedChatModel":
        self.tool_names.append([convert_to_openai_tool(t)["function"]["name"] for t in tools])
        return self

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.calls.append(list(messages))
        if not self.replies:
            raise AssertionError(f"scripted model ran out of replies (call {len(self.calls)})")
        nxt = self.replies.pop(0)
        msg = nxt(messages) if callable(nxt) else nxt
        msg = msg.model_copy(deep=True)
        if msg.usage_metadata is None:
            msg.usage_metadata = {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}
        return ChatResult(generations=[ChatGeneration(message=msg)])


# ----------------------------------------------------------------------------- cassettes
class CassetteMiss(Exception):
    """No recorded reply for this exact prompt. Re-record on purpose (it costs model requests)."""


_VOLATILE = ("id", "response_metadata", "usage_metadata")


def prompt_key(model_id: str, messages: list[BaseMessage], tools: list | None) -> str:
    """Stable fingerprint of one model call: model + history (minus run ids and usage) + tool schemas."""
    hist = []
    for d in messages_to_dict(messages):
        data = {k: v for k, v in d["data"].items() if k not in _VOLATILE}
        hist.append({"type": d["type"], "data": data})
    payload = {"model": model_id, "messages": hist,
               "tools": [convert_to_openai_tool(t) for t in (tools or [])]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


class CassetteHandle:
    """Same interface as models.ChatHandle. Replays recorded replies; records only when record=True."""

    def __init__(self, path: Path | str, inner=None, record: bool = False):
        self.path = Path(path)
        self.inner, self.record = inner, record
        self.data = (json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists()
                     else {"model": getattr(inner, "model_id", ""), "calls": {}})
        self.model_id = getattr(inner, "model_id", None) or self.data.get("model", "")
        self.provider = getattr(inner, "provider", "cassette")
        self.replayed = self.recorded = 0

    async def ainvoke(self, messages: list[BaseMessage], tools: list | None = None, kind: str = "agent") -> AIMessage:
        key = prompt_key(self.model_id, messages, tools)
        hit = self.data["calls"].get(key)
        if hit is not None:
            self.replayed += 1
            return messages_from_dict([hit["reply"]])[0]
        if not (self.record and self.inner is not None):
            raise CassetteMiss(f"no recorded reply for this prompt (key {key[:12]}) in {self.path.name}; "
                               "the prompt or tools changed: re-record on purpose")
        msg = await self.inner.ainvoke(messages, tools, kind)
        self.recorded += 1
        last = messages[-1]
        self.data["model"] = self.model_id
        self.data["calls"][key] = {"n": len(self.data["calls"]) + 1,
                                   "after": f"{last.type}: {str(last.content)[:80]}",
                                   "reply": messages_to_dict([msg])[0]}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=1, ensure_ascii=False), encoding="utf-8")
        return msg


# ----------------------------------------------------------------------------- history rule
def tool_pair_problems(messages: list[BaseMessage]) -> list[str]:
    """Every tool call needs exactly one ToolMessage before the next AI message. Returns the problems found."""
    problems, open_ids = [], []
    for m in messages:
        if isinstance(m, AIMessage):
            if open_ids:
                problems.append(f"model called again with unanswered tool calls {open_ids}")
            open_ids = [c["id"] for c in m.tool_calls]
        elif isinstance(m, ToolMessage):
            if m.tool_call_id in open_ids:
                open_ids.remove(m.tool_call_id)
            else:
                problems.append(f"result for unknown or already answered call {m.tool_call_id}")
    return problems
