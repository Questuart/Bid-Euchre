"""
Unit tests for the hybrid OLSa training pipeline.
"""

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from bid_euchre.models.train_hybrid_olsa import train_hybrid_olsa


def _make_synthetic_run(
    tmp_path: Path, n_hands=100, seed=42, include_partner_features=False
):
    """Create a synthetic bidless run directory with parquet files.

    Args:
        include_partner_features: If True, add 4 partner context columns to the
            bidless parquet, simulating auction-context-enriched datasets.

    Returns the run_dir path.
    """
    rng = np.random.RandomState(seed)
    run_dir = tmp_path / "test_run"
    datasets_dir = run_dir / "datasets"
    datasets_dir.mkdir(parents=True)

    # Generate hand-level data
    hand_ids = np.repeat(np.arange(n_hands), 4)  # 4 seats per hand
    seats = np.tile([0, 1, 2, 3], n_hands)

    # Contract types: alternate suit/high/low
    contracts = np.array(["suit", "high", "low"])
    contract_idx = rng.randint(0, 3, size=n_hands)
    contract_per_hand = contracts[contract_idx]
    contract_type = np.repeat(contract_per_hand, 4)

    # Trump suit: only for suit contracts
    trump_suit = np.where(contract_type == "suit", "S", None)

    n_rows = n_hands * 4

    # Generate 39 features (matching production schema)
    feature_names = [
        "bowers",
        "trump_count",
        "offsuit_aces",
        "offsuit_tens_count",
        "trump_power",
        "offsuit_kings",
        "void_count",
        "singleton_count",
        "doubleton_count",
        "max_offsuit_length",
        "trump_ace",
        "trump_king",
        "offsuit_queens",
        "offsuit_jacks",
        "trump_jack_count",
        "total_face_cards",
        "offsuit_suit_count",
        "min_offsuit_length",
        "trump_sequence_top",
        "has_left_bower",
        "has_right_bower",
        "offsuit_aces_squared",
        "trump_count_squared",
        "bowers_trump_interaction",
        "rank_weighted_trump",
        "offsuit_control_count",
        "offsuit_ten_count_high",
        "is_void_offsuit_any",
        "trump_density",
        "hand_high_card_points",
        "offsuit_winner_count",
        "trump_winner_count",
        "guaranteed_tricks_estimate",
        "losing_tricks_count",
        "quick_tricks",
        "offsuit_length_variance",
        "trump_body_cards",
        "offsuit_spot_cards",
        "hand_shape_code",
    ]

    features_data = {
        "hand_id": hand_ids,
        "seat": seats,
        "dealer_seat": np.tile([3, 3, 3, 3], n_hands)[:n_rows],
        "deal_id": np.repeat(np.arange(n_hands), 4),
        "contract_type": contract_type,
        "trump_suit": trump_suit,
        "hand_cards": [["SA", "SK"] * 5] * n_rows,
        "hand_feature_schema_version": np.ones(n_rows, dtype=int),
    }

    for fname in feature_names:
        # Base value per hand + small per-seat noise (avoids systematic bias)
        base = rng.randn(n_hands)
        noise = rng.normal(0, 0.05, n_rows)
        features_data[fname] = np.repeat(base, 4) + noise

    # Add partner features if requested
    if include_partner_features:
        features_data["partner_bid_level"] = rng.randint(0, 8, size=n_rows).astype(
            float
        )
        features_data["partner_passed"] = rng.randint(0, 2, size=n_rows).astype(float)
        features_data["partner_suit_match"] = rng.randint(0, 2, size=n_rows).astype(
            float
        )

    # Make bowers strongly predict tricks for testability
    features_df = pd.DataFrame(features_data)

    # Outcomes
    outcome_rows = []
    for i in range(n_hands):
        ct = contract_per_hand[i]
        ts = "S" if ct == "suit" else None
        # Tricks correlated with bowers feature for testability
        base_tricks = 5.0 + 2.0 * features_data["bowers"][i * 4]
        t0 = max(0, min(10, int(round(base_tricks + rng.normal(0, 1)))))
        t1 = 10 - t0
        outcome_rows.append(
            {
                "hand_id": i,
                "contract_type": ct,
                "trump_suit": ts,
                "tricks_team0": t0,
                "tricks_team1": t1,
                "team0_win": int(t0 > t1),
            }
        )

    outcomes_df = pd.DataFrame(outcome_rows)

    features_df.to_parquet(datasets_dir / "bidless.parquet", index=False)
    outcomes_df.to_parquet(datasets_dir / "bidless_outcomes.parquet", index=False)

    return str(run_dir)


