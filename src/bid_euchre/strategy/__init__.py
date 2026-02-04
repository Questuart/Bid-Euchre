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
    AlwaysHighestLegalStrategy,
    AlwaysLowestLegalStrategy,
    BasicStrategy,
    RandomLegalStrategy,
)

# Bidding policies
from .bidding import (
    AlwaysPassBidder,
    ArtifactBidder,
    BidAction,
    BiddingObservation,
    BiddingPolicy,
    FixedBidder,
    HeuristicSuitBidder,
    HighLowHeuristicBidder,
    ModeloEspecifico,
    RanktheTank,
    StrictRaiserBidder,
)

# Greedy strategies
from .greedy import (
    GluttonIsolatedStrategy,
    GluttonStrategy,
    GreedyStrategy,
    # Legacy functions for backwards compatibility
    choose_card_basic,
    choose_card_greedy,
)

# Regression strategies - REMOVED: RegressionBidder (legacy pickle path)

__all__ = [
    # Base
    "Strategy",
    "card_value_for_dump",
    # Bidding
    "BidAction",
    "BiddingObservation",
    "BiddingPolicy",
    "AlwaysPassBidder",
    "ArtifactBidder",
    "FixedBidder",
    "HeuristicSuitBidder",
    "HighLowHeuristicBidder",
    "ModeloEspecifico",
    "RanktheTank",
    "StrictRaiserBidder",
    # Baselines
    "BasicStrategy",
    "RandomLegalStrategy",
    "AlwaysLowestLegalStrategy",
    "AlwaysHighestLegalStrategy",
    # Greedy
    "GreedyStrategy",
    "GluttonStrategy",
    "GluttonIsolatedStrategy",
    # Regression - REMOVED: RegressionBidder (legacy pickle path)
    # Legacy functions
    "choose_card_basic",
    "choose_card_greedy",
]
