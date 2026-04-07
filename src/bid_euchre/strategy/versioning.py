"""
Strategy versioning utilities.

Provides helpers for collecting, comparing, and serializing strategy
version metadata from play strategies and bidding policies.
"""

from __future__ import annotations

from typing import Any

from .base import Strategy
from .bidding import BiddingPolicy


def collect_versions(
    strategies: list[Strategy],
    bidding_policies: list[BiddingPolicy],
) -> dict[str, Any]:
    """Collect version and fingerprint info for all strategies and policies.

    Returns a dict suitable for embedding in ``meta.json`` under a
    ``strategy_versions`` key.

    Example output::

        {
            "play_strategies": [
                {
                    "name": "glutton",
                    "class": "GluttonStrategy",
                    "version": "0.10.0",
                    "fingerprint": "a1b2c3d4"
                }
            ],
            "bidding_policies": [
                {
                    "name": "olsa_H",
                    "class": "OLSaBidder",
                    "version": "1.0.0",
                    "fingerprint": "e5f6a7b8"
                }
            ]
        }
    """
    play_entries = []
    for s in strategies:
        play_entries.append(
            {
                "name": s.name,
                "class": type(s).__name__,
                "version": type(s).VERSION,
                "fingerprint": s.fingerprint(),
            }
        )

    bid_entries = []
    for p in bidding_policies:
        bid_entries.append(
            {
                "name": p.name,
                "class": type(p).__name__,
                "version": type(p).VERSION,
                "fingerprint": p.fingerprint(),
            }
        )

    return {
        "play_strategies": play_entries,
        "bidding_policies": bid_entries,
    }


def compare_versions(
    old: dict[str, Any],
    new: dict[str, Any],
) -> list[dict[str, Any]]:
    """Compare two ``strategy_versions`` dicts and return a list of diffs.

    Each diff entry contains::

        {
            "category": "play_strategies" | "bidding_policies",
            "name": str,
            "old_version": str | None,
            "new_version": str | None,
            "old_fingerprint": str | None,
            "new_fingerprint": str | None,
            "change": "added" | "removed" | "version_changed" | "config_changed"
        }

    ``version_changed`` means the semver string changed.
    ``config_changed`` means the version is the same but the fingerprint
    differs (e.g., a feature flag was toggled without a version bump).
    """
    diffs: list[dict[str, Any]] = []

    for category in ("play_strategies", "bidding_policies"):
        old_items = {e["name"]: e for e in old.get(category, [])}
        new_items = {e["name"]: e for e in new.get(category, [])}

        # Removed
        for name in sorted(old_items.keys() - new_items.keys()):
            entry = old_items[name]
            diffs.append(
                {
                    "category": category,
                    "name": name,
                    "old_version": entry["version"],
                    "new_version": None,
                    "old_fingerprint": entry["fingerprint"],
                    "new_fingerprint": None,
                    "change": "removed",
                }
            )

        # Added
        for name in sorted(new_items.keys() - old_items.keys()):
            entry = new_items[name]
            diffs.append(
                {
                    "category": category,
                    "name": name,
                    "old_version": None,
                    "new_version": entry["version"],
                    "old_fingerprint": None,
                    "new_fingerprint": entry["fingerprint"],
                    "change": "added",
                }
            )

        # Changed
        for name in sorted(old_items.keys() & new_items.keys()):
            o = old_items[name]
            n = new_items[name]
            if o["version"] != n["version"]:
                diffs.append(
                    {
                        "category": category,
                        "name": name,
                        "old_version": o["version"],
                        "new_version": n["version"],
                        "old_fingerprint": o["fingerprint"],
                        "new_fingerprint": n["fingerprint"],
                        "change": "version_changed",
                    }
                )
            elif o["fingerprint"] != n["fingerprint"]:
                diffs.append(
                    {
                        "category": category,
                        "name": name,
                        "old_version": o["version"],
                        "new_version": n["version"],
                        "old_fingerprint": o["fingerprint"],
                        "new_fingerprint": n["fingerprint"],
                        "change": "config_changed",
                    }
                )

    return diffs
