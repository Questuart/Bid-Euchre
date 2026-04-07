"""
Bid Euchre Strategy Framework

This package provides strategy classes for playing Bid Euchre.

Organized into:
- base: Strategy ABC and shared utilities
- baselines: Simple/null strategies (basic, random, always-lowest, always-highest)
- glutton: Greedy/glutton strategies with 1-trick lookahead
"""

import sys

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
    ActionValueBidder,
    AlwaysPassBidder,
    ArtifactBidder,
    BidAction,
    BiddingObservation,
    BiddingPolicy,
    FilteredGBTBidder,
    FixedBidder,
    GBTActionValueBidder,
    HeuristicSuitBidder,
    HighLowHeuristicBidder,
    HybridOLSaBidder,
    ModeloEspecifico,
    OLSaBidder,
    RanktheTank,
    StrictHellRaiser,
    StrictRaiserBidder,  # backward-compat alias
    TwoStageActionValueBidder,
    compute_best_bid,
    enumerate_legal_actions,
)

# Greedy/glutton strategies
from .glutton import (
    GluttonIsolatedStrategy,
    GluttonStrategy,
    GreedyStrategy,
    # Legacy functions for backwards compatibility
    choose_card_basic,
    choose_card_greedy,
)

# Backward-compat shim: preserve old bid_euchre.strategy.greedy module path
# after rename to glutton.py (PR #2604). External code and configs referencing
# "greedy" will continue to work via sys.modules alias.
sys.modules[__name__ + ".greedy"] = sys.modules[__name__ + ".glutton"]

# Regression strategies - REMOVED: RegressionBidder (legacy pickle path)

__all__ = [
    # Base
    "Strategy",
    "card_value_for_dump",
    # Bidding
    "ActionValueBidder",
    "BidAction",
    "BiddingObservation",
    "BiddingPolicy",
    "AlwaysPassBidder",
    "ArtifactBidder",
    "FilteredGBTBidder",
    "FixedBidder",
    "GBTActionValueBidder",
    "TwoStageActionValueBidder",
    "HeuristicSuitBidder",
    "HighLowHeuristicBidder",
    "HybridOLSaBidder",
    "ModeloEspecifico",
    "OLSaBidder",
    "RanktheTank",
    "StrictHellRaiser",
    "StrictRaiserBidder",
    "compute_best_bid",
    "enumerate_legal_actions",
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
