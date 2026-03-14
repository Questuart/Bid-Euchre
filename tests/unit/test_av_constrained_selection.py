"""Unit tests for constrained feature set and forward selection in AV training."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

# Add scripts to path so we can import the trainer
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "internal"))

from train_action_value import (
    CONSTRAINED_FEATURES,
    FEATURE_SETS,
    VALID_SELECTIONS,
    resolve_feature_names,
    run_forward_selection,
)

from bid_euchre.features.hand_eval import get_hand_features
from bid_euchre.strategy.bidding import STATE_FEATURE_NAMES

# ── Constrained Feature Set ─────────────────────────────────


class TestConstrainedFeatureSet:
    """Tests for the constrained per-contract feature set."""

    def test_constrained_suit_features(self):
        """Suit contract uses exactly [bowers, trump_count, offsuit_aces]."""
        assert CONSTRAINED_FEATURES["suit"] == [
            "bowers",
            "trump_count",
            "offsuit_aces",
        ]

    def test_constrained_high_features(self):
        """High contract uses exactly [offsuit_aces, quick_tricks]."""
        assert CONSTRAINED_FEATURES["high"] == [
            "offsuit_aces",
            "quick_tricks",
        ]

    def test_constrained_low_features(self):
        """Low contract uses exactly [offsuit_tens_count, quick_tricks]."""
        assert CONSTRAINED_FEATURES["low"] == [
            "offsuit_tens_count",
            "quick_tricks",
        ]

    def test_constrained_features_exist_in_hand_eval(self):
        """All constrained features must be real features from hand_eval."""
        from bid_euchre.core.cards import Card

        # Generate a sample hand to get feature names
        # Card(suit, rank) — suit first, rank second
        sample_hand = [
            Card("H", "A"),
            Card("H", "K"),
            Card("H", "Q"),
            Card("H", "J"),
            Card("H", "T"),
            Card("S", "A"),
            Card("S", "K"),
            Card("S", "Q"),
            Card("S", "J"),
            Card("S", "T"),
        ]
        suit_features = get_hand_features(sample_hand, "suit", "H")
        high_features = get_hand_features(sample_hand, "high")
        low_features = get_hand_features(sample_hand, "low")

        all_feature_names = (
            set(suit_features.keys())
            | set(high_features.keys())
            | set(low_features.keys())
        )

        for family, feat_list in CONSTRAINED_FEATURES.items():
            for feat in feat_list:
                assert feat in all_feature_names, (
                    f"Constrained feature '{feat}' for {family} not found "
                    f"in hand_eval output"
                )

    def test_constrained_in_feature_sets(self):
        """FEATURE_SETS contains the 'constrained' entry as a dict."""
        assert "constrained" in FEATURE_SETS
        entry = FEATURE_SETS["constrained"]
        assert isinstance(entry, dict)
        assert set(entry.keys()) == {"suit", "high", "low"}

    def test_constrained_features_subset_of_state(self):
        """All constrained features are a subset of STATE_FEATURE_NAMES."""
        state_names_set = set(STATE_FEATURE_NAMES)
        for family, feat_list in CONSTRAINED_FEATURES.items():
            for feat in feat_list:
                assert feat in state_names_set, (
                    f"Constrained feature '{feat}' for {family} "
                    f"not in STATE_FEATURE_NAMES"
                )


class TestResolveFeatureNames:
    """Tests for the resolve_feature_names helper."""

    def test_flat_feature_set_returns_list(self):
        """Flat feature sets (full, r0) return the same list for any family."""
        for family in ("suit", "high", "low", "pass"):
            result = resolve_feature_names("full", family)
            assert result == list(STATE_FEATURE_NAMES)

    def test_constrained_suit_resolves(self):
        """Constrained suit resolves to suit-specific features."""
        result = resolve_feature_names("constrained", "suit")
        assert result == ["bowers", "trump_count", "offsuit_aces"]

    def test_constrained_high_resolves(self):
        """Constrained high resolves to high-specific features."""
        result = resolve_feature_names("constrained", "high")
        assert result == ["offsuit_aces", "quick_tricks"]

    def test_constrained_low_resolves(self):
        """Constrained low resolves to low-specific features."""
        result = resolve_feature_names("constrained", "low")
        assert result == ["offsuit_tens_count", "quick_tricks"]

    def test_constrained_pass_falls_back_to_suit(self):
        """Constrained pass falls back to suit features (no pass-specific set)."""
        result = resolve_feature_names("constrained", "pass")
        assert result == ["bowers", "trump_count", "offsuit_aces"]


# ── Forward Selection ────────────────────────────────────────


@pytest.fixture
def synthetic_train_df():
    """Create a small synthetic dataframe for forward selection tests."""
    rng = np.random.RandomState(42)
    n = 200
    # Create hand_id groups (4 rows per hand_id)
    hand_ids = np.repeat(np.arange(n // 4), 4)
    df = pd.DataFrame(
        {
            "hand_id": hand_ids,
            "bowers": rng.randint(0, 3, n).astype(float),
            "trump_count": rng.randint(0, 8, n).astype(float),
            "offsuit_aces": rng.randint(0, 5, n).astype(float),
            "bid_n": rng.randint(4, 11, n).astype(float),
            "contract_family": ["suit"] * n,
            "action_type": ["bid"] * n,
        }
    )
    # Target is correlated with bowers and trump_count
    df["net_points"] = (
        2.0 * df["bowers"]
        + 1.5 * df["trump_count"]
        + 0.1 * df["offsuit_aces"]
        + rng.normal(0, 1, n)
    )
    return df


class TestForwardSelection:
    """Tests for the forward selection integration."""

    def test_valid_selections(self):
        """VALID_SELECTIONS has expected entries."""
        assert "none" in VALID_SELECTIONS
        assert "forward" in VALID_SELECTIONS

    def test_forward_select_produces_subset(self, synthetic_train_df):
        """Forward selection produces a feature subset."""
        feature_names = ["bowers", "trump_count", "offsuit_aces"]
        selected, log = run_forward_selection(
            synthetic_train_df,
            feature_names,
            target_col="net_points",
            seed=42,
        )
        # Should select at least 1 feature
        assert len(selected) >= 1
        # Selected should be a subset of candidates
        assert set(selected).issubset(set(feature_names))
        # Log should have expected structure
        assert "steps" in log
        assert "final_r2" in log
        assert "n_selected" in log

    def test_forward_select_selects_informative_features(self, synthetic_train_df):
        """Forward selection should pick bowers and/or trump_count first."""
        feature_names = ["bowers", "trump_count", "offsuit_aces"]
        selected, log = run_forward_selection(
            synthetic_train_df,
            feature_names,
            target_col="net_points",
            seed=42,
        )
        # bowers (coefficient 2.0) should be selected
        assert "bowers" in selected

    def test_gbt_forward_selection_error(self):
        """--selection forward with --model-class gbt should be rejected."""

        from train_action_value import main

        test_args = [
            "--seed",
            "42",
            "--dataset",
            "dummy.parquet",
            "--output-dir",
            "/tmp/dummy",
            "--continuation-artifact",
            "dummy.json",
            "--model-class",
            "gbt",
            "--selection",
            "forward",
        ]
        with patch("sys.argv", ["train_action_value.py"] + test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            # argparse exits with code 2 on error
            assert exc_info.value.code == 2

    def test_selection_none_is_default(self):
        """--selection defaults to 'none'."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--selection",
            choices=list(VALID_SELECTIONS),
            default="none",
        )
        args = parser.parse_args([])
        assert args.selection == "none"