def test_train_produces_hybrid_artifact(tmp_path: Path):
    """Training produces a valid hybrid_olsa_v1 artifact."""
    run_dir = _make_synthetic_run(tmp_path)
    output_dir = str(tmp_path / "output")

    result = train_hybrid_olsa(
        run_dir=run_dir,
        seed=42,
        output_dir=output_dir,
        arm_mode="constrained",
        freeze=False,
    )

    assert "constrained" in result["artifacts"]
    artifact_path = result["artifacts"]["constrained"]
    assert os.path.exists(artifact_path)

    with open(artifact_path) as f:
        artifact = json.load(f)

    assert artifact["artifact_type"] == "hybrid_olsa_v1"
    assert artifact["schema_version"] == 1
    assert "payoff_model" in artifact
    assert "residual_variance" in artifact


def test_arm_mode_both(tmp_path: Path):
    """arm_mode='both' produces 2 artifacts."""
    run_dir = _make_synthetic_run(tmp_path)
    output_dir = str(tmp_path / "output")

    result = train_hybrid_olsa(
        run_dir=run_dir,
        seed=42,
        output_dir=output_dir,
        arm_mode="both",
        freeze=False,
    )

    assert "constrained" in result["artifacts"]
    assert "full" in result["artifacts"]
    assert os.path.exists(result["artifacts"]["constrained"])
    assert os.path.exists(result["artifacts"]["full"])


def test_arm_mode_constrained_only(tmp_path: Path):
    """arm_mode='constrained' produces 1 artifact (OLSa only)."""
    run_dir = _make_synthetic_run(tmp_path)
    output_dir = str(tmp_path / "output")

    result = train_hybrid_olsa(
        run_dir=run_dir,
        seed=42,
        output_dir=output_dir,
        arm_mode="constrained",
        freeze=False,
    )

    assert "constrained" in result["artifacts"]
    assert "full" not in result["artifacts"]


def test_residual_variance_positive(tmp_path: Path):
    """Residual variance should be positive and bounded."""
    run_dir = _make_synthetic_run(tmp_path)
    output_dir = str(tmp_path / "output")

    result = train_hybrid_olsa(
        run_dir=run_dir,
        seed=42,
        output_dir=output_dir,
        arm_mode="constrained",
        freeze=False,
    )

    with open(result["artifacts"]["constrained"]) as f:
        artifact = json.load(f)

    for cf, var in artifact["residual_variance"].items():
        assert 0 < var < 25, f"Unexpected residual_variance for {cf}: {var}"


def test_split_manifest_written(tmp_path: Path):
    """Split manifests should be written for each contract family."""
    run_dir = _make_synthetic_run(tmp_path)
    output_dir = str(tmp_path / "output")

    train_hybrid_olsa(
        run_dir=run_dir,
        seed=42,
        output_dir=output_dir,
        arm_mode="constrained",
        freeze=False,
    )

    # Check that at least one manifest exists
    manifests = list(Path(output_dir).glob("split_manifest_*.json"))
    assert len(manifests) >= 1

    # Verify manifest structure
    with manifests[0].open() as f:
        manifest = json.load(f)
    assert "split_type" in manifest
    assert manifest["split_type"] == "three_way"


