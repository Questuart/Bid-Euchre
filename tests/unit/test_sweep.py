"""Tests for bid_euchre.analysis.sweep — extracted analysis primitives."""

import hashlib

import numpy as np
import pandas as pd
import pytest

from bid_euchre.analysis.sweep import (
    LambdaSweep,
    ParameterSweep,
    ThresholdSweep,
    bid_level_search_vectorized,
    bootstrap_paired_delta,
    check_guardrails,
    compute_ev_vectorized,
    deal_partition,
)
from bid_euchre.strategy.bidding import _compute_ev_static, compute_best_bid

# ---------------------------------------------------------------------------
# deal_partition
# ---------------------------------------------------------------------------


class TestDealPartition:
    def test_deterministic(self):
        """Same input always produces the same output."""
        assert deal_partition("deal_001", seed=42) == deal_partition(
            "deal_001", seed=42
        )

    def test_distribution_60_40(self):
        """Over many IDs, ~60% should land in train."""
        results = [deal_partition(f"deal_{i}", seed=42) for i in range(10_000)]
        train_frac = sum(1 for r in results if r == "train") / len(results)
        assert 0.55 < train_frac < 0.65, f"Expected ~60% train, got {train_frac:.3f}"

    def test_matches_nb56_implementation(self):
        """Extracted function matches the inline nb56 implementation exactly."""

        # Inline reimplementation from nb56 lines 382-386
        def nb56_partition(deal_id: str, seed: int = 42) -> str:
            h = hashlib.sha256(f"{deal_id}:{seed}".encode()).hexdigest()
            bucket = int(h[:8], 16) % 5
            return "train" if bucket < 3 else "val"

        for i in range(200):
            deal_id = f"test_deal_{i}"
            assert deal_partition(deal_id, seed=42) == nb56_partition(deal_id, seed=42)

    def test_seed_matters(self):
        """Different seeds produce different partitions for some IDs."""
        # With enough IDs, at least some should differ between seeds
        results_42 = [deal_partition(f"deal_{i}", seed=42) for i in range(100)]
        results_99 = [deal_partition(f"deal_{i}", seed=99) for i in range(100)]
        assert (
            results_42 != results_99
        ), "Different seeds should produce different partitions"


# ---------------------------------------------------------------------------
# compute_ev_vectorized
# ---------------------------------------------------------------------------


class TestComputeEV:
    def test_sigma_zero_make(self):
        """When sigma=0 and mu >= bid_n, EV = 2*mu - 10."""
        mu = np.array([7.0])
        bid_n = np.array([5])
        result = compute_ev_vectorized(mu, 0.0, bid_n)
        expected = 2.0 * 7.0 - 10.0  # = 4.0
        np.testing.assert_allclose(result, [expected])

    def test_sigma_zero_set(self):
        """When sigma=0 and mu < bid_n, EV = mu - bid_n - 10."""
        mu = np.array([3.0])
        bid_n = np.array([5])
        result = compute_ev_vectorized(mu, 0.0, bid_n)
        expected = 3.0 - 5 - 10.0  # = -12.0
        np.testing.assert_allclose(result, [expected])

    def test_matches_scalar(self):
        """Vectorized result matches _compute_ev_static for single values."""
        test_cases = [
            (5.0, 1.5, 4),
            (7.0, 2.0, 6),
            (3.0, 1.0, 5),
            (8.5, 0.8, 8),
            (2.0, 3.0, 3),
            (5.0, 0.0, 5),  # sigma=0, make
            (4.9, 0.0, 5),  # sigma=0, set
        ]
        for mu, sigma, bid_n in test_cases:
            vec_result = compute_ev_vectorized(
                np.array([mu]), sigma, np.array([bid_n])
            )[0]
            scalar_result = _compute_ev_static(mu, sigma, bid_n)
            np.testing.assert_allclose(
                vec_result,
                scalar_result,
                atol=1e-12,
                err_msg=f"Mismatch for mu={mu}, sigma={sigma}, bid_n={bid_n}",
            )

    def test_vectorized_shape(self):
        """Output shape matches input shape."""
        mu = np.array([5.0, 6.0, 7.0])
        bid_n = np.array([4, 5, 6])
        result = compute_ev_vectorized(mu, 1.5, bid_n)
        assert result.shape == mu.shape


