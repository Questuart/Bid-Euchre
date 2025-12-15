"""
Bid Euchre Strategy Framework

This package provides strategy classes for playing Bid Euchre.
"""

from .strategy import (
    Strategy,
    BasicStrategy,
    GreedyStrategy,
    # Legacy functions for backwards compatibility
    choose_card_basic,
    choose_card_greedy,
)

__all__ = [
    "Strategy",
    "BasicStrategy",
    "GreedyStrategy",
    "choose_card_basic",
    "choose_card_greedy",
]