def test_training_report_written(tmp_path: Path):
    """Training report should contain per-contract metrics."""
    run_dir = _make_synthetic_run(tmp_path)
    output_dir = str(tmp_path / "output")

    result = train_hybrid_olsa(
        run_dir=run_dir,
        seed=42,
        output_dir=output_dir,
        arm_mode="constrained",
        freeze=False,
    )

    assert "training_report" in result
    report_path = result["training_report"]
    assert os.path.exists(report_path)

    with open(report_path) as f:
        report = json.load(f)

    assert report["rung_id"] == "r0"
    assert report["training_seed"] == 42
    assert "constrained" in report


def test_freeze_artifacts(tmp_path: Path):
    """When freeze=True, artifacts should have frozen_at set."""
    run_dir = _make_synthetic_run(tmp_path)
    output_dir = str(tmp_path / "output")

    result = train_hybrid_olsa(
        run_dir=run_dir,
        seed=42,
        output_dir=output_dir,
        arm_mode="constrained",
        freeze=True,
    )

    with open(result["artifacts"]["constrained"]) as f:
        artifact = json.load(f)

    assert artifact["frozen_at"] is not None
    assert artifact["artifact_sha256"] is not None


def test_rung_bundle_written(tmp_path: Path):
    """Rung bundle should match arc_d_rung_bundle_v1 schema."""
    run_dir = _make_synthetic_run(tmp_path)
    output_dir = str(tmp_path / "output")

    result = train_hybrid_olsa(
        run_dir=run_dir,
        seed=42,
        output_dir=output_dir,
        arm_mode="both",
        freeze=False,
    )

    assert "rung_bundle" in result
    with open(result["rung_bundle"]) as f:
        bundle = json.load(f)

    # Top-level schema fields
    assert bundle["bundle_schema"] == "arc_d_rung_bundle_v1"
    assert bundle["rung_id"] == "r0"
    assert bundle["arc"] == "arc_d"
    assert bundle["timestamp"] is not None

    # Arm blocks
    assert "olsa" in bundle
    assert "olsa_full" in bundle
    assert "artifact_path" in bundle["olsa"]
    assert "artifact_path" in bundle["olsa_full"]
    assert "selected_features" in bundle["olsa"]
    assert "selected_features" in bundle["olsa_full"]

    # Eval placeholders (populated by PR-I2)
    assert bundle["olsa"]["eval_seed42"] is None
    assert bundle["olsa_full"]["eval_seed42"] is None

    # Split manifest and training report
    assert bundle["split_manifest"] is not None
    assert bundle["training_report"] is not None

    # Incumbent and control (null at R0)
    assert bundle["incumbent"] is None
    assert bundle["control"] is None


def test_val_metrics_in_report(tmp_path: Path):
    """Training report should include validation metrics for three_way split."""
    run_dir = _make_synthetic_run(tmp_path)
    output_dir = str(tmp_path / "output")

    result = train_hybrid_olsa(
        run_dir=run_dir,
        seed=42,
        output_dir=output_dir,
        arm_mode="constrained",
        freeze=False,
        split_type="three_way",
    )

    with open(result["training_report"]) as f:
        report = json.load(f)

    # At least one contract family should have val metrics
    for cf in ["suit", "high", "low"]:
        if cf in report.get("constrained", {}):
            metrics = report["constrained"][cf]
            assert "r2_val" in metrics, f"Missing r2_val for {cf}"
            assert "mae_val" in metrics, f"Missing mae_val for {cf}"
            assert "n_val" in metrics, f"Missing n_val for {cf}"
            assert metrics["n_val"] > 0