# ---------------------------------------------------------------------------
# bid_level_search_vectorized
# ---------------------------------------------------------------------------


class TestBidLevelSearch:
    def test_basic(self):
        """Returns valid bid_n in [1, 10]."""
        mu = np.array([5.0, 7.0, 3.0])
        best_n, best_util = bid_level_search_vectorized(mu, sigma=1.5)
        assert best_n.shape == (3,)
        assert np.all(best_n >= 1)
        assert np.all(best_n <= 10)

    def test_high_mu_positive_utility(self):
        """Very high mu should yield strongly positive utility."""
        mu = np.array([9.0])
        best_n, best_util = bid_level_search_vectorized(mu, sigma=1.0)
        # With mu=9, the bidder is almost certain to make, yielding
        # EV ~ 2*9 - 10 = 8.  The optimal bid_n is low (1) because
        # bidding higher adds set-risk without changing make-payoff.
        assert (
            best_util[0] > 7.0
        ), f"Expected high utility for mu=9, got {best_util[0]:.4f}"
        assert best_n[0] >= 1

    def test_low_mu_bids_low(self):
        """Very low mu should result in lowest bid level."""
        mu = np.array([0.5])
        best_n, _ = bid_level_search_vectorized(mu, sigma=1.0)
        assert best_n[0] == 1, f"Expected bid_n=1 for mu=0.5, got {best_n[0]}"

    def test_scalar_fallback_produces_results(self):
        """Non-zero risk_lambda triggers scalar fallback with valid results."""
        mu = np.array([5.0, 7.0, 3.0, 9.0])
        best_n, best_util = bid_level_search_vectorized(mu, sigma=1.5, risk_lambda=0.5)
        assert best_n.shape == (4,)
        assert best_util.shape == (4,)
        # bid_n in [0, 10]: 0 = pass, 1-10 = valid bid
        assert np.all(best_n >= 0)
        assert np.all(best_n <= 10)
        # Hands that bid should have finite utility; passes get -inf
        for i in range(len(mu)):
            if best_n[i] > 0:
                assert np.isfinite(
                    best_util[i]
                ), f"Expected finite utility for bid at mu={mu[i]}"
            else:
                assert best_util[i] == -np.inf

    def test_scalar_fallback_parity_with_compute_best_bid(self):
        """Scalar fallback agrees with direct compute_best_bid() calls."""
        mu_vals = np.array([4.0, 6.0, 8.0, 2.0, 5.5])
        sigma = 1.5
        risk_lambda = 0.3
        seed = 42

        best_n, best_util = bid_level_search_vectorized(
            mu_vals, sigma=sigma, risk_lambda=risk_lambda, seed=seed
        )

        for i, mu in enumerate(mu_vals):
            result = compute_best_bid(
                mu=float(mu),
                sigma=sigma,
                current_high_bid=0,
                pass_threshold=0.0,
                bid_level_search=True,
                risk_lambda=risk_lambda,
                seed=seed,
            )
            if result is not None:
                assert best_n[i] == result[0], (
                    f"bid_n mismatch at mu={mu}: "
                    f"vectorized={best_n[i]}, scalar={result[0]}"
                )
                np.testing.assert_allclose(
                    best_util[i],
                    result[1],
                    atol=1e-12,
                    err_msg=f"utility mismatch at mu={mu}",
                )
            else:
                assert best_n[i] == 0, f"Expected pass (0) at mu={mu}"
                assert best_util[i] == -np.inf

    def test_scalar_fallback_with_pass(self):
        """Low mu + risk penalty causes all hands to pass (bid_n=0).

        pass_threshold semantics: pass when utility <= -pass_threshold.
        With pass_threshold=0.0, pass when utility <= 0. Low mu values
        produce negative utility, so compute_best_bid returns None.
        """
        mu = np.array([0.5, 1.0, 2.0])
        best_n, best_util = bid_level_search_vectorized(
            mu, sigma=1.5, risk_lambda=0.5, pass_threshold=0.0
        )
        assert np.all(best_n == 0), f"Expected all passes, got {best_n}"
        assert np.all(
            best_util == -np.inf
        ), f"Expected -inf utility for passes, got {best_util}"

    def test_new_params_accepted_on_lambda_zero(self):
        """pass_threshold and seed accepted on vectorized path (lambda=0)."""
        mu = np.array([5.0, 7.0])
        # Should not raise — new params are accepted even on lambda=0 path
        best_n, best_util = bid_level_search_vectorized(
            mu, sigma=1.5, risk_lambda=0.0, pass_threshold=0.0, seed=99
        )
        assert best_n.shape == (2,)
        assert np.all(best_n >= 1)

    def test_scalar_fallback_deterministic(self):
        """Scalar fallback produces identical results with same seed."""
        mu = np.array([5.0, 7.0, 3.0])
        r1 = bid_level_search_vectorized(mu, sigma=1.5, risk_lambda=0.5, seed=42)
        r2 = bid_level_search_vectorized(mu, sigma=1.5, risk_lambda=0.5, seed=42)
        np.testing.assert_array_equal(r1[0], r2[0])
        np.testing.assert_array_equal(r1[1], r2[1])


