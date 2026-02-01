"""
Deterministic deal generation utilities.

Primary use:
- Strategy comparisons with *common random numbers* (same exact deals across strategies).
- Reproducible experiments even if strategies introduce their own randomness.

This module intentionally uses a local RNG (random.Random) so it does not depend
on or mutate the global random module state.
"""

from __future__ import annotations

import random
from typing import List

from ..core.cards import Card, create_deck, deal_hands


def _deal_rng(seed: int, deal_id: int) -> random.Random:
    """
    Create a deterministic RNG for a (seed, deal_id) pair.

    The multiplier is just to reduce simple collisions when deal_id is small.
    """
    if seed is None:
        raise ValueError("seed must be an int for deterministic deal generation")
    # Use a stable, deterministic mapping
    combined = int(seed) * 1_000_003 + int(deal_id)
    return random.Random(combined)


def generate_deal(
    seed: int,
    deal_id: int,
    deal_method: str = "round_robin",
) -> List[List[Card]]:
    """
    Generate a deterministic deal (4 hands of 10 cards) for a given (seed, deal_id).

    Args:
        seed: RNG seed
        deal_id: Deal identifier (combined with seed for unique deals)
        deal_method: "block" or "round_robin" (default "round_robin")

    Returns:
        hands: List[List[Card]] with shape [4][10]
    """
    rng = _deal_rng(seed, deal_id)
    deck = create_deck()
    rng.shuffle(deck)
    hands = deal_hands(deck, num_players=4, hand_size=10, method=deal_method)
    # Defensive copy so callers can mutate
    return [list(h) for h in hands]


def generate_initial_leader(seed: int, deal_id: int) -> int:
    """Deterministically choose an initial leader (0-3) for a given (seed, deal_id)."""
    rng = _deal_rng(seed, deal_id)
    return rng.randrange(4)
