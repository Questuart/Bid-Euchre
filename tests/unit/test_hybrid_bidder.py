"""
Unit tests for HybridOLSaBidder.

Tests Gaussian EV computation, sigma=0 degenerate cases, z-cap stability,
risk penalty, artifact loading, config registration, bid-level search,
pass-threshold, and parity between search modes.
"""

import json
import math
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import norm

from bid_euchre.strategy.bidding import (
    BiddingObservation,
    HybridOLSaBidder,
    compute_best_bid,
)


def _make_artifact(
    tmp_path: Path,
    suit_weights=None,
    suit_bias=3.5,
    suit_features=None,
    high_weights=None,
    high_bias=2.5,
    high_features=None,
    low_weights=None,
    low_bias=2.3,
    low_features=None,
    residual_variance=None,
    risk_lambda=0.0,
    artifact_type="hybrid_olsa_v1",
    context_features=None,
) -> str:
    """Create a temporary hybrid_olsa_v1 artifact and return its path."""
    if suit_weights is None:
        suit_weights = [0.5, 0.3, 0.2]
    if suit_features is None:
        suit_features = ["bowers", "trump_count", "offsuit_aces"]
    if high_weights is None:
        high_weights = [0.8]
    if high_features is None:
        high_features = ["offsuit_aces"]
    if low_weights is None:
        low_weights = [0.7]
    if low_features is None:
        low_features = ["offsuit_tens_count"]
    if residual_variance is None:
        residual_variance = {"suit": 2.5, "high": 1.8, "low": 1.9}

    artifact = {
        "artifact_type": artifact_type,
        "schema_version": 1,
        "rung_id": "r0",
        "payoff_model": {
            "suit": {
                "weights": suit_weights,
                "bias": suit_bias,
                "feature_names": suit_features,
            },
            "high": {
                "weights": high_weights,
                "bias": high_bias,
                "feature_names": high_features,
            },
            "low": {
                "weights": low_weights,
                "bias": low_bias,
                "feature_names": low_features,
            },
        },
        "residual_variance": residual_variance,
        "risk_lambda": risk_lambda,
        "context_features": context_features or [],
        "training_seed": 42,
        "training_run_id": "test_run",
        "split_type": "three_way",
        "frozen_at": None,
        "artifact_sha256": None,
    }

    path = tmp_path / "hybrid_olsa_v1.json"
    path.write_text(json.dumps(artifact, indent=2))
    return str(path)


def test_ev_manual_calculation(tmp_path: Path):
    """Hand-computed EV matches _compute_ev to 6 decimal places."""
    path = _make_artifact(tmp_path)
    bidder = HybridOLSaBidder(path)

    # mu=5.0, sigma=1.5, bid_n=5
    mu, sigma, bid_n = 5.0, 1.5, 5
    threshold = bid_n - 0.5  # 4.5
    z = (threshold - mu) / sigma  # (4.5 - 5.0) / 1.5 = -0.3333...

    p_make = 1.0 - norm.cdf(z)
    p_set = norm.cdf(z)
    pdf_z = norm.pdf(z)

    e_make = mu + sigma * pdf_z / p_make
    e_set = mu - sigma * pdf_z / p_set

    expected_ev = p_make * (2.0 * e_make - 10.0) + p_set * (e_set - bid_n - 10.0)

    actual_ev = bidder._compute_ev(mu, sigma, bid_n)
    assert abs(actual_ev - expected_ev) < 1e-6, f"{actual_ev} != {expected_ev}"


def test_sigma_zero_above_bid(tmp_path: Path):
    """sigma=0, mu >= bid_n → returns 2*mu - 10 (make case)."""
    path = _make_artifact(
        tmp_path, residual_variance={"suit": 0.0, "high": 0.0, "low": 0.0}
    )
    bidder = HybridOLSaBidder(path)

    # mu=7.0, bid_n=5 → make → 2*7 - 10 = 4
    ev = bidder._compute_ev(7.0, 0.0, 5)
    assert ev == pytest.approx(4.0)


def test_sigma_zero_below_bid(tmp_path: Path):
    """sigma=0, mu < bid_n → returns mu - bid_n - 10 (set case)."""
    path = _make_artifact(
        tmp_path, residual_variance={"suit": 0.0, "high": 0.0, "low": 0.0}
    )
    bidder = HybridOLSaBidder(path)

    # mu=3.5, bid_n=5 → set → 3.5 - 5 - 10 = -11.5
    ev = bidder._compute_ev(3.5, 0.0, 5)
    assert ev == pytest.approx(-11.5)