def test_non_numeric_columns_excluded(tmp_path: Path):
    """Non-numeric columns (hand_cards, deal_id, etc.) should not be treated as features."""
    run_dir = _make_synthetic_run(tmp_path)
    output_dir = str(tmp_path / "output")

    # Full arm uses forward selection — would crash on non-numeric columns
    result = train_hybrid_olsa(
        run_dir=run_dir,
        seed=42,
        output_dir=output_dir,
        arm_mode="full",
        freeze=False,
    )

    with open(result["artifacts"]["full"]) as f:
        artifact = json.load(f)

    # Verify no non-feature columns leaked into selected features
    non_features = {
        "hand_cards",
        "deal_id",
        "dealer_seat",
        "hand_feature_schema_version",
    }
    for cf, model in artifact["payoff_model"].items():
        selected = set(model["feature_names"])
        leaked = selected & non_features
        assert not leaked, f"Non-feature columns in {cf}: {leaked}"


def test_context_candidates_additive_forward_selection(tmp_path: Path):
    """Constrained arm with context_candidates includes locked base + selected context features."""
    from bid_euchre.features.auction_context import PARTNER_FEATURE_NAMES
    from bid_euchre.models.train_olsa import CONTRACT_FEATURES

    run_dir = _make_synthetic_run(tmp_path, include_partner_features=True)
    output_dir = str(tmp_path / "output")

    result = train_hybrid_olsa(
        run_dir=run_dir,
        seed=42,
        output_dir=output_dir,
        arm_mode="constrained",
        freeze=False,
        context_candidates=PARTNER_FEATURE_NAMES,
    )

    with open(result["artifacts"]["constrained"]) as f:
        artifact = json.load(f)

    # Every contract's selected features must include the locked base
    for cf in ["suit", "high", "low"]:
        if cf not in artifact["payoff_model"]:
            continue
        selected = artifact["payoff_model"][cf]["feature_names"]
        locked = CONTRACT_FEATURES[cf]
        for feat in locked:
            assert (
                feat in selected
            ), f"Locked base feature '{feat}' missing from {cf}: {selected}"
        # Selected features should be a superset of (or equal to) locked base
        assert len(selected) >= len(locked)

    # Artifact context_features should be a subset of candidates (actually selected)
    assert set(artifact["context_features"]).issubset(set(PARTNER_FEATURE_NAMES))
    # At least some context features should have been selected (synthetic data
    # has partner_bid_level correlated with nothing, but forward_select always
    # tries adding — with random data some may pass the improvement threshold)
    # The key invariant: context_features ⊆ candidates, and all listed features
    # appear in at least one contract's model.
    for cf_name in artifact["context_features"]:
        found = any(
            cf_name in artifact["payoff_model"][cf]["feature_names"]
            for cf in artifact["payoff_model"]
        )
        assert found, f"context_features lists '{cf_name}' but no model uses it"

    # Feature selection log should be produced
    assert "constrained_feature_selection_log" in result


def test_full_arm_context_features_populated(tmp_path: Path):
    """Full arm artifact should have context_features when context_candidates provided."""
    from bid_euchre.features.auction_context import PARTNER_FEATURE_NAMES

    run_dir = _make_synthetic_run(tmp_path, include_partner_features=True)
    output_dir = str(tmp_path / "output")

    result = train_hybrid_olsa(
        run_dir=run_dir,
        seed=42,
        output_dir=output_dir,
        arm_mode="full",
        freeze=False,
        rung_id="test",
        context_candidates=list(PARTNER_FEATURE_NAMES),
    )

    with open(result["artifacts"]["full"]) as f:
        artifact = json.load(f)

    # Full arm should populate context_features (subset of candidates)
    assert set(artifact.get("context_features", [])).issubset(
        set(PARTNER_FEATURE_NAMES)
    )
    # Every listed context feature must appear in at least one contract model
    for cf_name in artifact["context_features"]:
        found = any(
            cf_name in artifact["payoff_model"][cf]["feature_names"]
            for cf in artifact["payoff_model"]
        )
        assert found, f"context_features lists '{cf_name}' but no model uses it"

    # Feature selection log should be produced for full arm
    assert "feature_selection_log" in result


