"""Tests for the normalizer offline go/no-go screen.

Covers: split reproducibility, utility transform, objective progress,
tie-break parity, bootstrap grouping, guardrails, end-to-end smoke.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from bid_euchre.analysis.sweep import deal_partition

# scripts/internal/ is not a package — add to sys.path so we can import the script.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "internal"))

import run_normalizer_offline_screen as _screen  # noqa: E402

CONTRACT_KEYS = _screen.CONTRACT_KEYS
FAMILY_IDX_FOR_KEY = _screen.FAMILY_IDX_FOR_KEY
FAMILY_NAMES = _screen.FAMILY_NAMES
N_CONTRACTS = _screen.N_CONTRACTS
N_FAMILIES = _screen.N_FAMILIES
_select_normalized_contract = _screen._select_normalized_contract
apply_rubric = _screen.apply_rubric
build_artifact = _screen.build_artifact
diagnostic_zero = _screen.diagnostic_zero
evaluate_validation = _screen.evaluate_validation
fit_normalizer = _screen.fit_normalizer
make_hand_decisions = _screen.make_hand_decisions
softmax_nll = _screen.softmax_nll


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_synthetic_hand_table(
    n_deals: int = 50,
    n_seats: int = 4,
    seed: int = 42,
) -> pd.DataFrame:
    """Create a synthetic hand table for testing.

    Each (deal_id, seat) gets 6 contract_key rows with plausible values.
    """
    rng = np.random.RandomState(seed)
    rows = []
    for deal_id in range(n_deals):
        for seat in range(n_seats):
            for i, ck in enumerate(CONTRACT_KEYS):
                family = FAMILY_NAMES[FAMILY_IDX_FOR_KEY[i]]
                mu = rng.normal(5.0, 1.5)
                bid_n = max(1, min(10, int(round(mu))))
                # Make suit contracts generally higher utility
                if family == "suit":
                    utility = rng.uniform(0.5, 3.0)
                elif family == "high":
                    utility = rng.uniform(-0.5, 1.5)
                else:  # low
                    utility = rng.uniform(-1.0, 1.0)
                tricks = rng.randint(0, 11)
                if tricks >= bid_n:
                    actual_net = 2.0 * tricks - 10.0
                else:
                    actual_net = tricks - bid_n - 10.0
                rows.append(
                    {
                        "deal_id": deal_id,
                        "seat": seat,
                        "contract_key": ck,
                        "contract_family": family,
                        "mu": mu,
                        "bid_n": bid_n,
                        "utility": utility,
                        "actual_net": actual_net,
                        "tricks_won": tricks,
                    }
                )
    df = pd.DataFrame(rows)
    df = df.sort_values(["deal_id", "seat", "contract_key"]).reset_index(drop=True)
    return df


def _make_calibratable_data(n_hands: int = 500, seed: int = 42) -> dict:
    """Create synthetic data where a normalizer CAN improve accuracy.

    The "true" best contract is determined by scaled utilities, but the raw
    utilities have systematic scale differences across families.
    """
    rng = np.random.RandomState(seed)

    # True scale factors (what the normalizer should learn)
    true_alpha = np.array([1.5, 0.8, 1.0])  # high, low, suit
    true_beta = np.array([-0.5, 0.3, 0.0])

    utilities = rng.normal(1.0, 0.5, size=(n_hands, N_CONTRACTS))
    # Make all utilities positive for simplicity
    utilities = np.abs(utilities) + 0.1

    # The "true" scaled utilities determine the oracle choice
    alpha_per_key = true_alpha[FAMILY_IDX_FOR_KEY]
    beta_per_key = true_beta[FAMILY_IDX_FOR_KEY]
    true_u = utilities * alpha_per_key[None, :] + beta_per_key[None, :]
    oracle_indices = np.argmax(true_u, axis=1)

    # Synthetic bid_ns and actual_nets
    bid_ns = np.full((n_hands, N_CONTRACTS), 3)
    actual_nets = rng.normal(0.0, 2.0, size=(n_hands, N_CONTRACTS))
    # Make oracle contract have best actual_net
    for i in range(n_hands):
        actual_nets[i, oracle_indices[i]] = rng.uniform(2.0, 5.0)

    tricks_won = np.full((n_hands, N_CONTRACTS), 5)
    deal_ids = np.arange(n_hands) // 4  # 4 hands per deal
    seats = np.tile(np.arange(4), n_hands // 4 + 1)[:n_hands]

    # Model (raw utility) would pick argmax of raw utilities
    model_idx = np.argmax(utilities, axis=1)
    model_net = actual_nets[np.arange(n_hands), model_idx]

    return {
        "deal_ids": deal_ids,
        "seats": seats,
        "utilities": utilities,
        "bid_ns": bid_ns,
        "actual_nets": actual_nets,
        "tricks_won": tricks_won,
        "oracle_idx": oracle_indices,
        "oracle_net": actual_nets[np.arange(n_hands), oracle_indices],
        "model_idx": model_idx,
        "model_net": model_net,
        "_true_alpha": true_alpha,
        "_true_beta": true_beta,
    }


# ---------------------------------------------------------------------------
# Test 1: Split reproducibility
# ---------------------------------------------------------------------------


class TestSplitReproducibility:
    def test_same_seed_same_result(self):
        """deal_partition produces identical splits with the same seed."""
        deal_ids = [str(i) for i in range(100)]
        splits_a = [deal_partition(d, seed=42) for d in deal_ids]
        splits_b = [deal_partition(d, seed=42) for d in deal_ids]
        assert splits_a == splits_b

    def test_different_seed_different_result(self):
        """Different seeds produce different partitions."""
        deal_ids = [str(i) for i in range(100)]
        splits_42 = [deal_partition(d, seed=42) for d in deal_ids]
        splits_99 = [deal_partition(d, seed=99) for d in deal_ids]
        assert splits_42 != splits_99

    def test_approximate_60_40_split(self):
        """Split is approximately 60/40 train/val."""
        deal_ids = [str(i) for i in range(10000)]
        splits = [deal_partition(d, seed=42) for d in deal_ids]
        train_frac = sum(1 for s in splits if s == "train") / len(splits)
        assert (
            0.55 < train_frac < 0.65
        ), f"Train fraction {train_frac:.3f} outside [0.55, 0.65]"


# ---------------------------------------------------------------------------
# Test 2: Utility transform correctness
# ---------------------------------------------------------------------------


class TestUtilityTransform:
    def test_identity_transform(self):
        """Alpha=1, beta=0 leaves utilities unchanged."""
        params = {
            "alpha": {"high": 1.0, "low": 1.0, "suit": 1.0},
            "beta": {"high": 0.0, "low": 0.0, "suit": 0.0},
        }
        utilities = np.array([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]])
        bid_ns = np.array([[3, 3, 3, 3, 3, 3]])

        norm_idx, u_norm = _select_normalized_contract(utilities, bid_ns, params)
        np.testing.assert_allclose(u_norm, utilities)

    def test_scaling_changes_ranking(self):
        """Non-identity alpha/beta can change which contract is selected."""
        # Raw: suit_S (idx=5) has highest utility
        utilities = np.array([[0.5, 0.3, 1.0, 1.0, 1.0, 2.0]])
        bid_ns = np.array([[3, 3, 3, 3, 3, 3]])

        # Without normalizer: suit_S wins (highest raw utility)
        assert np.argmax(utilities[0]) == 5

        # With normalizer: boost high (idx=0), suppress suit
        params = {
            "alpha": {"high": 2.0, "low": 1.0, "suit": 0.5},
            "beta": {"high": 1.0, "low": 0.0, "suit": -0.5},
        }
        norm_idx, u_norm = _select_normalized_contract(utilities, bid_ns, params)
        # high: 2.0 * 0.5 + 1.0 = 2.0
        # suit_S: 0.5 * 2.0 + (-0.5) = 0.5
        assert norm_idx[0] == 0, "Normalizer should select high (idx=0)"

    def test_per_family_grouping(self):
        """All suit contracts share the same alpha/beta."""
        params = {
            "alpha": {"high": 1.0, "low": 1.0, "suit": 2.0},
            "beta": {"high": 0.0, "low": 0.0, "suit": 1.0},
        }
        # All suit contracts (indices 2-5) should be scaled by alpha=2, beta=1
        utilities = np.array([[1.0, 1.0, 1.0, 1.0, 1.0, 1.0]])
        bid_ns = np.array([[3, 3, 3, 3, 3, 3]])
        _, u_norm = _select_normalized_contract(utilities, bid_ns, params)

        # high (idx 0): 1.0 * 1.0 + 0.0 = 1.0
        # low (idx 1): 1.0 * 1.0 + 0.0 = 1.0
        # suit_* (idx 2-5): 1.0 * 2.0 + 1.0 = 3.0
        assert u_norm[0, 0] == pytest.approx(1.0)
        assert u_norm[0, 1] == pytest.approx(1.0)
        for j in range(2, 6):
            assert u_norm[0, j] == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# Test 3: Objective decreases from identity
# ---------------------------------------------------------------------------


class TestObjectiveProgress:
    def test_optimizer_improves_on_calibratable_data(self):
        """Optimizer reduces loss from identity on synthetically miscalibrated data."""
        data = _make_calibratable_data(n_hands=500, seed=42)
        partition = np.array(
            [deal_partition(str(d), seed=42) for d in data["deal_ids"]]
        )
        train_mask = partition == "train"

        # Loss at identity
        x0 = np.array([1.0] * N_FAMILIES + [0.0] * N_FAMILIES)
        loss_identity = softmax_nll(
            x0, data["utilities"], data["oracle_idx"], FAMILY_IDX_FOR_KEY, 1e-3
        )

        # Fit and get final loss
        fit_result = fit_normalizer(data, train_mask)
        assert fit_result["optimizer_status"] == "converged"
        assert (
            fit_result["final_loss"] < loss_identity
        ), f"Optimizer did not improve: {fit_result['final_loss']:.6f} >= {loss_identity:.6f}"

    def test_normalized_accuracy_improves(self):
        """Normalizer improves oracle-match accuracy on calibratable data."""
        data = _make_calibratable_data(n_hands=500, seed=42)
        partition = np.array(
            [deal_partition(str(d), seed=42) for d in data["deal_ids"]]
        )
        train_mask = partition == "train"

        fit_result = fit_normalizer(data, train_mask)
        assert (
            fit_result["train_accuracy_normalized"]
            > fit_result["train_accuracy_baseline"]
        )


# ---------------------------------------------------------------------------
# Test 4: Tie-break parity
# ---------------------------------------------------------------------------


class TestTieBreakParity:
    def test_higher_bid_n_wins_tie(self):
        """When utilities are equal, higher bid_n breaks the tie."""
        hand_table = _make_synthetic_hand_table(n_deals=1, n_seats=1, seed=0)
        # Override: set all utilities to the same positive value
        hand_table["utility"] = 1.0
        # Set different bid_ns
        hand_table["bid_n"] = [3, 3, 3, 3, 5, 3]  # suit_H (idx=4) has bid_n=5
        hand_table["actual_net"] = 0.0

        decisions = make_hand_decisions(hand_table)
        # Model should pick suit_H (idx=4) due to higher bid_n
        assert decisions["model_idx"][0] == 4

    def test_higher_contract_key_index_wins_final_tie(self):
        """When utility AND bid_n are equal, higher contract_key index wins."""
        hand_table = _make_synthetic_hand_table(n_deals=1, n_seats=1, seed=0)
        hand_table["utility"] = 1.0
        hand_table["bid_n"] = 3  # all same
        hand_table["actual_net"] = 0.0

        decisions = make_hand_decisions(hand_table)
        # suit_S (idx=5) should win as last in alphabetical order
        assert decisions["model_idx"][0] == 5


# ---------------------------------------------------------------------------
# Test 5: Bootstrap grouping
# ---------------------------------------------------------------------------


class TestBootstrapGrouping:
    def test_groups_by_deal_id(self):
        """Validation bootstrap aggregates to deal level before resampling."""
        data = _make_calibratable_data(n_hands=200, seed=42)
        partition = np.array(
            [deal_partition(str(d), seed=42) for d in data["deal_ids"]]
        )
        train_mask = partition == "train"
        val_mask = partition == "val"

        fit_result = fit_normalizer(data, train_mask)
        assert fit_result["params"] is not None

        # This should not raise — key matching in bootstrap requires
        # deal-level aggregation (not hand-level, which would have duplicates)
        val_metrics = evaluate_validation(
            data,
            val_mask,
            fit_result["params"],
            n_bootstrap=100,
            seed=42,
        )
        assert "delta_ci_low" in val_metrics
        assert "delta_ci_high" in val_metrics
        assert val_metrics["delta_ci_low"] <= val_metrics["delta_ci_high"]


# ---------------------------------------------------------------------------
# Test 6: Guardrail computations
# ---------------------------------------------------------------------------


class TestGuardrails:
    def test_bid_rate_in_bounds(self):
        """Guardrails pass when bid_rate is within [0.05, 0.95]."""
        from bid_euchre.analysis.sweep import check_guardrails

        ok, violations = check_guardrails({"bid_rate": 0.5, "make_rate": 0.8})
        assert ok
        assert violations == []

    def test_bid_rate_too_high(self):
        """Guardrails fail when bid_rate exceeds cap."""
        from bid_euchre.analysis.sweep import check_guardrails

        ok, violations = check_guardrails({"bid_rate": 0.99, "make_rate": 0.8})
        assert not ok
        assert any("cap" in v for v in violations)

    def test_bid_rate_too_low(self):
        """Guardrails fail when bid_rate below floor."""
        from bid_euchre.analysis.sweep import check_guardrails

        ok, violations = check_guardrails({"bid_rate": 0.02, "make_rate": 0.8})
        assert not ok
        assert any("floor" in v for v in violations)

    def test_make_rate_too_low(self):
        """Guardrails fail when make_rate below floor."""
        from bid_euchre.analysis.sweep import check_guardrails

        ok, violations = check_guardrails({"bid_rate": 0.5, "make_rate": 0.3})
        assert not ok
        assert any("make_rate" in v for v in violations)


# ---------------------------------------------------------------------------
# Test 7: End-to-end smoke test
# ---------------------------------------------------------------------------


class TestEndToEndSmoke:
    def test_artifact_schema(self, tmp_path):
        """End-to-end: synthetic data → artifact with correct schema."""
        data = _make_calibratable_data(n_hands=200, seed=42)

        # Run diagnostic zero
        diag = diagnostic_zero(data)
        assert "n_disagreement_hands" in diag
        assert "early_exit" in diag

        # Partition
        partition = np.array(
            [deal_partition(str(d), seed=42) for d in data["deal_ids"]]
        )
        train_mask = partition == "train"
        val_mask = partition == "val"

        # Fit
        fit_result = fit_normalizer(data, train_mask)
        assert fit_result["params"] is not None

        # Validate
        val_metrics = evaluate_validation(
            data,
            val_mask,
            fit_result["params"],
            n_bootstrap=100,
            seed=42,
        )

        # Decision
        decision, rationale = apply_rubric(diag, val_metrics)
        assert decision in ("GO_TO_FULL_TRACK_E", "NO_GO_DEFER_R1", "NEEDS_REVIEW")
        assert isinstance(rationale, list)

        # Build artifact
        import argparse

        args = argparse.Namespace(
            seed=42,
            pass_threshold=0.0,
            risk_lambda=0.0,
            n_bootstrap=100,
            output=str(tmp_path / "test_artifact.json"),
        )
        artifact = build_artifact(
            args, diag, fit_result, val_metrics, decision, rationale
        )

        # Check schema
        assert artifact["schema"] == "normalizer_offline_screen_v1"
        assert "created_at_utc" in artifact
        assert artifact["seed"] == 42
        assert "diagnostic_zero" in artifact
        assert "fit" in artifact
        assert "val_metrics" in artifact
        assert "decision" in artifact
        assert "rationale" in artifact

        # Check fit sub-schema
        assert "optimizer_status" in artifact["fit"]
        assert "params" in artifact["fit"]
        assert "alpha" in artifact["fit"]["params"]
        assert "beta" in artifact["fit"]["params"]
        for name in FAMILY_NAMES:
            assert name in artifact["fit"]["params"]["alpha"]
            assert name in artifact["fit"]["params"]["beta"]

        # Check val_metrics sub-schema
        vm = artifact["val_metrics"]
        for key in [
            "accuracy_baseline",
            "accuracy_normalized",
            "accuracy_lift",
            "net_eppd_baseline",
            "net_eppd_normalized",
            "delta_net_eppd",
            "delta_ci_low",
            "delta_ci_high",
            "bid_rate_baseline",
            "bid_rate_normalized",
            "bid_rate_delta",
            "new_bidders_count",
            "lost_bidders_count",
            "make_rate_normalized",
            "guardrails_pass",
        ]:
            assert key in vm, f"Missing key: {key}"

        # Artifact is JSON-serializable
        json_str = json.dumps(artifact)
        parsed = json.loads(json_str)
        assert parsed["schema"] == "normalizer_offline_screen_v1"


# ---------------------------------------------------------------------------
# Test: Decision rubric
# ---------------------------------------------------------------------------


class TestDecisionRubric:
    def test_early_exit_is_no_go(self):
        diag = {
            "n_total_hands": 1000,
            "n_disagreement_hands": 500,
            "disagreement_rate": 0.5,
            "utility_gap_quantiles": {"p25": 1.0, "p50": 2.5, "p75": 3.5, "p90": 5.0},
            "early_exit": True,
        }
        decision, rationale = apply_rubric(diag, None)
        assert decision == "NO_GO_DEFER_R1"
        assert any("early exit" in r.lower() for r in rationale)

    def test_go_decision(self):
        diag = {"early_exit": False}
        val = {
            "delta_net_eppd": 0.10,
            "delta_ci_low": 0.03,
            "delta_ci_high": 0.17,
            "accuracy_lift": 0.05,
            "guardrails_pass": True,
            "guardrail_violations": [],
        }
        decision, _ = apply_rubric(diag, val)
        assert decision == "GO_TO_FULL_TRACK_E"

    def test_no_go_negative_delta(self):
        diag = {"early_exit": False}
        val = {
            "delta_net_eppd": -0.02,
            "delta_ci_low": -0.05,
            "delta_ci_high": 0.01,
            "accuracy_lift": 0.01,
            "guardrails_pass": True,
            "guardrail_violations": [],
        }
        decision, _ = apply_rubric(diag, val)
        assert decision == "NO_GO_DEFER_R1"

    def test_needs_review_borderline(self):
        diag = {"early_exit": False}
        val = {
            "delta_net_eppd": 0.05,  # > 0 but < 0.08
            "delta_ci_low": 0.01,  # > 0
            "delta_ci_high": 0.09,  # > 0.03
            "accuracy_lift": 0.025,  # >= 0.02 but < 0.03
            "guardrails_pass": True,
            "guardrail_violations": [],
        }
        decision, _ = apply_rubric(diag, val)
        assert decision == "NEEDS_REVIEW"


# ---------------------------------------------------------------------------
# Test: Diagnostic Zero
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Test: pass_threshold affects model eligibility
# ---------------------------------------------------------------------------


class TestPassThreshold:
    def test_pass_threshold_zero_excludes_negative_utility(self):
        """With pass_threshold=0, hands with utility in (-0.5, 0) do NOT bid."""
        hand_table = _make_synthetic_hand_table(n_deals=1, n_seats=1, seed=0)
        # Set utilities: some negative, some positive
        hand_table["utility"] = [-0.3, -0.1, 0.5, 0.2, -0.4, 1.0]
        hand_table["bid_n"] = 3
        hand_table["actual_net"] = 1.0

        decisions = make_hand_decisions(hand_table, pass_threshold=0.0)
        # Model should only pick from indices where utility > 0 (indices 2, 3, 5)
        assert decisions["model_idx"][0] in (2, 3, 5)
        # Specifically, suit_S (idx=5, utility=1.0) should win
        assert decisions["model_idx"][0] == 5

    def test_pass_threshold_positive_includes_near_zero_utility(self):
        """With pass_threshold=0.5, hands with utility in (-0.5, 0) SHOULD bid."""
        hand_table = _make_synthetic_hand_table(n_deals=1, n_seats=1, seed=0)
        # Set utilities: the "best" is at index 0 with -0.1 (above -0.5 threshold)
        hand_table["utility"] = [-0.1, -0.6, -0.7, -0.8, -0.9, -1.0]
        hand_table["bid_n"] = 3
        hand_table["actual_net"] = 1.0

        # With t=0.0, all utilities are negative → model passes
        decisions_t0 = make_hand_decisions(hand_table, pass_threshold=0.0)
        assert decisions_t0["model_idx"][0] == -1  # pass

        # With t=0.5, utility > -0.5 → index 0 is eligible
        decisions_t05 = make_hand_decisions(hand_table, pass_threshold=0.5)
        assert decisions_t05["model_idx"][0] == 0  # bids on high


# ---------------------------------------------------------------------------
# Test: Oracle eligibility filters by bid_n > 0
# ---------------------------------------------------------------------------


class TestOracleEligibility:
    def test_oracle_skips_bid_n_zero(self):
        """Oracle does NOT select contracts where bid_n == 0."""
        hand_table = _make_synthetic_hand_table(n_deals=1, n_seats=1, seed=0)
        # Contract 0 (high) has best actual_net but bid_n=0
        hand_table["actual_net"] = [10.0, 1.0, 2.0, 3.0, 4.0, 5.0]
        hand_table["bid_n"] = [0, 3, 3, 3, 3, 3]
        hand_table["utility"] = [0.0, 1.0, 1.0, 1.0, 1.0, 1.0]

        decisions = make_hand_decisions(hand_table)
        # Oracle should NOT pick index 0 (bid_n=0), should pick index 5 (next best)
        assert decisions["oracle_idx"][0] != 0
        assert decisions["oracle_idx"][0] == 5

    def test_oracle_all_bid_n_zero_passes(self):
        """When all bid_n == 0, oracle passes (idx=-1, net=0)."""
        hand_table = _make_synthetic_hand_table(n_deals=1, n_seats=1, seed=0)
        hand_table["actual_net"] = [10.0, 5.0, 3.0, 2.0, 1.0, 0.5]
        hand_table["bid_n"] = 0  # all zero
        hand_table["utility"] = -1.0

        decisions = make_hand_decisions(hand_table)
        assert decisions["oracle_idx"][0] == -1
        assert decisions["oracle_net"][0] == 0.0


# ---------------------------------------------------------------------------
# Test: Diagnostic Zero
# ---------------------------------------------------------------------------


class TestDiagnosticZero:
    def test_no_disagreement(self):
        """When model matches oracle perfectly, no early exit."""
        n = 100
        decisions = {
            "oracle_idx": np.arange(n) % N_CONTRACTS,
            "model_idx": np.arange(n) % N_CONTRACTS,  # same as oracle
            "utilities": np.random.RandomState(42).rand(n, N_CONTRACTS),
        }
        diag = diagnostic_zero(decisions)
        assert diag["n_disagreement_hands"] == 0
        assert not diag["early_exit"]

    def test_large_gap_triggers_early_exit(self):
        """Large utility gaps trigger early exit (model poverty)."""
        n = 100
        rng = np.random.RandomState(42)
        oracle_idx = np.zeros(n, dtype=int)  # oracle always picks high
        model_idx = np.full(n, 5, dtype=int)  # model always picks suit_S
        utilities = rng.rand(n, N_CONTRACTS)
        # Make model's chosen utility much higher than oracle's
        utilities[np.arange(n), model_idx] = 10.0
        utilities[np.arange(n), oracle_idx] = 1.0

        decisions = {
            "oracle_idx": oracle_idx,
            "model_idx": model_idx,
            "utilities": utilities,
        }
        diag = diagnostic_zero(decisions)
        assert diag["n_disagreement_hands"] == n
        # Gap = model_util - oracle_util = 10.0 - 1.0 = 9.0 for all hands
        assert diag["utility_gap_quantiles"]["p50"] > 2.0
        assert diag["utility_gap_quantiles"]["p75"] > 3.0
        assert diag["early_exit"]