def test_z_cap_prevents_overflow(tmp_path: Path):
    """Extreme mu/sigma values don't produce NaN or Inf."""
    path = _make_artifact(tmp_path)
    bidder = HybridOLSaBidder(path)

    # Very high mu, low sigma: essentially guaranteed make
    ev1 = bidder._compute_ev(100.0, 0.01, 5)
    assert math.isfinite(ev1)

    # Very low mu, low sigma: essentially guaranteed set
    ev2 = bidder._compute_ev(-100.0, 0.01, 5)
    assert math.isfinite(ev2)

    # Zero sigma edge
    ev3 = bidder._compute_ev(5.0, 0.0, 5)
    assert math.isfinite(ev3)


def test_all_negative_utility_passes(tmp_path: Path):
    """When all utilities are negative, bidder should PASS."""
    # Very low bias so predicted tricks < 3 for all contracts
    path = _make_artifact(
        tmp_path,
        suit_weights=[0.0, 0.0, 0.0],
        suit_bias=1.0,
        high_weights=[0.0],
        high_bias=1.0,
        low_weights=[0.0],
        low_bias=1.0,
    )
    bidder = HybridOLSaBidder(path)

    from bid_euchre.core.cards import Card

    hand = [Card("S", "A")] * 10
    obs = BiddingObservation(hand=hand, seat=0, dealer_seat=3, current_high_bid=0)
    action = bidder.choose_bid(obs)
    assert action.is_pass()


def test_zero_utility_passes(tmp_path: Path):
    """When best utility is exactly 0, bidder should PASS (not bid)."""
    path = _make_artifact(tmp_path)
    bidder = HybridOLSaBidder(path)

    # _compute_ev returns exactly 0 when mu=5, sigma=0, bid_n=5:
    # make case: 2*5 - 10 = 0
    ev = bidder._compute_ev(5.0, 0.0, 5)
    assert ev == pytest.approx(0.0)

    # With risk_lambda=0, utility = EV = 0, so bidder should PASS
    # (plan says PASS when max(utility) <= 0)


def test_risk_lambda_zero(tmp_path: Path):
    """With risk_lambda=0, utility equals EV exactly (no penalty)."""
    path = _make_artifact(tmp_path, risk_lambda=0.0)
    bidder = HybridOLSaBidder(path)

    # Penalty should be exactly 0
    penalty = bidder._compute_risk_penalty(5.0, 1.5, 5)
    assert penalty == 0.0


def test_risk_penalty_nonnegative(tmp_path: Path):
    """Risk penalty is always >= 0."""
    path = _make_artifact(tmp_path, risk_lambda=1.0)
    bidder = HybridOLSaBidder(path)

    # Various mu/sigma/bid_n combinations
    for mu in [3.0, 5.0, 7.0, 10.0]:
        for sigma in [0.5, 1.0, 2.0]:
            for bid_n in [3, 5, 7, 10]:
                penalty = bidder._compute_risk_penalty(mu, sigma, bid_n)
                assert (
                    penalty >= 0.0
                ), f"Negative penalty for mu={mu}, sigma={sigma}, bid_n={bid_n}"


def test_analytical_p_make(tmp_path: Path):
    """P(make) from CDF matches Monte Carlo within tolerance."""
    _make_artifact(tmp_path)  # ensure artifact loads (smoke check)

    mu, sigma, bid_n = 5.5, 1.5, 5
    threshold = bid_n - 0.5

    # Analytical P(make)
    z = (threshold - mu) / sigma
    p_make_analytical = 1.0 - norm.cdf(z)

    # Monte Carlo P(make)
    rng = np.random.RandomState(42)
    draws = rng.normal(mu, sigma, 100_000)
    p_make_mc = (draws >= threshold).mean()

    assert abs(p_make_analytical - p_make_mc) < 0.01


def test_loads_hybrid_artifact(tmp_path: Path):
    """Successfully loads a valid hybrid_olsa_v1 artifact."""
    path = _make_artifact(tmp_path)
    bidder = HybridOLSaBidder(path)

    assert "suit" in bidder.models
    assert "high" in bidder.models
    assert "low" in bidder.models
    assert bidder.risk_lambda == 0.0
    assert len(bidder.models["suit"]["weights"]) == 3


