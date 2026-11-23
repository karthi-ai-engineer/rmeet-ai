"""
Step 4.0 spike: a small LangGraph graph with the same shape as the Phase 4 design, to prove
tool calling (incl. two calls at once), the safety gate, and the approval pause/resume with saved runs.

  agent ⇄ tools                         read tools loop
  agent → prepare_approval → agent      a safety rule blocked the step (result goes back to the model)
  agent → prepare_approval → await_approval (interrupt) → execute → agent
                                       await_approval → agent (change) / respond (cancel, expired)
  agent → respond → END

Tools work on a tiny in-memory world (no Microsoft calls). The real tools and graph come in step 4.3.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Annotated, Any, TypedDict
from zoneinfo import ZoneInfo

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command, interrupt

from .clock import Clock
from .models import BudgetBlocked, ModelError

MAX_STEPS = 6
TEAM_TZ = ZoneInfo("Europe/London")


# ----------------------------------------------------------------------------- the tiny world
@dataclass
class SpikeWorld:
    clock: Clock
    company: dict = field(default_factory=lambda: {
        "Karthi M": "karthi@kestrel.example", "Prince Alex": "prince@kestrel.example",
        "Daniel": "daniel@kestrel.example", "Jacob Thomas": "jacob@kestrel.example"})
    memory: list = field(default_factory=lambda: [
        "20 Oct meeting: shortlisted Vector Robotics and LiftLine Systems for warehouse automation; "
        "LiftLine's lead time is 14 weeks.",
        "Budget Review 20 Nov: approved the Riverside-only pilot with Vector Robotics (200K), "
        "covering the 95K gap with options D and E. Daniel to confirm Vector's Riverside quote by 25 Nov."])
    busy: dict = field(default_factory=lambda: {"Daniel": ["09:00", "11:00"], "Prince Alex": ["15:00"]})
    events: dict = field(default_factory=dict)       # transactionId -> event (creating twice is a no-op)
    replies: list = field(default_factory=list)      # what Max posted

    def free_times(self, date: str, attendees: list[str], minutes: int) -> list[str]:
        busy = {t for a in attendees for t in self.busy.get(a, [])}
        return [f"{date} {h}" for h in ("09:00", "10:00", "11:00", "14:00", "15:00", "16:00") if h not in busy][:3]


READ, EXTERNAL = "read", "external"


def make_tools(world: SpikeWorld) -> tuple[list, dict]:
    @tool
    def search_memory(query: str) -> str:
        """Search the team's memory (channel posts, files, past meetings) for facts about a topic."""
        words = [w for w in query.lower().split() if len(w) > 2]
        hits = [m for m in world.memory if any(w in m.lower() for w in words)]
        return "\n".join(hits) or "No matching notes."

    @tool
    def find_free_times(date: str, attendees: list[str], minutes: int = 30) -> str:
        """Find free meeting start times on a date (YYYY-MM-DD) when all attendees (full names) are free."""
        unknown = [a for a in attendees if a not in world.company]
        if unknown:
            return f"Unknown people: {', '.join(unknown)}. Known: {', '.join(world.company)}."
        return "Free for everyone: " + ", ".join(world.free_times(date, attendees, minutes))

    @tool
    def create_meeting(title: str, start: str, minutes: int, attendees: list[str], agenda: str = "") -> str:
        """Create a Teams meeting in Max's calendar and send the invites. start is 'YYYY-MM-DD HH:MM' in the
        team's time zone; attendees are full names or email addresses. A person must approve it first."""
        return "not run here: create_meeting runs only after approval"

    tools = [search_memory, find_free_times, create_meeting]
    risk = {"search_memory": READ, "find_free_times": READ, "create_meeting": EXTERNAL}
    return tools, risk


# ----------------------------------------------------------------------------- state
class SpikeState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    pending: dict | None        # the call waiting for approval: {"call": ..., "preview": ...}
    decision: dict | None       # {"action": "approve|change|cancel|expired", "by": ..., "edit": ...}
    steps: int


def system_prompt(world: SpikeWorld) -> str:
    now = world.clock.now().astimezone(TEAM_TZ)
    tomorrow = (now + timedelta(days=1)).strftime("%A %d %B %Y (%Y-%m-%d)")
    return ("You are Max, an AI teammate in the Planning Department's Teams channel. Use the tools to look things "
            "up and to act. To set up a meeting: find free times first, then call create_meeting right away with "
            "the earliest time everyone is free (unless the person named a time). Don't ask which time in chat: "
            "the person sees your proposal on an approval card and can approve it or ask for a change there. "
            "Use full names. If a tool says something was blocked or not done, explain that briefly to the "
            "person. Keep replies short.\n"
            f"Now: {now:%A %d %B %Y %H:%M} (team time zone {TEAM_TZ.key}). Tomorrow is {tomorrow}.")