# ---------------------------------------------------------------------------
# check_guardrails
# ---------------------------------------------------------------------------


class TestGuardrails:
    def test_all_pass(self):
        """Normal metrics should pass all guardrails."""
        ok, violations = check_guardrails({"bid_rate": 0.5, "make_rate": 0.7})
        assert ok is True
        assert violations == []

    def test_bid_rate_below_floor(self):
        """bid_rate below floor triggers violation."""
        ok, violations = check_guardrails({"bid_rate": 0.03, "make_rate": 0.7})
        assert ok is False
        assert len(violations) == 1
        assert "floor" in violations[0]

    def test_bid_rate_above_cap(self):
        """bid_rate above cap triggers violation."""
        ok, violations = check_guardrails({"bid_rate": 0.97, "make_rate": 0.7})
        assert ok is False
        assert len(violations) == 1
        assert "cap" in violations[0]

    def test_make_rate_below_floor(self):
        """make_rate below floor triggers violation."""
        ok, violations = check_guardrails({"bid_rate": 0.5, "make_rate": 0.40})
        assert ok is False
        assert len(violations) == 1
        assert "make_rate" in violations[0]

    def test_boundary_inclusive(self):
        """Exact boundary values should pass (not strict inequality)."""
        ok, violations = check_guardrails({"bid_rate": 0.05, "make_rate": 0.45})
        assert ok is True
        assert violations == []

        # Also test upper boundary
        ok2, violations2 = check_guardrails({"bid_rate": 0.95, "make_rate": 0.45})
        assert ok2 is True
        assert violations2 == []

    def test_multiple_violations(self):
        """All three guardrails violated at once."""
        ok, violations = check_guardrails({"bid_rate": 0.98, "make_rate": 0.30})
        assert ok is False
        # bid_rate > cap AND make_rate < floor = 2 violations
        assert len(violations) == 2

        # Test all 3: bid_rate < floor requires separate call since
        # bid_rate can't be both < floor AND > cap
        ok2, violations2 = check_guardrails({"bid_rate": 0.01, "make_rate": 0.30})
        assert ok2 is False
        assert len(violations2) == 2

    def test_guardrails_partial_metrics_no_keyerror(self):
        """check_guardrails with empty dict should not raise KeyError."""
        passed, violations = check_guardrails({})
        assert passed is True  # no metrics to violate
        assert violations == []

    def test_guardrails_only_bid_rate(self):
        """check_guardrails with only bid_rate should check just that."""
        passed, violations = check_guardrails({"bid_rate": 0.03})
        assert passed is False
        assert len(violations) == 1

    def test_bid_rate_key_custom(self):
        """check_guardrails uses bid_rate_key to select the bid rate metric."""
        # deal-level bid_rate would fail cap, but seat_bid_propensity passes
        metrics = {
            "bid_rate": 0.99,
            "seat_bid_propensity": 0.5,
            "make_rate": 0.7,
        }
        ok, violations = check_guardrails(metrics, bid_rate_key="seat_bid_propensity")
        assert ok is True
        assert violations == []

    def test_bid_rate_key_below_floor(self):
        """check_guardrails detects violation using custom bid_rate_key."""
        metrics = {
            "bid_rate": 0.13,
            "seat_bid_propensity": 0.034,
            "make_rate": 1.0,
        }
        ok, violations = check_guardrails(metrics, bid_rate_key="seat_bid_propensity")
        assert ok is False
        assert any("floor" in v for v in violations)

    def test_bid_rate_key_missing(self):
        """When custom bid_rate_key is absent from metrics, no bid rate violation."""
        ok, violations = check_guardrails(
            {"make_rate": 0.7}, bid_rate_key="seat_bid_propensity"
        )
        assert ok is True
        assert violations == []


