"""
Max's agent (Phase 4, LangGraph). Design: docs/plans/phase4-max-teammate.md + max-agent-graph.html.

Step 4.0 (plumbing):
  clock.py    injectable clock (real one, and a fake one for tests)
  models.py   the one model adapter: Gemini or Qwen chosen by config; every Gemini call metered
  testing.py  scripted fake model + recorded model replies ("cassettes") so tests cost $0
  spike.py    a small LangGraph graph that proves tool calling and the approval pause
"""

import os

# Meeting and team data must never leave this machine through tracing.
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
# Refuse unexpected object types when loading saved runs (checkpoints).
os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")
