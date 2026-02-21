"""
Unit tests for the hybrid OLSa training pipeline.
"""

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from bid_euchre.models.train_hybrid_olsa import train_hybrid_olsa


def _make_synthetic_run(tmp_path: Path, n_hands=100, seed=42):
    """Create a synthetic bidless run directory with parquet files.

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
        "contract_type": contract_type,
        "trump_suit": trump_suit,
    }

    for fname in feature_names:
        # Base value per hand + small per-seat noise (avoids systematic bias)
        base = rng.randn(n_hands)
        noise = rng.normal(0, 0.05, n_rows)
        features_data[fname] = np.repeat(base, 4) + noise

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
    """Rung bundle should be written when arm_mode='both'."""
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

    assert bundle["bundle_type"] == "arc_d_rung_bundle_v1"
    assert bundle["rung_id"] == "r0"
    assert "constrained_artifact" in bundle
    assert "full_artifact" in bundle
