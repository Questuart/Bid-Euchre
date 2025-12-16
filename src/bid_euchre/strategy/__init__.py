"""
Bid Euchre Strategy Framework

This package provides strategy classes for playing Bid Euchre.
"""

from .strategy import (
    Strategy,
    BasicStrategy,
    GreedyStrategy,
    RandomLegalStrategy,
    AlwaysLowestLegalStrategy,
    AlwaysHighestLegalStrategy,
    # Legacy functions for backwards compatibility
    choose_card_basic,
    choose_card_greedy,
)

__all__ = [
    "Strategy",
    "BasicStrategy",
    "GreedyStrategy",
    "RandomLegalStrategy",
    "AlwaysLowestLegalStrategy",
    "AlwaysHighestLegalStrategy",
    "choose_card_basic",
    "choose_card_greedy",
]