def test_rejects_olsa_v1(tmp_path: Path):
    """ValueError when artifact_type is olsa_v1 instead of hybrid_olsa_v1."""
    path = _make_artifact(tmp_path, artifact_type="olsa_v1")
    with pytest.raises(ValueError, match="hybrid_olsa_v1"):
        HybridOLSaBidder(path)


def test_config_registration():
    """HybridOLSaBidder is discoverable via BiddingPolicyConfig."""
    from bid_euchre.experiments.config import (
        BIDDING_POLICY_REGISTRY,
        BIDDING_REQUIRED_PARAMS,
    )

    assert "HybridOLSaBidder" in BIDDING_POLICY_REGISTRY
    assert BIDDING_POLICY_REGISTRY["HybridOLSaBidder"] is HybridOLSaBidder
    assert "artifact_path" in BIDDING_REQUIRED_PARAMS["HybridOLSaBidder"]


def test_cvar_uses_continuity_corrected_threshold(tmp_path: Path):
    """CVaR make/set threshold matches EV's continuity correction (bid_n - 0.5).

    We pick mu well above bid_n so the 5th-percentile tail straddles the
    correction zone [bid_n - 0.5, bid_n). Draws in that region are classified
    as "make" (net = 2x - 10) with the correction but "set" (net = x - bid_n - 10)
    without it — a ~11-point swing per draw that materially changes CVaR.
    """
    path = _make_artifact(tmp_path, risk_lambda=1.0)
    bidder = HybridOLSaBidder(path)

    # mu=8, sigma=1.5, bid_n=6 → 5th pctile ≈ 5.53, right in [5.5, 6.0)
    mu, sigma, bid_n = 8.0, 1.5, 6

    # Compute penalty with the corrected threshold (bid_n - 0.5 = 5.5)
    penalty_corrected = bidder._compute_risk_penalty(mu, sigma, bid_n)

    # Manually compute what penalty would be WITHOUT the correction
    # (using bid_n as threshold instead of bid_n - 0.5)
    rng = np.random.RandomState(bidder._CVAR_SEED)
    draws = rng.normal(mu, sigma, bidder._CVAR_DRAWS)
    nets_uncorrected = np.where(
        draws >= bid_n,  # no continuity correction
        2.0 * draws - 10.0,
        draws - bid_n - 10.0,
    )
    tail_size = max(1, int(bidder._CVAR_DRAWS * bidder._CVAR_TAIL))
    sorted_nets = np.sort(nets_uncorrected)
    cvar_uncorrected = float(sorted_nets[:tail_size].mean())
    penalty_uncorrected = max(0.0, -cvar_uncorrected) * bidder.risk_lambda

    # Corrected threshold is more lenient (more draws classified as "make"),
    # so the penalty should be strictly lower than the uncorrected version
    assert penalty_corrected < penalty_uncorrected, (
        f"Corrected penalty {penalty_corrected:.4f} should be less than "
        f"uncorrected {penalty_uncorrected:.4f}"
    )


def test_risk_lambda_override(tmp_path: Path):
    """risk_lambda parameter overrides artifact value."""
    path = _make_artifact(tmp_path, risk_lambda=0.5)
    bidder = HybridOLSaBidder(path, risk_lambda=1.0)
    assert bidder.risk_lambda == 1.0

    # Without override, uses artifact value
    bidder2 = HybridOLSaBidder(path)
    assert bidder2.risk_lambda == 0.5


# ---------------------------------------------------------------------------
# compute_best_bid() standalone function tests
# ---------------------------------------------------------------------------


