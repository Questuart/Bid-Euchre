"""Temporary test fixture for Codex review validation.

This file contains deliberate violations to test whether Codex
detects and reports them using the structured format in AGENTS.md.
DO NOT MERGE — close PR without merging after validation.
"""

import random
import os

from tests.unit import test_rules  # C4: import boundary violation


def compute_metrics(results: list[dict]) -> dict:
    """Compute aggregate metrics from experiment results."""
    # C1: unseeded randomness — should use random.Random(seed)
    rng = random.Random()
    sample = rng.sample(results, min(100, len(results)))

    total_tricks = sum(r["tricks_won"] for r in sample)

    # C2: falsy numeric guard — 0.0 is a valid metric value
    avg_tricks = total_tricks / len(sample)
    avg_tricks = avg_tricks or 5.0  # BUG: replaces valid 0.0

    # Global random usage (C1 variant)
    random.shuffle(sample)

    breakpoint()  # Debug artifact left in

    return {"avg_tricks": avg_tricks, "sample_size": len(sample)}


<<<<<<< HEAD
# Merge conflict marker left in
def old_function():
    pass
=======
def new_function():
    pass
>>>>>>> feature-branch

# def commented_out_block_1():
#     """This is a large commented-out block."""
#     x = 1
#     y = 2
#     z = 3
#     a = x + y
#     b = y + z
#     c = a + b
#     d = c + a
#     e = d + b
#     f = e + c
#     return f
