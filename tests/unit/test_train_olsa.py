"""
Unit tests for OLSa training pipeline.
"""

import json

import numpy as np
import pandas as pd

from bid_euchre.models.freeze import verify_frozen
from bid_euchre.models.train_olsa import CONTRACT_FEATURES, save_artifacts, train_olsa


def _make_training_data(tmp_path, n_hands=200, seed=42):
    """Create synthetic bidless + outcomes parquet for testing."""
    rng = np.random.RandomState(seed)
    run_dir = tmp_path / "test_run"
    datasets_dir = run_dir / "datasets"
    datasets_dir.mkdir(parents=True)

    contract_types = ["suit", "suit", "suit", "suit", "high", "low"]
    trump_suits = ["C", "D", "H", "S", None, None]

    bidless_rows = []
    outcomes_rows = []

    for hand_id in range(n_hands):
        ct_idx = hand_id % len(contract_types)
        ct = contract_types[ct_idx]
        ts = trump_suits[ct_idx]

        tricks_team0 = rng.randint(0, 11)
        tricks_team1 = 10 - tricks_team0

        outcomes_rows.append(
            {
                "hand_id": hand_id,
                "deal_id": hand_id,
                "dealer_seat": 0,
                "contract_type": ct,
                "trump_suit": ts,
                "strategy_id": "test",
                "matchup_id": "test",
                "team0_strategy": "greedy",
                "team1_strategy": "greedy",
                "tricks_team0": tricks_team0,
                "tricks_team1": tricks_team1,
                "team0_win": tricks_team0 > tricks_team1,
            }
        )

        for seat in range(4):
            bidless_rows.append(
                {
                    "hand_id": hand_id,
                    "seat": seat,
                    "dealer_seat": 0,
                    "deal_id": hand_id,
                    "hand_cards": ["SA", "HA"],
                    "hand_features": {
                        "bowers": rng.randint(0, 3),
                        "trump_count": rng.randint(0, 7),
                        "offsuit_aces": rng.randint(0, 5),
                        "offsuit_tens_count": rng.randint(0, 5),
                        "rank_sum": rng.randint(10, 50),
                        "hand_value": rng.randint(100, 400),
                        "offsuit_non_ace_count": rng.randint(0, 8),
                        "trump_rb_count": rng.randint(0, 2),
                        "trump_lb_count": rng.randint(0, 2),
                        "trump_ace_count": rng.randint(0, 2),
                        "trump_king_count": rng.randint(0, 2),
                        "trump_queen_count": rng.randint(0, 2),
                        "trump_ten_count": rng.randint(0, 2),
                        "trump_count_x_void_count": rng.randint(0, 10),
                        "trump_count_x_offsuit_ace": rng.randint(0, 10),
                        "top_trump_count": rng.randint(0, 4),
                        "top_trump_sum": rng.randint(0, 20),
                        "trump_power_sum": rng.randint(0, 30),
                        "trump_power_avg": float(rng.uniform(0, 5)),
                        "trump_duplicate_pairs": rng.randint(0, 3),
                        "highest_trump_rank": rng.randint(0, 6),
                        "second_highest_trump_rank": rng.randint(0, 5),
                        "third_highest_trump_rank": rng.randint(0, 4),
                        "void_count": rng.randint(0, 3),
                        "num_singletons": rng.randint(0, 3),
                        "num_doubletons": rng.randint(0, 3),
                        "max_suit_len": rng.randint(2, 8),
                        "second_suit_len": rng.randint(1, 5),
                        "third_suit_len": rng.randint(0, 4),
                        "fourth_suit_len": rng.randint(0, 3),
                        "offsuit_king_count_total": rng.randint(0, 4),
                        "offsuit_queen_count_total": rng.randint(0, 4),
                        "offsuit_suits_with_ace": rng.randint(0, 4),
                        "offsuit_suits_with_double_ace": rng.randint(0, 2),
                        "offsuit_suits_with_ace_and_king": rng.randint(0, 3),
                        "offsuit_length_3plus_count": rng.randint(0, 4),
                        "offsuit_best_rank_sum": rng.randint(0, 20),
                        "offsuit_secondbest_rank_sum": rng.randint(0, 15),
                        "high_card_count": rng.randint(0, 8),
                        "low_card_count": rng.randint(0, 8),
                        "double_ten_jack_count": rng.randint(0, 3),
                    },
                    "hand_feature_schema_version": 1,
                    "contract_type": ct,
                    "trump_suit": ts,
                }
            )

    pd.DataFrame(bidless_rows).to_parquet(datasets_dir / "bidless.parquet")
    pd.DataFrame(outcomes_rows).to_parquet(datasets_dir / "bidless_outcomes.parquet")

    return str(run_dir)