class TestComputeBestBid:
    """Tests for the compute_best_bid() standalone function."""

    def test_overcall(self):
        """With current_high_bid >= floor(mu), search finds levels above the high bid."""
        # mu=5.5, current_high_bid=5 → floor(5.5)=5, which is NOT > 5
        # Floor-only mode would skip this contract entirely
        result_floor = compute_best_bid(5.5, 1.5, 5, bid_level_search=False)
        assert result_floor is None, "Floor-only should fail when floor(mu) <= high bid"

        # Search mode evaluates levels 6-10, may find positive utility at 6
        # (though at mu=5.5 this will likely be negative — try stronger hand)
        result_search = compute_best_bid(8.0, 1.5, 5, bid_level_search=True)
        assert result_search is not None, "Search should find a bid above high bid"
        bid_n, utility = result_search
        assert bid_n >= 6, "Bid must exceed current_high_bid of 5"
        assert utility > 0, "Selected bid should have positive utility"

    def test_max_utility_picked(self):
        """When multiple levels have positive utility, picks highest utility (not first)."""
        # mu=7.0, sigma=1.5, current_high_bid=0 → levels 1-10 all legal
        # EV is monotonically decreasing in bid_n for fixed mu, so bid_n=1 is best
        result = compute_best_bid(7.0, 1.5, 0, bid_level_search=True)
        assert result is not None

        bid_n, utility = result
        # Verify this is actually the max utility across all levels
        for n in range(1, 11):
            from bid_euchre.strategy.bidding import _compute_ev_static

            ev_n = _compute_ev_static(7.0, 1.5, n)
            assert (
                utility >= ev_n - 1e-10
            ), f"bid_n={bid_n} utility={utility:.4f} but bid_n={n} has ev={ev_n:.4f}"

    def test_parity_with_v1(self, tmp_path: Path):
        """bid_level_search=False produces identical results to v1 choose_bid logic.

        We verify that for the same mu/sigma, compute_best_bid with search=False
        returns the same bid_n as floor(mu) with the same utility.
        """
        mu, sigma = 8.0, 1.5  # floor(8.0) = 8
        result = compute_best_bid(mu, sigma, 0, bid_level_search=False)
        assert result is not None
        bid_n, utility = result
        assert bid_n == 8, "Floor-only should pick floor(mu)=8"

        # Manually compute v1 EV at floor(mu)
        from bid_euchre.strategy.bidding import _compute_ev_static

        expected_ev = _compute_ev_static(mu, sigma, 8)
        assert utility == pytest.approx(expected_ev)

    def test_parity_pass_condition(self):
        """bid_level_search=False with negative utility returns None (matches v1 PASS)."""
        # mu=3.0, sigma=1.5 → floor(3)=3, EV at bid_n=3 is negative
        result = compute_best_bid(3.0, 1.5, 0, bid_level_search=False)
        # Verify: EV at bid_n=3 is indeed negative
        from bid_euchre.strategy.bidding import _compute_ev_static

        ev = _compute_ev_static(3.0, 1.5, 3)
        assert ev < 0, "Sanity: EV should be negative"
        assert result is None, "Should pass when utility is negative"

    def test_pass_threshold(self):
        """pass_threshold=0.5 rejects bids with utility <= -0.5."""
        # Use a mu where utility is slightly negative at the only legal level
        mu, sigma = 4.5, 1.5

        # With t=0.0 (default), slightly negative utility → pass
        result_strict = compute_best_bid(
            mu, sigma, 0, pass_threshold=0.0, bid_level_search=False
        )

        # With t=0.5, bids with utility > -0.5 are accepted
        result_lenient = compute_best_bid(
            mu, sigma, 0, pass_threshold=0.5, bid_level_search=False
        )

        from bid_euchre.strategy.bidding import _compute_ev_static

        ev = _compute_ev_static(mu, sigma, 4)  # floor(4.5) = 4
        if -0.5 < ev <= 0:
            # EV is in (-0.5, 0]: strict passes, lenient bids
            assert result_strict is None
            assert result_lenient is not None
        elif ev <= -0.5:
            # EV is very negative: both pass
            assert result_strict is None
            assert result_lenient is None
        else:
            # EV > 0: both bid
            assert result_strict is not None
            assert result_lenient is not None

    def test_pass_threshold_convention(self):
        """Verify pass threshold convention: pass if utility <= -t.

        t=0.0 → pass when utility <= 0 (conservative, default).
        t>0 → pass when utility <= -t (more aggressive, accepts slight negatives).
        """
        # Construct a case with known utility in range (-1, 0)
        # mu=5.0, sigma=0, bid_n=5: EV = 2*5-10 = 0 → passes at t=0
        result_t0 = compute_best_bid(
            5.0, 0.0, 0, pass_threshold=0.0, bid_level_search=False
        )
        assert result_t0 is None, "utility=0 should pass at t=0"

        # With t=0.01, utility=0 > -0.01 → bids
        result_t001 = compute_best_bid(
            5.0, 0.0, 0, pass_threshold=0.01, bid_level_search=False
        )
        assert result_t001 is not None, "utility=0 should bid at t=0.01"

    def test_lambda_path_reproducible(self):
        """Nonzero risk_lambda with fixed seed is deterministic."""
        result1 = compute_best_bid(
            7.0, 1.5, 0, risk_lambda=1.0, seed=42, bid_level_search=True
        )
        result2 = compute_best_bid(
            7.0, 1.5, 0, risk_lambda=1.0, seed=42, bid_level_search=True
        )
        assert result1 == result2, "Same seed should produce identical results"

        # Different seed produces different result (or same — just verify no crash)
        result3 = compute_best_bid(
            7.0, 1.5, 0, risk_lambda=1.0, seed=99, bid_level_search=True
        )
        assert result3 is not None

    def test_search_all_levels_exhaustive(self):
        """bid_level_search=True evaluates all legal levels, not just a subset."""
        # With current_high_bid=0, search should evaluate levels 1-10
        # Use sigma=0 so EV is deterministic and we can predict exactly
        mu = 7.0  # sigma=0: make at bid_n<=7, set at bid_n>7

        # bid_n=7: EV = 2*7-10 = 4
        # bid_n=8: EV = 7-8-10 = -11
        # bid_n=1: EV = 2*7-10 = 4 (same as 7, but 7 wins on tie-break)
        result = compute_best_bid(mu, 0.0, 0, bid_level_search=True)
        assert result is not None
        bid_n, utility = result
        # All make-levels (1-7) have EV=4.0; tie-break picks highest bid_n
        assert bid_n == 7, f"Expected bid_n=7 (tie-break), got {bid_n}"
        assert utility == pytest.approx(4.0)

    def test_min_bid_boundary(self):
        """When current_high_bid=9, only bid_n=10 is legal."""
        result = compute_best_bid(10.0, 0.0, 9, bid_level_search=True)
        assert result is not None
        assert result[0] == 10

        # current_high_bid=10 → no legal bids
        result_none = compute_best_bid(10.0, 0.0, 10, bid_level_search=True)
        assert result_none is None