# ----------------------------------------------------------------------------- graph
def build_spike_graph(handle, world: SpikeWorld, checkpointer):
    tools, risk = make_tools(world)
    by_name = {t.name: t for t in tools}

    def run_read(call: dict) -> ToolMessage:
        try:
            out = by_name[call["name"]].invoke(call["args"])
        except Exception as e:  # bad arguments from the model: tell it, don't crash
            out = f"error: {type(e).__name__}: {e}"
        return ToolMessage(content=str(out), tool_call_id=call["id"], name=call["name"])

    def last_ai(state) -> AIMessage:
        return next(m for m in reversed(state["messages"]) if isinstance(m, AIMessage))

    async def agent(state: SpikeState) -> dict:
        history = [SystemMessage(system_prompt(world))] + state["messages"]
        try:
            msg = await handle.ainvoke(history, tools)
        except (BudgetBlocked, ModelError) as e:
            msg = AIMessage(content=f"Sorry, I can't think right now ({e}).")
        return {"messages": [msg], "steps": state.get("steps", 0) + 1}

    def after_agent(state: SpikeState) -> str:
        ai = last_ai(state)
        if not ai.tool_calls:
            return "respond"
        if state.get("steps", 0) >= MAX_STEPS:
            return "respond"
        if any(risk.get(c["name"]) == EXTERNAL for c in ai.tool_calls):
            return "prepare_approval"
        return "tools"

    async def tools_node(state: SpikeState) -> dict:
        return {"messages": [run_read(c) for c in last_ai(state).tool_calls]}

    async def prepare_approval(state: SpikeState) -> dict:
        """Safety gate: read calls from the same batch first, then rules, then the preview card."""
        out, pending = [], None
        for call in last_ai(state).tool_calls:
            if risk.get(call["name"]) != EXTERNAL:
                out.append(run_read(call))
                continue
            if pending is not None:
                out.append(ToolMessage("not run: one approval at a time; ask again after this one",
                                       tool_call_id=call["id"], name=call["name"]))
                continue
            args = call["args"]
            emails = set(world.company.values())
            outside = [a for a in args.get("attendees", []) if a not in world.company and a not in emails]
            if outside:   # rule: company people only, whatever the model or a file says
                out.append(ToolMessage(f"blocked: {', '.join(outside)} is outside the company; Max only invites "
                                       "company people", tool_call_id=call["id"], name=call["name"]))
                continue
            preview = (f"Meeting: {args.get('title')} · {args.get('start')} for {args.get('minutes')} min · "
                       f"{', '.join(args.get('attendees', []))} · agenda: {args.get('agenda') or '-'}")
            pending = {"call": call, "preview": preview}
        return {"messages": out, "pending": pending, "decision": None}

    def after_prepare(state: SpikeState) -> str:
        return "await_approval" if state.get("pending") else "agent"

    async def await_approval(state: SpikeState) -> dict:
        # Only the interrupt here: LangGraph re-runs this node from the top when the run resumes.
        decision = interrupt({"kind": "approval", "preview": state["pending"]["preview"]})
        call = state["pending"]["call"]
        action = decision.get("action")
        if action == "approve":
            return {"decision": decision}
        text = (f"Not done: {decision.get('by', 'someone')} asked for a change: {decision.get('edit', '')}"
                if action == "change" else f"Not done: {action or 'cancelled'}.")
        return {"decision": decision, "pending": None,
                "messages": [ToolMessage(text, tool_call_id=call["id"], name=call["name"])]}

    def after_await(state: SpikeState) -> str:
        action = (state.get("decision") or {}).get("action")
        return {"approve": "execute", "change": "agent"}.get(action, "respond")

    async def execute(state: SpikeState) -> dict:
        call = state["pending"]["call"]
        tx = call["id"]                                  # like Graph's transactionId: a retry can't double-create
        if tx not in world.events:
            world.events[tx] = {**call["args"], "approved_by": state["decision"].get("by")}
        ev = world.events[tx]
        result = f"created: '{ev['title']}' at {ev['start']}; invites sent to {', '.join(ev['attendees'])}"
        return {"messages": [ToolMessage(result, tool_call_id=call["id"], name=call["name"])], "pending": None}

    async def respond(state: SpikeState) -> dict:
        ai = last_ai(state)
        out = []
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:         # stopped by the step cap: close the calls
            out = [ToolMessage("not run: step limit reached", tool_call_id=c["id"], name=c["name"])
                   for c in ai.tool_calls]
            text = "I couldn't finish that in a few steps. Could you narrow it down?"
        elif isinstance(last, ToolMessage):                         # cancelled / expired
            text = f"OK, I didn't do it ({(state.get('decision') or {}).get('action', 'cancelled')})."
        else:
            text = ai.content if isinstance(ai.content, str) else _text_of(ai.content)
        world.replies.append(text)
        return {"messages": out}

    g = StateGraph(SpikeState)
    for name, fn in (("agent", agent), ("tools", tools_node), ("prepare_approval", prepare_approval),
                     ("await_approval", await_approval), ("execute", execute), ("respond", respond)):
        g.add_node(name, fn)
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", after_agent, ["tools", "prepare_approval", "respond"])
    g.add_edge("tools", "agent")
    g.add_conditional_edges("prepare_approval", after_prepare, ["await_approval", "agent"])
    g.add_conditional_edges("await_approval", after_await, ["execute", "agent", "respond"])
    g.add_edge("execute", "agent")
    g.add_edge("respond", END)
    return g.compile(checkpointer=checkpointer)


def _text_of(content: Any) -> str:
    """Model content can be a list of blocks; keep the text parts."""
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")


async def ask(graph, thread_id: str, text: str) -> dict:
    """Start a run for a new request. Returns the graph output (with '__interrupt__' if it paused)."""
    return await graph.ainvoke({"messages": [HumanMessage(text)], "pending": None, "decision": None, "steps": 0},
                               {"configurable": {"thread_id": thread_id}})


async def decide(graph, thread_id: str, action: str, by: str = "Karthi M", edit: str = "") -> dict:
    """Resume a paused run with a person's decision (what a card click does)."""
    return await graph.ainvoke(Command(resume={"action": action, "by": by, "edit": edit}),
                               {"configurable": {"thread_id": thread_id}})


def paused(out: dict) -> dict | None:
    """The approval request if the run paused, else None."""
    intr = out.get("__interrupt__") or []
    return intr[0].value if intr else None
