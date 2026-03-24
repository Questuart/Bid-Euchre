"""Hosted-play domain engine for browser-based Bid Euchre.

Provides stepwise hand/match state transitions that reuse existing rule
and strategy interfaces from ``bid_euchre.core``, ``bid_euchre.strategy``,
``bid_euchre.sim``, and ``bid_euchre.scoring``.

This package is web-framework-free.  The ``web/`` application layer imports
from here; this package must never import from ``web/``.
"""

from .engine import HUMAN_SEAT, MATCH_TARGET, AIActionEvent, MatchEngine
from .state import HandState, MatchState, TrickResult, TrickState

__all__ = [
    "AIActionEvent",
    "HUMAN_SEAT",
    "MATCH_TARGET",
    "HandState",
    "MatchEngine",
    "MatchState",
    "TrickResult",
    "TrickState",
]
