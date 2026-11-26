"""AI usage: meter for every AI call (any provider), daily limits, pause switch, live dashboard (python run.py dashboard)."""

from .meter import Blocked, Meter

__all__ = ["Blocked", "Meter"]