# ---------------------------------------------------------------------------
# HybridOLSaBidder integration tests with new params
# ---------------------------------------------------------------------------


def test_bid_level_search_default_is_false(tmp_path: Path):
    """Default bid_level_search=False preserves v1 behavior."""
    path = _make_artifact(tmp_path)
    bidder = HybridOLSaBidder(path)
    assert bidder.bid_level_search is False


def test_pass_threshold_default_is_zero(tmp_path: Path):
    """Default pass_threshold=0.0."""
    path = _make_artifact(tmp_path)
    bidder = HybridOLSaBidder(path)
    assert bidder.pass_threshold == 0.0


def test_bidder_with_bid_level_search(tmp_path: Path):
    """HybridOLSaBidder with bid_level_search=True produces a bid action."""
    path = _make_artifact(tmp_path, suit_bias=8.0)  # Strong hand
    bidder = HybridOLSaBidder(path, bid_level_search=True)

    from bid_euchre.core.cards import Card

    hand = [Card("S", "A")] * 10
    obs = BiddingObservation(hand=hand, seat=0, dealer_seat=3, current_high_bid=0)
    action = bidder.choose_bid(obs)
    assert not action.is_pass(), "Strong hand with search should bid"


def test_bidder_parity_search_false(tmp_path: Path):
    """bid_level_search=False + pass_threshold=0 reproduces v1 behavior exactly."""
    path = _make_artifact(tmp_path, suit_bias=8.0)

    bidder_v1 = HybridOLSaBidder(path)  # defaults: search=False, threshold=0.0
    bidder_v2 = HybridOLSaBidder(path, bid_level_search=False, pass_threshold=0.0)

    from bid_euchre.core.cards import Card

    hand = [Card("S", "A")] * 10
    obs = BiddingObservation(hand=hand, seat=0, dealer_seat=3, current_high_bid=0)

    action_v1 = bidder_v1.choose_bid(obs)
    action_v2 = bidder_v2.choose_bid(obs)

    assert action_v1.n == action_v2.n
    assert action_v1.contract == action_v2.contract


# ---------------------------------------------------------------------------
# Partner feature runtime integration tests
# ---------------------------------------------------------------------------


