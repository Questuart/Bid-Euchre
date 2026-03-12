"""Tests for the R1.5.3 Step 0 suit decision diagnostic.

Covers: error taxonomy classification, bid-level headroom calculation,
boundary analysis, counterfactual wrong-contract/under-bid/wrong-level
detection, and OLS prediction reconstruction.
"""

from __future__ import annotations

import json

# Import from scripts/internal — use sys.path since it's not a package
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "internal"))

from suit_decision_diagnostic import (
    _analyze_under_bid,
    _analyze_wrong_contract,
    _analyze_wrong_level,
    analyze_bid_level_headroom,
    analyze_boundary,
    analyze_disagreements,
    analyze_error_taxonomy,
    determine_gate_decision,
    reconstruct_ols_predictions_vectorized,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_h2h_df(
    n_made: int = 30,
    n_set: int = 70,
    made_points: float = 12.0,
    set_points: float = -14.0,
) -> pd.DataFrame:
    """Create synthetic H2H suit bidder DataFrame."""
    rows = []
    for i in range(n_made):
        rows.append(
            {
                "deal_id": i,
                "seat": 0,
                "team": 0,
                "contract_type": "suit",
                "trump": "H",
                "tricks_won": 6,
                "winning_bid": 4,
                "bidder_seat": 0,
                "bidder_team": 0,
                "is_bidder": True,
                "is_declaring_team": True,
                "made_bid": True,
                "points_won": made_points,
                "matchup": "action_value_v1_vs_hybrid_olsa_r0",
                "av1_team": 0,
            }
        )
    for i in range(n_set):
        rows.append(
            {
                "deal_id": n_made + i,
                "seat": 0,
                "team": 0,
                "contract_type": "suit",
                "trump": "S",
                "tricks_won": 3,
                "winning_bid": 4,
                "bidder_seat": 0,
                "bidder_team": 0,
                "is_bidder": True,
                "is_declaring_team": True,
                "made_bid": False,
                "points_won": set_points,
                "matchup": "action_value_v1_vs_hybrid_olsa_r0",
                "av1_team": 0,
            }
        )
    return pd.DataFrame(rows)


def _make_cf_all_df() -> pd.DataFrame:
    """Create synthetic counterfactual dataset with multiple action types."""
    rows = []
    # Hand 0: suit is best action (made), also has pass and high alternatives
    rows.append(
        {
            "hand_id": 0,
            "deal_id": 0,
            "focal_seat": 0,
            "action_type": "bid",
            "contract_family": "suit",
            "focal_declared": True,
            "bid_n": 4,
            "net_points": 12.0,
            "tricks_won": 6,
            "bowers": 2.0,
            "trump_count": 5.0,
        }
    )
    rows.append(
        {
            "hand_id": 0,
            "deal_id": 0,
            "focal_seat": 0,
            "action_type": "bid",
            "contract_family": "high",
            "focal_declared": True,
            "bid_n": 4,
            "net_points": 8.0,
            "tricks_won": 5,
            "bowers": 0.0,
            "trump_count": 0.0,
        }
    )
    rows.append(
        {
            "hand_id": 0,
            "deal_id": 0,
            "focal_seat": 0,
            "action_type": "pass",
            "contract_family": "none",
            "focal_declared": False,
            "bid_n": 0,
            "net_points": -2.0,
            "tricks_won": 3,
            "bowers": 0.0,
            "trump_count": 0.0,
        }
    )

    # Hand 1: suit is wrong contract (high is better)
    rows.append(
        {
            "hand_id": 1,
            "deal_id": 1,
            "focal_seat": 0,
            "action_type": "bid",
            "contract_family": "suit",
            "focal_declared": True,
            "bid_n": 4,
            "net_points": -14.0,
            "tricks_won": 3,
            "bowers": 1.0,
            "trump_count": 3.0,
        }
    )
    rows.append(
        {
            "hand_id": 1,
            "deal_id": 1,
            "focal_seat": 0,
            "action_type": "bid",
            "contract_family": "high",
            "focal_declared": True,
            "bid_n": 4,
            "net_points": 8.0,
            "tricks_won": 5,
            "bowers": 0.0,
            "trump_count": 0.0,
        }
    )
    rows.append(
        {
            "hand_id": 1,
            "deal_id": 1,
            "focal_seat": 0,
            "action_type": "pass",
            "contract_family": "none",
            "focal_declared": False,
            "bid_n": 0,
            "net_points": 1.0,
            "tricks_won": 4,
            "bowers": 0.0,
            "trump_count": 0.0,
        }
    )

    # Hand 2: pass is best, but suit is profitable (under-bid scenario)
    rows.append(
        {
            "hand_id": 2,
            "deal_id": 2,
            "focal_seat": 0,
            "action_type": "pass",
            "contract_family": "none",
            "focal_declared": False,
            "bid_n": 0,
            "net_points": -1.0,
            "tricks_won": 3,
            "bowers": 0.0,
            "trump_count": 0.0,
        }
    )
    rows.append(
        {
            "hand_id": 2,
            "deal_id": 2,
            "focal_seat": 0,
            "action_type": "bid",
            "contract_family": "suit",
            "focal_declared": True,
            "bid_n": 4,
            "net_points": 6.0,
            "tricks_won": 5,
            "bowers": 1.0,
            "trump_count": 4.0,
        }
    )

    # Hand 3: suit with multiple bid levels (wrong level scenario)
    rows.append(
        {
            "hand_id": 3,
            "deal_id": 3,
            "focal_seat": 0,
            "action_type": "bid",
            "contract_family": "suit",
            "focal_declared": True,
            "bid_n": 4,
            "net_points": 12.0,
            "tricks_won": 7,
            "bowers": 2.0,
            "trump_count": 6.0,
        }
    )
    rows.append(
        {
            "hand_id": 3,
            "deal_id": 3,
            "focal_seat": 0,
            "action_type": "bid",
            "contract_family": "suit",
            "focal_declared": True,
            "bid_n": 5,
            "net_points": 14.0,
            "tricks_won": 7,
            "bowers": 2.0,
            "trump_count": 6.0,
        }
    )
    rows.append(
        {
            "hand_id": 3,
            "deal_id": 3,
            "focal_seat": 0,
            "action_type": "bid",
            "contract_family": "suit",
            "focal_declared": True,
            "bid_n": 6,
            "net_points": 8.0,
            "tricks_won": 7,
            "bowers": 2.0,
            "trump_count": 6.0,
        }
    )

    return pd.DataFrame(rows)


def _make_cf_suit_df() -> pd.DataFrame:
    """Create synthetic counterfactual suit-only dataset."""
    rows = []
    # Mix of made and set outcomes at different prediction levels
    rng = np.random.RandomState(42)
    for i in range(200):
        # Create bimodal distribution
        made = rng.random() < 0.37  # 37% make rate
        net_pts = rng.normal(2.3, 3.6) if made else rng.normal(-13.4, 1.8)
        tricks = max(0, min(10, int(rng.normal(7 if made else 3, 1))))
        bid_n = 4

        rows.append(
            {
                "hand_id": i,
                "deal_id": i,
                "focal_seat": 0,
                "action_type": "bid",
                "contract_family": "suit",
                "focal_declared": True,
                "bid_n": bid_n,
                "net_points": net_pts,
                "tricks_won": tricks,
                "made_contract": tricks >= bid_n,
                "bid_n_sq": bid_n**2,
                # Feature columns needed for OLS reconstruction
                "bowers": rng.choice([0, 1, 2]),
                "trump_count": rng.randint(2, 8),
                "offsuit_aces": rng.randint(0, 5),
                "offsuit_non_ace_count": rng.randint(0, 8),
                "hand_value": rng.normal(5, 2),
                "trump_rb_count": rng.choice([0, 1]),
                "trump_lb_count": rng.choice([0, 1]),
                "trump_ace_count": rng.choice([0, 1, 2]),
                "trump_king_count": rng.choice([0, 1, 2]),
                "trump_queen_count": rng.choice([0, 1, 2]),
                "trump_ten_count": rng.choice([0, 1, 2]),
                "highest_trump_rank": rng.randint(10, 15),
                "second_highest_trump_rank": rng.randint(0, 14),
                "third_highest_trump_rank": rng.randint(0, 13),
                "trump_power_sum": rng.normal(10, 5),
                "trump_duplicate_pairs": rng.choice([0, 1, 2]),
                "offsuit_king_count_total": rng.randint(0, 4),
                "offsuit_queen_count_total": rng.randint(0, 4),
                "offsuit_suits_with_ace": rng.randint(0, 4),
                "offsuit_suits_with_double_ace": rng.choice([0, 1]),
                "offsuit_suits_with_ace_and_king": rng.choice([0, 1, 2]),
                "void_count": rng.choice([0, 1, 2]),
                "max_suit_len": rng.randint(2, 6),
                "second_suit_len": rng.randint(1, 5),
                "third_suit_len": rng.randint(0, 4),
                "fourth_suit_len": rng.randint(0, 3),
                "num_singletons": rng.choice([0, 1, 2]),
                "num_doubletons": rng.choice([0, 1, 2, 3]),
                "offsuit_tens_count": rng.randint(0, 4),
                "offsuit_length_3plus_count": rng.randint(0, 3),
                "offsuit_best_rank_sum": rng.normal(10, 3),
                "offsuit_secondbest_rank_sum": rng.normal(7, 3),
                "double_ten_jack_count": rng.choice([0, 1, 2]),
                "high_card_count": rng.randint(0, 6),
                "low_card_count": rng.randint(0, 6),
                "trump_count_x_void_count": rng.randint(0, 10),
                "trump_count_x_offsuit_ace": rng.randint(0, 12),
                "losing_tricks_count": rng.randint(0, 8),
                "quick_tricks": rng.normal(3, 1.5),
                "partner_bid_level": rng.choice([0, 1, 2, 3]),
                "partner_passed": rng.choice([0.0, 1.0]),
                "partner_suit_match": rng.choice([0.0, 1.0]),
                "current_high_bid": rng.choice([0, 1, 2, 3]),
                "is_high": 0.0,
                "is_low": 0.0,
                "trump_C": float(i % 4 == 0),
                "trump_D": float(i % 4 == 1),
                "trump_H": float(i % 4 == 2),
                "trump_S": float(i % 4 == 3),
                "seat_rel_1": float(i % 4 == 1),
                "seat_rel_2": float(i % 4 == 2),
                "seat_rel_3": float(i % 4 == 3),
            }
        )

    return pd.DataFrame(rows)


def _make_artifact(tmp_path: Path) -> Path:
    """Create a minimal AV v1 model artifact for OLS reconstruction tests."""
    from bid_euchre.strategy.bidding import ACTION_FEATURE_NAMES, STATE_FEATURE_NAMES

    feature_names = list(STATE_FEATURE_NAMES) + list(ACTION_FEATURE_NAMES)
    n_features = len(feature_names)

    # Simple coefficients: mostly zero, a few meaningful ones
    coefficients = [0.0] * n_features
    # bowers (idx 0) → positive
    coefficients[0] = 1.5
    # trump_count (idx 1) → positive
    coefficients[1] = 0.8
    # bid_n (last-1) → negative
    coefficients[-2] = -2.0

    artifact = {
        "schema_version": "action_value_olsa_v1",
        "models": {
            "suit": {
                "coefficients": coefficients,
                "intercept": -5.0,
                "feature_names": feature_names,
            },
            "high": {
                "coefficients": [0.0] * n_features,
                "intercept": 0.0,
                "feature_names": feature_names,
            },
            "low": {
                "coefficients": [0.0] * n_features,
                "intercept": 0.0,
                "feature_names": feature_names,
            },
        },
        "pass_model": {
            "coefficients": [0.0] * len(STATE_FEATURE_NAMES),
            "intercept": 0.0,
            "feature_names": list(STATE_FEATURE_NAMES),
        },
        "metadata": {"context_features": []},
    }

    path = tmp_path / "test_artifact.json"
    with open(path, "w") as f:
        json.dump(artifact, f)
    return path


# ---------------------------------------------------------------------------
# Tests: Error Taxonomy
# ---------------------------------------------------------------------------


class TestErrorTaxonomy:
    def test_basic_classification(self):
        """Over-bid and made counts match input data."""
        h2h = _make_h2h_df(n_made=30, n_set=70)
        cf = _make_cf_all_df()
        result = analyze_error_taxonomy(h2h, cf)

        assert result["n_suit_hands_h2h"] == 100
        assert result["over_bid"]["count"] == 70
        assert result["over_bid"]["fraction"] == pytest.approx(0.7)
        assert result["made"]["count"] == 30
        assert result["made"]["fraction"] == pytest.approx(0.3)

    def test_over_bid_points_negative(self):
        """Over-bid hands have negative average points."""
        h2h = _make_h2h_df(n_made=30, n_set=70, set_points=-14.0)
        cf = _make_cf_all_df()
        result = analyze_error_taxonomy(h2h, cf)

        assert result["over_bid"]["avg_points"] < 0

    def test_made_points_positive(self):
        """Made hands have positive average points."""
        h2h = _make_h2h_df(n_made=30, n_set=70, made_points=12.0)
        cf = _make_cf_all_df()
        result = analyze_error_taxonomy(h2h, cf)

        assert result["made"]["avg_points"] > 0

    def test_empty_input(self):
        """Empty H2H data returns error indicator."""
        empty = pd.DataFrame(columns=_make_h2h_df().columns)
        cf = _make_cf_all_df()
        result = analyze_error_taxonomy(empty, cf)
        assert "error" in result


class TestWrongContract:
    def test_detects_wrong_contract(self):
        """Identifies hands where high/low beats suit."""
        cf = _make_cf_all_df()
        result = _analyze_wrong_contract(cf)

        # Hand 1 has suit=-14, high=8 → wrong contract
        assert result["count"] >= 1
        assert result["fraction"] > 0
        assert result["avg_cost"] < 0  # negative = suit was worse

    def test_correct_contract_not_flagged(self):
        """Hand 0 has suit=12 > high=8 → not wrong contract."""
        cf = _make_cf_all_df()
        result = _analyze_wrong_contract(cf)

        # Should not flag hand 0
        assert result["count"] < result["n_suit_hands"]


class TestUnderBid:
    def test_detects_under_bid(self):
        """Identifies pass hands with profitable suit alternative."""
        cf = _make_cf_all_df()
        result = _analyze_under_bid(cf)

        # Hand 2: pass=-1, suit=6 → under-bid
        assert result["count"] >= 1
        assert result["avg_opportunity"] > 0

    def test_no_under_bid_when_pass_better(self):
        """Hand 1: pass=1, suit=-14 → not under-bid (suit worse than pass)."""
        # Hand 1's pass is 1.0, suit is -14.0 — suit is not profitable vs pass
        cf = _make_cf_all_df()
        result = _analyze_under_bid(cf)

        # Hand 0 (pass=-2, suit=12) and hand 2 (pass=-1, suit=6) are under-bids.
        # Hand 1 (pass=1, suit=-14) is NOT under-bid. So count = 2.
        assert result["count"] == 2
        # Verify hand 1 is excluded by checking count < total pass hands
        assert result["count"] < result["n_pass_hands"]


class TestWrongLevel:
    def test_detects_wrong_level(self):
        """Identifies hands where higher bid level is better."""
        cf = _make_cf_all_df()
        result = _analyze_wrong_level(cf)

        # Hand 3: bid-4=12, bid-5=14, bid-6=8 → level 5 is optimal
        assert result["count"] >= 1
        assert result["avg_cost"] < 0  # min level is suboptimal


# ---------------------------------------------------------------------------
# Tests: Bid-Level Headroom
# ---------------------------------------------------------------------------


class TestBidLevelHeadroom:
    def test_identifies_improvable_hands(self):
        """Finds hands where optimal level differs from minimum."""
        cf_suit = pd.DataFrame(
            [
                # Hand with single level — not improvable
                {
                    "hand_id": 0,
                    "bid_n": 4,
                    "net_points": 10.0,
                    "focal_declared": True,
                    "contract_family": "suit",
                    "tricks_won": 6,
                    "made_contract": True,
                },
                # Hand with two levels — level 5 is better
                {
                    "hand_id": 1,
                    "bid_n": 4,
                    "net_points": 8.0,
                    "focal_declared": True,
                    "contract_family": "suit",
                    "tricks_won": 5,
                    "made_contract": True,
                },
                {
                    "hand_id": 1,
                    "bid_n": 5,
                    "net_points": 10.0,
                    "focal_declared": True,
                    "contract_family": "suit",
                    "tricks_won": 5,
                    "made_contract": True,
                },
                # Hand where min level is already best
                {
                    "hand_id": 2,
                    "bid_n": 4,
                    "net_points": 12.0,
                    "focal_declared": True,
                    "contract_family": "suit",
                    "tricks_won": 7,
                    "made_contract": True,
                },
                {
                    "hand_id": 2,
                    "bid_n": 5,
                    "net_points": 6.0,
                    "focal_declared": True,
                    "contract_family": "suit",
                    "tricks_won": 7,
                    "made_contract": True,
                },
            ]
        )

        result = analyze_bid_level_headroom(cf_suit)

        assert result["n_hands_analyzed"] == 2  # hands 1 and 2 have multi-level
        assert result["n_improvable"] == 1  # only hand 1
        assert result["avg_improvement_when_improvable"] == pytest.approx(2.0)

    def test_all_optimal_at_min(self):
        """No headroom when minimum level is always best."""
        cf_suit = pd.DataFrame(
            [
                {
                    "hand_id": 0,
                    "bid_n": 4,
                    "net_points": 12.0,
                    "focal_declared": True,
                    "contract_family": "suit",
                    "tricks_won": 7,
                    "made_contract": True,
                },
                {
                    "hand_id": 0,
                    "bid_n": 5,
                    "net_points": 6.0,
                    "focal_declared": True,
                    "contract_family": "suit",
                    "tricks_won": 7,
                    "made_contract": True,
                },
            ]
        )

        result = analyze_bid_level_headroom(cf_suit)
        assert result["n_improvable"] == 0
        assert result["pct_improvable"] == 0.0


# ---------------------------------------------------------------------------
# Tests: OLS Prediction Reconstruction
# ---------------------------------------------------------------------------


class TestOLSReconstruction:
    def test_known_prediction(self, tmp_path):
        """Reconstructed OLS matches manual calculation."""
        artifact_path = _make_artifact(tmp_path)
        cf_suit = _make_cf_suit_df().head(5)

        predictions = reconstruct_ols_predictions_vectorized(cf_suit, artifact_path)

        # Manual: intercept(-5) + bowers*1.5 + trump_count*0.8 + bid_n*(-2.0)
        for i, (_, row) in enumerate(cf_suit.iterrows()):
            expected = (
                -5.0
                + row["bowers"] * 1.5
                + row["trump_count"] * 0.8
                + row["bid_n"] * (-2.0)
            )
            assert predictions[i] == pytest.approx(
                expected, abs=1e-10
            ), f"Row {i}: expected {expected}, got {predictions[i]}"

    def test_output_shape(self, tmp_path):
        """Prediction array matches input row count."""
        artifact_path = _make_artifact(tmp_path)
        cf_suit = _make_cf_suit_df()

        predictions = reconstruct_ols_predictions_vectorized(cf_suit, artifact_path)
        assert len(predictions) == len(cf_suit)


# ---------------------------------------------------------------------------
# Tests: Boundary Analysis
# ---------------------------------------------------------------------------


class TestBoundaryAnalysis:
    def test_runs_without_error(self, tmp_path):
        """Boundary analysis completes on synthetic data."""
        artifact_path = _make_artifact(tmp_path)
        cf_suit = _make_cf_suit_df()

        result = analyze_boundary(cf_suit, artifact_path)

        assert "r_squared" in result
        assert "calibration_bins" in result
        assert "error_concentration" in result
        assert "bimodality" in result
        assert result["n_rows"] == len(cf_suit)

    def test_error_concentration_sums_to_100(self, tmp_path):
        """Error concentration percentages sum to approximately 100%."""
        artifact_path = _make_artifact(tmp_path)
        cf_suit = _make_cf_suit_df()

        result = analyze_boundary(cf_suit, artifact_path)
        ec = result["error_concentration"]
        total = ec["boundary_pct"] + ec["clear_make_pct"] + ec["clear_set_pct"]
        assert total == pytest.approx(100.0, abs=1.0)

    def test_bimodality_gap_positive(self, tmp_path):
        """Gap between made and set averages is positive."""
        artifact_path = _make_artifact(tmp_path)
        cf_suit = _make_cf_suit_df()

        result = analyze_boundary(cf_suit, artifact_path)
        assert result["bimodality"]["gap"] > 0


# ---------------------------------------------------------------------------
# Tests: Gate Decision
# ---------------------------------------------------------------------------


class TestGateDecision:
    def test_boundary_dominant_selects_track_a(self):
        """>60% boundary error → Track A."""
        boundary = {"error_concentration": {"boundary_pct": 75.0}}
        taxonomy = {"wrong_contract": {"fraction": 0.1}}
        headroom = {"pct_improvable": 10.0, "headroom_per_hand": 0.1}

        gate = determine_gate_decision(taxonomy, boundary, headroom)
        assert "Track A" in gate["recommended_track"]

    def test_wrong_contract_dominant_selects_new_direction(self):
        """>30% wrong contract → new direction."""
        boundary = {"error_concentration": {"boundary_pct": 30.0}}
        taxonomy = {"wrong_contract": {"fraction": 0.4}}
        headroom = {"pct_improvable": 10.0, "headroom_per_hand": 0.1}

        gate = determine_gate_decision(taxonomy, boundary, headroom)
        assert "contract selection" in gate["recommended_track"].lower()

    def test_headroom_dominant_selects_level_fix(self):
        """>30% improvable bid level → level fix."""
        boundary = {"error_concentration": {"boundary_pct": 30.0}}
        taxonomy = {"wrong_contract": {"fraction": 0.1}}
        headroom = {"pct_improvable": 45.0, "headroom_per_hand": 0.5}

        gate = determine_gate_decision(taxonomy, boundary, headroom)
        assert "level" in gate["recommended_track"].lower()

    def test_default_fallback(self):
        """No dominant signal → Track B or further investigation."""
        boundary = {"error_concentration": {"boundary_pct": 30.0}}
        taxonomy = {"wrong_contract": {"fraction": 0.1}}
        headroom = {"pct_improvable": 10.0, "headroom_per_hand": 0.05}

        gate = determine_gate_decision(taxonomy, boundary, headroom)
        assert (
            "Track B" in gate["recommended_track"]
            or "investigation" in gate["recommended_track"]
        )


# ---------------------------------------------------------------------------
# Tests: Disagreement Analysis
# ---------------------------------------------------------------------------


class TestDisagreementAnalysis:
    def test_basic_metrics(self):
        """Disagreement analysis produces expected metrics."""
        h2h_suit = _make_h2h_df(n_made=30, n_set=70)

        # Create full H2H with R0 suit hands too
        r0_rows = []
        for i in range(50):
            r0_rows.append(
                {
                    "deal_id": 200 + i,
                    "seat": 1,
                    "team": 1,
                    "contract_type": "suit",
                    "trump": "D",
                    "tricks_won": 5,
                    "winning_bid": 4,
                    "bidder_seat": 1,
                    "bidder_team": 1,
                    "is_bidder": True,
                    "is_declaring_team": True,
                    "made_bid": i < 25,  # 50% make rate
                    "points_won": 10.0 if i < 25 else -14.0,
                    "matchup": "hybrid_olsa_r0_vs_action_value_v1",
                    "av1_team": 1,  # AV v1 is team 1, so R0 is team 0... wait
                }
            )
        # R0 is the non-AV1 team. In this matchup, AV v1 is team 1,
        # so R0 is team 0.
        for row in r0_rows:
            row["av1_team"] = 1  # AV v1 is team 1
            row["team"] = 0  # R0 is on team 0

        full_h2h = pd.concat([h2h_suit, pd.DataFrame(r0_rows)], ignore_index=True)

        result = analyze_disagreements(h2h_suit, full_h2h)

        assert result["av1_suit_hands"] == 100
        assert result["av1_suit_made_rate"] == pytest.approx(0.3)
        assert result["r0_suit_hands"] == 50
        assert result["r0_suit_made_rate"] == pytest.approx(0.5)
