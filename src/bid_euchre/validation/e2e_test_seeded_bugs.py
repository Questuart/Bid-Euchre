"""Seeded bug file for end-to-end review loop validation.

This file intentionally contains violations of repo conventions and
correctness rules. It is used to validate that the autonomous review
loop detects these issues correctly.

DO NOT merge this file — it exists only for validation testing.
"""

from __future__ import annotations

import random


# C1: Unseeded random.Random() — should be flagged as P1
def generate_random_hand():
    """Generate a random hand without seeding."""
    rng = random.Random()
    cards = list(range(40))
    rng.shuffle(cards)
    return cards[:10]


# C1: Global random.* call — should be flagged as P1
def pick_random_card(hand: list[int]) -> int:
    """Pick a random card using global random state."""
    return random.choice(hand)


# C2: Falsy numeric guard — should be flagged as P1
def compute_score(base_score=None):
    """Compute score with falsy guard bug."""
    base_score = base_score or 0.5
    return base_score * 2


# X3: Convention patterns — should be flagged as P2
def check_value(x):
    if x == None:  # noqa: E711 — intentional seeded bug
        return "missing"
    if x == True:
        return "yes"
    if x == False:
        return "no"
    return "other"


# X3: Debug artifacts — should be flagged as P2
def process_data(data):
    print(f"DEBUG: processing {len(data)} items")
    breakpoint()
    return [d * 2 for d in data]