class TestTrainOlsa:
    """Test OLSa training pipeline."""

    def test_train_produces_artifact(self, tmp_path):
        """Test that training produces a valid artifact."""
        run_dir = _make_training_data(tmp_path)
        artifact, metrics = train_olsa(run_dir, seed=42)

        assert artifact["artifact_type"] == "olsa_v1"
        assert artifact["schema_version"] == "1"
        assert "suit" in artifact["models"]
        assert "high" in artifact["models"]
        assert "low" in artifact["models"]

    def test_artifact_model_structure(self, tmp_path):
        """Test that each model has correct structure."""
        run_dir = _make_training_data(tmp_path)
        artifact, _ = train_olsa(run_dir, seed=42)

        for cf, expected_features in CONTRACT_FEATURES.items():
            model = artifact["models"][cf]
            assert "weights" in model
            assert "bias" in model
            assert "feature_names" in model
            assert model["feature_names"] == expected_features
            assert len(model["weights"]) == len(expected_features)

    def test_metrics_have_required_fields(self, tmp_path):
        """Test that training metrics have all required fields."""
        run_dir = _make_training_data(tmp_path)
        _, metrics = train_olsa(run_dir, seed=42)

        for cf in CONTRACT_FEATURES:
            assert cf in metrics
            m = metrics[cf]
            assert "r2_train" in m
            assert "r2_test" in m
            assert "mae_train" in m
            assert "mae_test" in m
            assert "n_train" in m
            assert "n_test" in m

    def test_artifact_roundtrip(self, tmp_path):
        """Test that artifact can be saved and loaded by OLSaBidder."""
        from bid_euchre.strategy.bidding import OLSaBidder

        run_dir = _make_training_data(tmp_path)
        artifact, metrics = train_olsa(run_dir, seed=42)

        output_dir = str(tmp_path / "artifacts")
        artifact_path = save_artifacts(artifact, metrics, output_dir)

        # Load with OLSaBidder
        bidder = OLSaBidder(artifact_path)
        assert "suit" in bidder.models
        assert "high" in bidder.models
        assert "low" in bidder.models

    def test_missing_data_raises(self, tmp_path):
        """Test that missing data raises FileNotFoundError."""
        try:
            train_olsa(str(tmp_path / "nonexistent"), seed=42)
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError:
            pass


class TestAutoFreeze:
    """Test --freeze integration with training pipeline."""

    def test_freeze_after_save(self, tmp_path):
        """Test that freeze_artifact() works on saved artifact."""
        from bid_euchre.models.freeze import freeze_artifact

        run_dir = _make_training_data(tmp_path)
        artifact, metrics = train_olsa(run_dir, seed=42)
        output_dir = str(tmp_path / "artifacts")
        artifact_path = save_artifacts(artifact, metrics, output_dir)

        # Before freeze: frozen_at should be None
        with open(artifact_path) as f:
            data = json.load(f)
        assert data["frozen_at"] is None

        # Freeze
        freeze_artifact(artifact_path)

        # After freeze: verify_frozen should pass
        assert verify_frozen(artifact_path)

        with open(artifact_path) as f:
            data = json.load(f)
        assert data["frozen_at"] is not None
        assert data["artifact_sha256"] is not None

    def test_freeze_already_frozen_raises(self, tmp_path):
        """Test that freezing an already-frozen artifact raises ValueError."""
        from bid_euchre.models.freeze import freeze_artifact

        run_dir = _make_training_data(tmp_path)
        artifact, metrics = train_olsa(run_dir, seed=42)
        output_dir = str(tmp_path / "artifacts")
        artifact_path = save_artifacts(artifact, metrics, output_dir)

        freeze_artifact(artifact_path)

        try:
            freeze_artifact(artifact_path)
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_unfrozen_artifact_fails_verify(self, tmp_path):
        """Test that an unfrozen artifact fails verification."""
        run_dir = _make_training_data(tmp_path)
        artifact, metrics = train_olsa(run_dir, seed=42)
        output_dir = str(tmp_path / "artifacts")
        artifact_path = save_artifacts(artifact, metrics, output_dir)

        assert not verify_frozen(artifact_path)
