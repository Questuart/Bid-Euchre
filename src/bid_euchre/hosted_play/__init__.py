"""Hosted-play domain engine for browser-based Bid Euchre.

Provides stepwise hand/match state transitions that reuse existing rule
and strategy interfaces from ``bid_euchre.core``, ``bid_euchre.strategy``,
``bid_euchre.sim``, and ``bid_euchre.scoring``.

This package is web-framework-free.  The ``web/`` application layer imports
from here; this package must never import from ``web/``.
"""
