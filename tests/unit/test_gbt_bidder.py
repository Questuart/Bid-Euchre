"""Tests for GBT action-value bidding infrastructure.

Tests GBT training, serialization round-trip, GBTActionValueBidder loading,
feature validation, and choose_bid behavior.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from bid_euchre.core.cards import Card
from bid_euchre.strategy.bidding import (
    STATE_FEATURE_NAMES,
    BidAction,
    BiddingObservation,
    GBTActionValueBidder,
    enumerate_legal_actions,
)

# ── Fixtures ──────────────────────────────────────────────


def _make_hand() -> list[Card]:
    """Create a valid 10-card hand for testing."""
    suits = ["C", "D", "H", "S"]
    ranks = ["T", "J", "Q", "K", "A"]
    cards = []
    for i, suit in enumerate(suits):
        for rank in ranks[i : i + 3]:
            cards.append(Card(rank=rank, suit=suit))
            if len(cards) == 10:
                return cards
    while len(cards) < 10:
        cards.append(Card(rank="T", suit="C"))
    return cards[:10]


def _make_obs(
    current_high_bid: int = 0,
    seat: int = 1,
    dealer_seat: int = 0,
    allowed_contracts: tuple[str, ...] = ("C", "D", "H", "S", "HIGH", "LOW"),
    auction_transcript: tuple[dict, ...] = (),
) -> BiddingObservation:
    """Create a BiddingObservation for testing."""
    return BiddingObservation(
        hand=_make_hand(),
        seat=seat,
        dealer_seat=dealer_seat,
        current_high_bid=current_high_bid,
        allowed_contracts=allowed_contracts,
        auction_transcript=auction_transcript,
    )


def _make_synthetic_dataset(n_deals: int = 50, seed: int = 42) -> pd.DataFrame:
    """Create a synthetic action-value dataset for GBT training tests.

    Produces rows with all required columns matching the real dataset schema.
    """
    rng = np.random.RandomState(seed)

    rows = []
    for deal_id in range(n_deals):
        hand_id = deal_id * 4
        for seat in range(4):
            for action_type, family, bid_n in [
                ("pass", "pass", 0),
                ("bid", "suit", 4),
                ("bid", "high", 4),
                ("bid", "low", 4),
            ]:
                row = {
                    "hand_id": hand_id + seat,
                    "deal_id": deal_id,
                    "focal_seat": seat,
                    "action_type": action_type,
                    "contract_family": family,
                    "bid_n": bid_n,
                    "trump_suit": "C" if family == "suit" else None,
                    "net_points": rng.randn() * 5.0,
                }
                # Add state features
                for feat in STATE_FEATURE_NAMES:
                    row[feat] = rng.randn()
                rows.append(row)

    return pd.DataFrame(rows)


@pytest.fixture
def synthetic_dataset():
    """Provide a synthetic dataset for training tests."""
    return _make_synthetic_dataset()


@pytest.fixture
def trained_gbt_artifact(synthetic_dataset, tmp_path):
    """Train GBT models on synthetic data and return artifact path."""
    from scripts.internal.train_action_value import (
        build_gbt_artifact,
        split_by_deal,
        train_family_gbt,
        train_pass_gbt,
    )

    train_df, val_df, _ = split_by_deal(synthetic_dataset, seed=42)

    gbt_models = {}
    model_metadata = {}

    for family in ("suit", "high", "low"):
        model, meta = train_family_gbt(train_df, val_df, family, seed=42)
        gbt_models[family] = model
        model_metadata[family] = meta

    pass_model, pass_meta = train_pass_gbt(train_df, val_df, seed=42)
    gbt_models["pass"] = pass_model
    model_metadata["pass"] = pass_meta

    artifact = build_gbt_artifact(
        gbt_models,
        model_metadata,
        tmp_path,
        seed=42,
        n_deals=50,
        continuation_artifact="dummy_r0.json",
    )

    artifact_path = tmp_path / "action_value_gbt.json"
    artifact_path.write_text(json.dumps(artifact, indent=2))

    return str(artifact_path)


# ── GBT Training ─────────────────────────────────────────


class TestGBTTraining:
    def test_train_family_gbt_returns_model_and_metadata(self, synthetic_dataset):
        from scripts.internal.train_action_value import (
            split_by_deal,
            train_family_gbt,
        )

        train_df, val_df, _ = split_by_deal(synthetic_dataset, seed=42)
        model, meta = train_family_gbt(train_df, val_df, "suit", seed=42)

        # Model should be a sklearn GBT
        assert hasattr(model, "predict")
        assert hasattr(model, "feature_importances_")

        # Metadata should have expected keys
        assert "r_squared" in meta
        assert "mae" in meta
        assert "feature_names" in meta
        assert "n_train" in meta
        assert "feature_importances" in meta
        assert meta["n_train"] > 0

    def test_train_pass_gbt_has_no_action_features(self, synthetic_dataset):
        from scripts.internal.train_action_value import (
            split_by_deal,
            train_pass_gbt,
        )

        train_df, val_df, _ = split_by_deal(synthetic_dataset, seed=42)
        model, meta = train_pass_gbt(train_df, val_df, seed=42)

        # Pass model should use state features only
        assert meta["feature_names"] == list(STATE_FEATURE_NAMES)
        assert "bid_n" not in meta["feature_names"]

    def test_gbt_deterministic_with_seed(self, synthetic_dataset):
        from scripts.internal.train_action_value import (
            split_by_deal,
            train_family_gbt,
        )

        train_df, val_df, _ = split_by_deal(synthetic_dataset, seed=42)

        _, meta1 = train_family_gbt(train_df, val_df, "suit", seed=42)
        _, meta2 = train_family_gbt(train_df, val_df, "suit", seed=42)

        assert meta1["r_squared"] == meta2["r_squared"]
        assert meta1["mae"] == meta2["mae"]


# ── Serialization Round-Trip ─────────────────────────────


class TestGBTSerialization:
    def test_artifact_has_correct_schema(self, trained_gbt_artifact):
        with open(trained_gbt_artifact) as f:
            artifact = json.load(f)

        assert artifact["schema_version"] == "action_value_gbt_v1"
        assert "models" in artifact
        assert set(artifact["models"]) == {"suit", "high", "low", "pass"}

        for family in ("suit", "high", "low", "pass"):
            model_meta = artifact["models"][family]
            assert "model_file" in model_meta
            assert "feature_names" in model_meta
            assert "r_squared" in model_meta
            assert "feature_importances" in model_meta

    def test_joblib_files_exist(self, trained_gbt_artifact):
        artifact_dir = Path(trained_gbt_artifact).parent

        for family in ("suit", "high", "low", "pass"):
            model_path = artifact_dir / f"gbt_{family}.joblib"
            assert model_path.exists(), f"Missing model file: {model_path}"

    def test_round_trip_prediction_matches(self, trained_gbt_artifact):
        """Train → serialize → load → predict gives same result."""
        import joblib

        artifact_dir = Path(trained_gbt_artifact).parent

        with open(trained_gbt_artifact) as f:
            artifact = json.load(f)

        # Load serialized model
        model = joblib.load(artifact_dir / artifact["models"]["suit"]["model_file"])

        # Make a prediction
        n_features = len(artifact["models"]["suit"]["feature_names"])
        test_input = np.zeros((1, n_features))
        pred = model.predict(test_input)

        assert isinstance(pred[0], (float, np.floating))


# ── GBTActionValueBidder ─────────────────────────────────


class TestGBTActionValueBidder:
    def test_loads_from_artifact(self, trained_gbt_artifact):
        bidder = GBTActionValueBidder(artifact_path=trained_gbt_artifact)
        assert bidder.name == "gbt_action_value"

    def test_choose_bid_returns_valid_action(self, trained_gbt_artifact):
        bidder = GBTActionValueBidder(artifact_path=trained_gbt_artifact)
        obs = _make_obs(current_high_bid=0)
        action = bidder.choose_bid(obs)

        assert isinstance(action, BidAction)
        legal = enumerate_legal_actions(obs)
        # Action must be one of the legal actions
        assert any(action.n == a.n and action.contract == a.contract for a in legal)

    def test_choose_bid_after_high_bid(self, trained_gbt_artifact):
        bidder = GBTActionValueBidder(artifact_path=trained_gbt_artifact)
        obs = _make_obs(current_high_bid=9)
        action = bidder.choose_bid(obs)
        assert isinstance(action, BidAction)

    def test_rejects_wrong_schema(self, tmp_path):
        artifact = {
            "schema_version": "action_value_olsa_v1",
            "models": {},
        }
        path = tmp_path / "wrong_schema.json"
        path.write_text(json.dumps(artifact))

        with pytest.raises(ValueError, match="action_value_gbt_v1"):
            GBTActionValueBidder(artifact_path=str(path))

    def test_rejects_mismatched_features(self, trained_gbt_artifact):
        artifact_dir = Path(trained_gbt_artifact).parent

        with open(trained_gbt_artifact) as f:
            artifact = json.load(f)

        # Corrupt feature names
        artifact["models"]["suit"]["feature_names"] = ["wrong_feature"]

        # Write corrupted artifact in same dir as .joblib files
        bad_path = artifact_dir / "bad_artifact.json"
        bad_path.write_text(json.dumps(artifact))

        with pytest.raises(ValueError, match="feature_names mismatch"):
            GBTActionValueBidder(artifact_path=str(bad_path))

    def test_config_registration(self):
        """GBTActionValueBidder is registered in the experiment config system."""
        from bid_euchre.experiments.config import (
            BIDDING_POLICY_REGISTRY,
            BIDDING_REQUIRED_PARAMS,
        )

        assert "GBTActionValueBidder" in BIDDING_POLICY_REGISTRY
        assert BIDDING_REQUIRED_PARAMS["GBTActionValueBidder"] == ["artifact_path"]