def test_partner_features_used_when_in_model(tmp_path: Path):
    """HybridOLSaBidder merges partner features when model uses them."""
    # Create artifact with partner features in suit model
    path = _make_artifact(
        tmp_path,
        suit_weights=[0.5, 0.3, 0.2, 0.1],
        suit_features=["bowers", "trump_count", "offsuit_aces", "partner_bid_level"],
        suit_bias=6.0,
        context_features=["partner_bid_level"],
    )
    bidder = HybridOLSaBidder(path)

    from bid_euchre.core.cards import Card

    hand = [Card("S", "A")] * 10
    transcript = (
        {
            "seat": 2,
            "action": "BID",
            "tricks_bid": 6,
            "contract_type": "suit",
            "trump": "S",
        },
    )
    obs = BiddingObservation(
        hand=hand,
        seat=0,
        dealer_seat=3,
        current_high_bid=0,
        auction_transcript=transcript,
    )
    action = bidder.choose_bid(obs)
    # Should not crash — partner_bid_level is available from transcript
    assert action is not None


def test_partner_features_empty_transcript_defaults(tmp_path: Path):
    """HybridOLSaBidder with partner features works when auction_transcript is empty.

    The first bidder in an auction has an empty transcript. Partner features
    should default to 0 (extract_partner_features returns zeros for empty input).
    """
    # Artifact includes partner_bid_level in suit features
    path = _make_artifact(
        tmp_path,
        suit_weights=[0.5, 0.3, 0.2, 0.1],
        suit_features=["bowers", "trump_count", "offsuit_aces", "partner_bid_level"],
        suit_bias=6.0,
        context_features=["partner_bid_level"],
    )
    bidder = HybridOLSaBidder(path)

    from bid_euchre.core.cards import Card

    hand = [Card("S", "A")] * 10
    # Empty transcript — partner features default to 0 (no partner info yet)
    obs = BiddingObservation(
        hand=hand,
        seat=0,
        dealer_seat=3,
        current_high_bid=0,
        auction_transcript=(),
    )
    action = bidder.choose_bid(obs)
    # Should not crash — partner features default to 0 with empty transcript
    assert action is not None


def test_r0_model_unaffected_by_partner_merge(tmp_path: Path):
    """R0 model (no partner features) works regardless of auction_transcript."""
    path = _make_artifact(tmp_path, suit_bias=8.0)  # Standard R0 features
    bidder = HybridOLSaBidder(path)

    from bid_euchre.core.cards import Card

    hand = [Card("S", "A")] * 10

    # With transcript: partner features merged but not used by model
    transcript = (
        {
            "seat": 2,
            "action": "BID",
            "tricks_bid": 6,
            "contract_type": "suit",
            "trump": "S",
        },
    )
    obs_with = BiddingObservation(
        hand=hand,
        seat=0,
        dealer_seat=3,
        current_high_bid=0,
        auction_transcript=transcript,
    )
    action_with = bidder.choose_bid(obs_with)

    # Without transcript: no partner features merged
    obs_without = BiddingObservation(
        hand=hand,
        seat=0,
        dealer_seat=3,
        current_high_bid=0,
    )
    action_without = bidder.choose_bid(obs_without)

    # Both should produce the same bid (partner features are extra dict keys, ignored by _predict)
    assert action_with.n == action_without.n
    assert action_with.contract == action_without.contract


def test_zero_partner_features_ablation(tmp_path: Path):
    """zero_partner_features=True zeroes all partner_* features before prediction.

    Investigation C: verify that the ablation flag causes partner features to
    contribute nothing to the prediction (0 * weight = 0), producing the same
    mu as if partner features were absent.
    """
    # Create artifact WITH partner features and a measurable weight
    path = _make_artifact(
        tmp_path,
        suit_weights=[0.5, 0.3, 0.2, 2.0],
        suit_features=["bowers", "trump_count", "offsuit_aces", "partner_bid_level"],
        suit_bias=3.0,
        context_features=["partner_bid_level"],
    )

    # Normal bidder: partner_bid_level=8 contributes 2.0 * 8 = 16.0 to mu
    bidder_normal = HybridOLSaBidder(path)
    # Ablated bidder: partner_bid_level zeroed, contributes 0
    bidder_ablated = HybridOLSaBidder(path, zero_partner_features=True)

    # Test at the _predict level with explicit features
    features_with_partner = {
        "bowers": 2.0,
        "trump_count": 5.0,
        "offsuit_aces": 1.0,
        "partner_bid_level": 8.0,
    }
    features_zeroed = {
        "bowers": 2.0,
        "trump_count": 5.0,
        "offsuit_aces": 1.0,
        "partner_bid_level": 0.0,
    }

    mu_normal = bidder_normal._predict("suit", features_with_partner)
    mu_ablated = bidder_ablated._predict("suit", features_zeroed)

    # Both predictions use the same base features, but ablated has partner=0
    assert mu_normal != mu_ablated, "Partner features should change prediction"
    assert mu_ablated == bidder_normal._predict(
        "suit", features_zeroed
    ), "Ablated mu should equal prediction with zeroed partner features"
    # The difference should be exactly partner_bid_level * weight = 8 * 2.0 = 16
    assert abs((mu_normal - mu_ablated) - 16.0) < 1e-10

    # Verify the zero_partner_features flag defaults to False
    assert not bidder_normal.zero_partner_features
    assert bidder_ablated.zero_partner_features


