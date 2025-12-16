"""
Bid Euchre Strategy Framework

This package provides strategy classes for playing Bid Euchre.

Organized into:
- base: Strategy ABC and shared utilities
- baselines: Simple/null strategies (basic, random, always-lowest, always-highest)
- greedy: Greedy strategies with 1-trick lookahead
"""

# Base strategy class
from .base import Strategy, card_value_for_dump

# Baseline strategies
from .baselines import (
    BasicStrategy,
    RandomLegalStrategy,
    AlwaysLowestLegalStrategy,
    AlwaysHighestLegalStrategy,
)

# Greedy strategies
from .greedy import (
    GreedyStrategy,
    ImprovedGreedyStrategy,
    # Legacy functions for backwards compatibility
    choose_card_basic,
    choose_card_greedy,
)

__all__ = [
    # Base
    "Strategy",
    "card_value_for_dump",
    # Baselines
    "BasicStrategy",
    "RandomLegalStrategy",
    "AlwaysLowestLegalStrategy",
    "AlwaysHighestLegalStrategy",
    # Greedy
    "GreedyStrategy",
    "ImprovedGreedyStrategy",
    # Legacy functions
    "choose_card_basic",
    "choose_card_greedy",
]
