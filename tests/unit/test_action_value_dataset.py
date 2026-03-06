"""Unit tests for the R1.5 counterfactual action-value dataset generator."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Add scripts to path so we can import the generator
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "internal"))

from generate_action_value_dataset import (
    _bidding_order,
    _deterministic_dealer,
    _play_tricks,
    generate_dataset,
    run_partial_auction,
    simulate_counterfactual,
    validate_gate_x1,
)

from bid_euchre.sim.deals import generate_deal
from bid_euchre.strategy.bidding import (
    STATE_FEATURE_NAMES,
    AlwaysPassBidder,
    BidAction,
    StrictHellRaiser,
)

# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def seed():
    return 42


@pytest.fixture
def hands(seed):
    return generate_deal(seed, 0)


@pytest.fixture
def dealer(seed):
    return _deterministic_dealer(seed, 0)


@pytest.fixture
def raiser():
    """A continuation policy that bids aggressively (ensures non-misdeal)."""
    return StrictHellRaiser(name="test_raiser")


@pytest.fixture
def passer():
    """A continuation policy that always passes."""
    return AlwaysPassBidder(name="test_passer")


# ── Helpers ───────────────────────────────────────────────────


class TestBiddingOrder:
    def test_dealer_last(self):
        assert _bidding_order(0) == [1, 2, 3, 0]
        assert _bidding_order(2) == [3, 0, 1, 2]

    def test_four_seats(self):
        for dealer in range(4):
            order = _bidding_order(dealer)
            assert len(order) == 4
            assert set(order) == {0, 1, 2, 3}


class TestDeterministicDealer:
    def test_reproducible(self, seed):
        d1 = _deterministic_dealer(seed, 0)
        d2 = _deterministic_dealer(seed, 0)
        assert d1 == d2

    def test_range(self, seed):
        for deal_id in range(100):
            d = _deterministic_dealer(seed, deal_id)
            assert 0 <= d <= 3

    def test_matches_engine_formula(self, seed):
        """Verify dealer derivation matches play_single_hand's auction-mode formula.

        The engine uses: random.Random(deal_seed + deal_id).randrange(4)
        NOT the _deal_rng formula (seed * 1_000_003 + deal_id).
        """
        import random

        for deal_id in range(20):
            expected = random.Random(seed + deal_id).randrange(4)
            actual = _deterministic_dealer(seed, deal_id)
            assert actual == expected, (
                f"Dealer mismatch at deal_id={deal_id}: "
                f"engine={expected}, generator={actual}"
            )


# ── Partial Auction ───────────────────────────────────────────


class TestRunPartialAuction:
    def test_first_seat_empty_transcript(self, hands, dealer, raiser):
        """First seat to bid should have empty transcript and high_bid=0."""
        first_seat = _bidding_order(dealer)[0]
        high_bid, transcript = run_partial_auction(hands, dealer, first_seat, raiser)
        assert high_bid == 0
        assert len(transcript) == 0

    def test_later_seat_sees_prior_bids(self, hands, dealer, raiser):
        """A later seat should see prior bids in transcript."""
        order = _bidding_order(dealer)
        # Third seat should see 2 prior actions
        third_seat = order[2]
        high_bid, transcript = run_partial_auction(hands, dealer, third_seat, raiser)
        assert len(transcript) == 2
        # StrictHellRaiser always bids, so high_bid > 0
        assert high_bid > 0

    def test_all_pass_continuation(self, hands, dealer, passer):
        """With AlwaysPassBidder, all prior seats pass."""
        order = _bidding_order(dealer)
        last_seat = order[3]
        high_bid, transcript = run_partial_auction(hands, dealer, last_seat, passer)
        assert high_bid == 0
        assert len(transcript) == 3
        assert all(e["action"] == "PASS" for e in transcript)


# ── Counterfactual Simulation ─────────────────────────────────


class TestSimulateCounterfactual:
    def test_pass_returns_float(self, hands, dealer, raiser):
        """Pass action produces a float net_points."""
        focal = _bidding_order(dealer)[0]
        high_bid, transcript = run_partial_auction(hands, dealer, focal, raiser)
        result = simulate_counterfactual(
            hands,
            dealer,
            focal,
            BidAction.pass_bid(),
            high_bid,
            transcript,
            raiser,
        )
        assert isinstance(result, float)

    def test_bid_returns_float(self, hands, dealer, raiser):
        """Bid action produces a float net_points."""
        focal = _bidding_order(dealer)[0]
        high_bid, transcript = run_partial_auction(hands, dealer, focal, raiser)
        action = BidAction.bid(3, "S")
        result = simulate_counterfactual(
            hands,
            dealer,
            focal,
            action,
            high_bid,
            transcript,
            raiser,
        )
        assert isinstance(result, float)

    def test_misdeal_returns_zero(self, hands, dealer, passer):
        """When all pass (including forced pass), net_points=0."""
        focal = _bidding_order(dealer)[0]
        high_bid, transcript = run_partial_auction(hands, dealer, focal, passer)
        result = simulate_counterfactual(
            hands,
            dealer,
            focal,
            BidAction.pass_bid(),
            high_bid,
            transcript,
            passer,
        )
        assert result == 0.0

    def test_net_points_range(self, hands, dealer, raiser):
        """net_points should be in a plausible range."""
        focal = _bidding_order(dealer)[0]
        high_bid, transcript = run_partial_auction(hands, dealer, focal, raiser)
        action = BidAction.bid(3, "S")
        result = simulate_counterfactual(
            hands,
            dealer,
            focal,
            action,
            high_bid,
            transcript,
            raiser,
        )
        assert -20 <= result <= 20

    def test_different_actions_different_outcomes(self, raiser):
        """Across multiple deals, pass vs bid produce different net_points."""
        # Use multiple deals to avoid single-deal flukes where continuation
        # policy overwhelms the forced action
        results_pass = []
        results_bid = []
        for deal_id in range(10):
            hands = generate_deal(42, deal_id)
            dealer = _deterministic_dealer(42, deal_id)
            focal = _bidding_order(dealer)[0]
            high_bid, transcript = run_partial_auction(hands, dealer, focal, raiser)

            r_pass = simulate_counterfactual(
                hands,
                dealer,
                focal,
                BidAction.pass_bid(),
                high_bid,
                transcript,
                raiser,
            )
            r_bid = simulate_counterfactual(
                hands,
                dealer,
                focal,
                BidAction.bid(5, "S"),
                high_bid,
                transcript,
                raiser,
            )
            results_pass.append(r_pass)
            results_bid.append(r_bid)

        # Across 10 deals, pass and bid=5S should differ on at least one
        assert (
            results_pass != results_bid
        ), "Pass and bid always identical across 10 deals"


# ── Play Tricks ───────────────────────────────────────────────


class TestPlayTricks:
    def test_tricks_sum_to_ten(self, hands):
        t0, t1 = _play_tricks(
            hands, initial_leader=0, contract_type="suit", trump_suit="S"
        )
        assert t0 + t1 == 10

    def test_all_contract_types(self, hands):
        for ctype, trump in [
            ("suit", "C"),
            ("suit", "D"),
            ("high", None),
            ("low", None),
        ]:
            t0, t1 = _play_tricks(
                hands, initial_leader=0, contract_type=ctype, trump_suit=trump
            )
            assert t0 + t1 == 10
            assert 0 <= t0 <= 10


# ── Full Dataset Generation ──────────────────────────────────


class TestGenerateDataset:
    @pytest.fixture
    def small_df(self, raiser):
        """Generate a tiny dataset for testing (5 deals)."""
        return generate_dataset(
            seed=42, n_deals=5, continuation_policy=raiser, progress=False
        )

    def test_has_required_columns(self, small_df):
        required = {
            "hand_id",
            "deal_id",
            "focal_seat",
            "action_type",
            "contract_family",
            "bid_n",
            "trump_suit",
            "net_points",
        }
        assert required.issubset(set(small_df.columns))

    def test_has_state_features(self, small_df):
        for fname in STATE_FEATURE_NAMES:
            assert fname in small_df.columns, f"Missing: {fname}"

    def test_pass_coverage(self, small_df):
        """Exactly 1 pass per (deal_id, focal_seat)."""
        pass_df = small_df[small_df["action_type"] == "pass"]
        counts = pass_df.groupby(["deal_id", "focal_seat"]).size()
        assert (counts == 1).all()
        assert len(counts) == 5 * 4  # 5 deals × 4 seats

    def test_no_nan(self, small_df):
        feature_cols = STATE_FEATURE_NAMES + ["net_points"]
        assert small_df[feature_cols].isna().sum().sum() == 0

    def test_action_types(self, small_df):
        assert set(small_df["action_type"].unique()) == {"pass", "bid"}

    def test_contract_families(self, small_df):
        families = set(small_df["contract_family"].unique())
        # Must have at least pass (none) and some bid families
        assert "none" in families
        assert len(families) >= 2

    def test_row_count_plausible(self, small_df):
        """5 deals × 4 seats × ~40 avg actions ≈ 800 rows."""
        assert 200 <= len(small_df) <= 2000


# ── Determinism ───────────────────────────────────────────────


class TestDeterminism:
    def test_same_seed_same_output(self, raiser):
        df1 = generate_dataset(
            seed=99, n_deals=3, continuation_policy=raiser, progress=False
        )
        df2 = generate_dataset(
            seed=99, n_deals=3, continuation_policy=raiser, progress=False
        )
        pd.testing.assert_frame_equal(df1, df2)

    def test_different_seed_different_output(self, raiser):
        df1 = generate_dataset(
            seed=99, n_deals=3, continuation_policy=raiser, progress=False
        )
        df2 = generate_dataset(
            seed=100, n_deals=3, continuation_policy=raiser, progress=False
        )
        # Different seeds should produce different net_points
        assert not np.allclose(df1["net_points"].values, df2["net_points"].values)


# ── Gate X1 ───────────────────────────────────────────────────


class TestGateX1:
    def test_passes_on_valid_data(self, raiser):
        df = generate_dataset(
            seed=42, n_deals=10, continuation_policy=raiser, progress=False
        )
        # Should not raise
        validate_gate_x1(df, n_deals=10)

    def test_fails_on_missing_pass(self, raiser):
        df = generate_dataset(
            seed=42, n_deals=5, continuation_policy=raiser, progress=False
        )
        # Remove all pass rows
        df_no_pass = df[df["action_type"] != "pass"].copy()
        with pytest.raises(AssertionError, match="pass"):
            validate_gate_x1(df_no_pass, n_deals=5)