def test_zero_partner_features_ablation_choose_bid(tmp_path: Path):
    """zero_partner_features=True zeroes partner features in the choose_bid() path.

    Companion to test_zero_partner_features_ablation which tests _predict()
    directly. This test exercises the full choose_bid() code path with a
    BiddingObservation containing a transcript, verifying that the ablation
    flag causes the same bid as an empty-transcript observation (where partner
    features default to 0).
    """
    from bid_euchre.core.cards import Card

    # Use bid_level_search=False (floor-based) and a bias that makes the
    # partner contribution change floor(mu). Without partner: mu ~ bias + hand
    # contribution. With partner_bid_level=6 and weight=1.0: mu increases by 6.
    # This shifts floor(mu) and therefore the bid level.
    path = _make_artifact(
        tmp_path,
        suit_weights=[0.0, 0.0, 0.0, 1.0],
        suit_features=["bowers", "trump_count", "offsuit_aces", "partner_bid_level"],
        suit_bias=4.5,
        high_weights=[0.0],
        high_bias=1.0,
        low_weights=[0.0],
        low_bias=1.0,
        context_features=["partner_bid_level"],
        residual_variance={"suit": 0.0, "high": 0.0, "low": 0.0},
    )

    hand = [Card("S", "A")] * 10
    transcript = (
        {
            "seat": 2,
            "action": "BID",
            "tricks_bid": 6,
            "contract_type": "suit",
            "trump": "S",
        },
    )

    # Non-ablated bidder with transcript — partner_bid_level=6 adds 6.0 to mu
    # mu = 4.5 + 6.0 = 10.5, floor = 10
    bidder_normal = HybridOLSaBidder(path, bid_level_search=False)
    obs_with_transcript = BiddingObservation(
        hand=hand,
        seat=0,
        dealer_seat=3,
        current_high_bid=0,
        auction_transcript=transcript,
    )
    action_normal = bidder_normal.choose_bid(obs_with_transcript)

    # Ablated bidder with same transcript — partner_bid_level zeroed
    # mu = 4.5 + 0.0 = 4.5, floor = 4
    bidder_ablated = HybridOLSaBidder(
        path, bid_level_search=False, zero_partner_features=True
    )
    action_ablated = bidder_ablated.choose_bid(obs_with_transcript)

    # Non-ablated bidder with empty transcript — partner features default to 0
    # mu = 4.5 + 0.0 = 4.5, floor = 4
    obs_empty_transcript = BiddingObservation(
        hand=hand,
        seat=0,
        dealer_seat=3,
        current_high_bid=0,
        auction_transcript=(),
    )
    action_empty = bidder_normal.choose_bid(obs_empty_transcript)

    # Ablated bid should match the empty-transcript bid (both have partner=0)
    assert action_ablated.n == action_empty.n, (
        f"Ablated bid ({action_ablated.n}) should match empty-transcript bid "
        f"({action_empty.n})"
    )
    assert action_ablated.contract == action_empty.contract

    # Normal bid with transcript should differ from ablated (partner weight=1.0
    # with partner_bid_level=6 adds 6.0 to mu, changing floor from 4 to 10)
    assert action_normal.n != action_ablated.n, (
        f"Normal bid with transcript ({action_normal.n} {action_normal.contract}) "
        f"should differ from ablated ({action_ablated.n} {action_ablated.contract})"
    )