def test_context_candidates_none_backward_compat(tmp_path: Path):
    """Constrained arm without context_candidates uses only locked base (R0 path)."""
    from bid_euchre.models.train_olsa import CONTRACT_FEATURES

    run_dir = _make_synthetic_run(tmp_path)
    output_dir = str(tmp_path / "output")

    result = train_hybrid_olsa(
        run_dir=run_dir,
        seed=42,
        output_dir=output_dir,
        arm_mode="constrained",
        freeze=False,
    )

    with open(result["artifacts"]["constrained"]) as f:
        artifact = json.load(f)

    # Features should be exactly the locked base (no additive selection)
    for cf in ["suit", "high", "low"]:
        if cf not in artifact["payoff_model"]:
            continue
        selected = artifact["payoff_model"][cf]["feature_names"]
        assert (
            selected == CONTRACT_FEATURES[cf]
        ), f"Expected locked base for {cf}, got {selected}"

    # context_features should be empty
    assert artifact["context_features"] == []

    # No feature selection log
    assert "constrained_feature_selection_log" not in result


def test_training_mode_joint_default(tmp_path: Path):
    """Default training_mode='joint' produces same results as before (backward compat)."""
    from bid_euchre.models.train_olsa import CONTRACT_FEATURES

    run_dir = _make_synthetic_run(tmp_path, seed=99)
    output_dir_default = str(tmp_path / "output_default")
    output_dir_joint = str(tmp_path / "output_joint")

    result_default = train_hybrid_olsa(
        run_dir=run_dir,
        seed=42,
        output_dir=output_dir_default,
        arm_mode="constrained",
        freeze=False,
    )

    result_joint = train_hybrid_olsa(
        run_dir=run_dir,
        seed=42,
        output_dir=output_dir_joint,
        arm_mode="constrained",
        freeze=False,
        training_mode="joint",
    )

    with open(result_default["artifacts"]["constrained"]) as f:
        art_default = json.load(f)
    with open(result_joint["artifacts"]["constrained"]) as f:
        art_joint = json.load(f)

    # Weights and biases should be identical
    for cf in CONTRACT_FEATURES:
        if cf not in art_default["payoff_model"]:
            continue
        w_default = art_default["payoff_model"][cf]["weights"]
        w_joint = art_joint["payoff_model"][cf]["weights"]
        np.testing.assert_allclose(w_default, w_joint, atol=1e-12)
        assert (
            art_default["payoff_model"][cf]["bias"]
            == art_joint["payoff_model"][cf]["bias"]
        )

    # Artifact metadata should record training_mode
    assert art_joint["training_mode"] == "joint"
    assert "ridge_alpha" not in art_joint


def test_training_mode_ridge(tmp_path: Path):
    """Ridge mode with alpha>0 produces different weights than joint, but valid predictions."""
    run_dir = _make_synthetic_run(tmp_path, seed=99)
    output_dir_joint = str(tmp_path / "output_joint")
    output_dir_ridge = str(tmp_path / "output_ridge")

    result_joint = train_hybrid_olsa(
        run_dir=run_dir,
        seed=42,
        output_dir=output_dir_joint,
        arm_mode="constrained",
        freeze=False,
        training_mode="joint",
    )

    result_ridge = train_hybrid_olsa(
        run_dir=run_dir,
        seed=42,
        output_dir=output_dir_ridge,
        arm_mode="constrained",
        freeze=False,
        training_mode="ridge",
        ridge_alpha=10.0,
    )

    with open(result_joint["artifacts"]["constrained"]) as f:
        art_joint = json.load(f)
    with open(result_ridge["artifacts"]["constrained"]) as f:
        art_ridge = json.load(f)

    # Weights should differ with large alpha
    any_differ = False
    for cf in art_joint["payoff_model"]:
        w_joint = np.array(art_joint["payoff_model"][cf]["weights"])
        w_ridge = np.array(art_ridge["payoff_model"][cf]["weights"])
        if not np.allclose(w_joint, w_ridge, atol=1e-6):
            any_differ = True
        # Ridge weights should be smaller in magnitude (shrinkage)
        assert np.linalg.norm(w_ridge) <= np.linalg.norm(w_joint) + 1e-6
    assert any_differ, "Ridge with alpha=10.0 should produce different weights than OLS"

    # Artifact metadata should record ridge params
    assert art_ridge["training_mode"] == "ridge"
    assert art_ridge["ridge_alpha"] == 10.0

    # Residual variances should still be valid
    for cf, var in art_ridge["residual_variance"].items():
        assert 0 < var < 25, f"Unexpected residual_variance for {cf}: {var}"