# ---------------------------------------------------------------------------
# bootstrap_paired_delta
# ---------------------------------------------------------------------------


class TestBootstrapPairedDelta:
    def test_identical_values(self):
        """When baseline == candidate, delta should be ~0."""
        data = {i: float(i) for i in range(100)}
        delta, ci_lo, ci_hi = bootstrap_paired_delta(data, data)
        assert abs(delta) < 1e-12
        assert abs(ci_lo) < 1e-12
        assert abs(ci_hi) < 1e-12

    def test_clear_positive(self):
        """When candidate is clearly better, CI should exclude 0."""
        rng = np.random.RandomState(123)
        baseline = {i: rng.normal(0, 1) for i in range(500)}
        candidate = {i: baseline[i] + 2.0 for i in range(500)}  # +2.0 shift
        delta, ci_lo, ci_hi = bootstrap_paired_delta(baseline, candidate)
        assert delta > 1.5
        assert ci_lo > 0, "CI should exclude 0 for clear positive effect"

    def test_reproducible(self):
        """Same seed produces same results."""
        baseline = {i: float(i % 5) for i in range(50)}
        candidate = {i: float(i % 5) + 0.5 for i in range(50)}
        r1 = bootstrap_paired_delta(baseline, candidate, seed=42)
        r2 = bootstrap_paired_delta(baseline, candidate, seed=42)
        assert r1 == r2

    def test_mismatched_keys(self):
        """Mismatched keys should raise ValueError."""
        baseline = {1: 0.0, 2: 1.0}
        candidate = {1: 0.0, 3: 1.0}  # key 3 not in baseline
        with pytest.raises(ValueError, match="Keys must match"):
            bootstrap_paired_delta(baseline, candidate)

    def test_bootstrap_empty_dicts_raises(self):
        """bootstrap_paired_delta with empty dicts should raise ValueError."""
        with pytest.raises(ValueError, match="No paired observations"):
            bootstrap_paired_delta({}, {})


# ---------------------------------------------------------------------------
# ParameterSweep
# ---------------------------------------------------------------------------


class TestParameterSweep:
    def test_abstract_evaluate(self):
        """Base class evaluate_candidate raises NotImplementedError."""
        sweep = ParameterSweep(name="test", grid=[0.0, 1.0])
        with pytest.raises(NotImplementedError):
            sweep.evaluate_candidate(pd.DataFrame(), 0.0)

    def test_add_partition(self):
        """add_partition_column adds _partition column with train/val values."""
        sweep = ParameterSweep(name="test", grid=[0.0], split_seed=42)
        df = pd.DataFrame({"deal_id": [f"d_{i}" for i in range(100)]})
        result = sweep.add_partition_column(df)
        assert "_partition" in result.columns
        assert set(result["_partition"].unique()).issubset({"train", "val"})
        # Original df should not be modified
        assert "_partition" not in df.columns

    def test_threshold_sweep_name(self):
        """ThresholdSweep has correct name."""
        sweep = ThresholdSweep(grid=[0.0, 0.5, 1.0])
        assert sweep.name == "threshold"

    def test_lambda_sweep_name_and_threshold(self):
        """LambdaSweep has correct name and stores pass_threshold."""
        sweep = LambdaSweep(grid=[0.0, 0.1], pass_threshold=0.5)
        assert sweep.name == "lambda"
        assert sweep.pass_threshold == 0.5

    def test_run_train_selection(self):
        """run_train_selection picks best net_eppd from grid."""

        class MockSweep(ParameterSweep):
            def evaluate_candidate(self, df, param_value):
                # Higher param = lower metric (to test it picks the best)
                return {"net_eppd": 1.0 - param_value}

        sweep = MockSweep(name="mock", grid=[0.0, 0.5, 1.0])
        df = pd.DataFrame(
            {"deal_id": ["a", "b", "c"], "_partition": ["train", "train", "val"]}
        )
        best, results = sweep.run_train_selection(df)
        assert best == 0.0  # Highest net_eppd is at param=0.0
        assert len(results) == 3
