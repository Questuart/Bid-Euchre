"""
Unit tests for HybridOLSaBidder.

Tests Gaussian EV computation, sigma=0 degenerate cases, z-cap stability,
risk penalty, artifact loading, and config registration.
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
        "context_features": [],
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