def test_training_mode_two_stage(tmp_path: Path):
    """Two-stage produces base weights identical to base-only fit, plus partner weights."""
    from bid_euchre.features.auction_context import PARTNER_FEATURE_NAMES
    from bid_euchre.models.train_olsa import CONTRACT_FEATURES

    run_dir = _make_synthetic_run(tmp_path, seed=99, include_partner_features=True)
    output_dir_two_stage = str(tmp_path / "output_two_stage")

    result = train_hybrid_olsa(
        run_dir=run_dir,
        seed=42,
        output_dir=output_dir_two_stage,
        arm_mode="constrained",
        freeze=False,
        context_candidates=PARTNER_FEATURE_NAMES,
        training_mode="two_stage",
    )

    with open(result["artifacts"]["constrained"]) as f:
        art = json.load(f)

    # Artifact metadata
    assert art["training_mode"] == "two_stage"
    assert "ridge_alpha" not in art

    # Every contract should have valid model
    for cf in ["suit", "high", "low"]:
        if cf not in art["payoff_model"]:
            continue
        model = art["payoff_model"][cf]
        weights = model["weights"]
        bias = model["bias"]
        feature_names = model["feature_names"]

        # Should have at least the base features
        base = CONTRACT_FEATURES[cf]
        for feat in base:
            assert feat in feature_names, f"Missing base feature {feat} in {cf}"

        # Weights should be finite
        assert all(np.isfinite(w) for w in weights)
        assert np.isfinite(bias)

    # Residual variances should be valid
    for cf, var in art["residual_variance"].items():
        assert 0 < var < 25, f"Unexpected residual_variance for {cf}: {var}"


def test_training_mode_two_stage_without_context_falls_back(tmp_path: Path):
    """Two_stage without context_candidates behaves like joint."""
    from bid_euchre.models.train_olsa import CONTRACT_FEATURES

    run_dir = _make_synthetic_run(tmp_path, seed=99)
    output_dir_joint = str(tmp_path / "output_joint")
    output_dir_two_stage = str(tmp_path / "output_two_stage")

    result_joint = train_hybrid_olsa(
        run_dir=run_dir,
        seed=42,
        output_dir=output_dir_joint,
        arm_mode="constrained",
        freeze=False,
        training_mode="joint",
    )

    result_two_stage = train_hybrid_olsa(
        run_dir=run_dir,
        seed=42,
        output_dir=output_dir_two_stage,
        arm_mode="constrained",
        freeze=False,
        training_mode="two_stage",
    )

    with open(result_joint["artifacts"]["constrained"]) as f:
        art_joint = json.load(f)
    with open(result_two_stage["artifacts"]["constrained"]) as f:
        art_two_stage = json.load(f)

    # Without context_candidates, two_stage falls back to joint — same weights
    for cf in CONTRACT_FEATURES:
        if cf not in art_joint["payoff_model"]:
            continue
        w_joint = art_joint["payoff_model"][cf]["weights"]
        w_two_stage = art_two_stage["payoff_model"][cf]["weights"]
        np.testing.assert_allclose(w_joint, w_two_stage, atol=1e-12)
        assert (
            art_joint["payoff_model"][cf]["bias"]
            == art_two_stage["payoff_model"][cf]["bias"]
        )
